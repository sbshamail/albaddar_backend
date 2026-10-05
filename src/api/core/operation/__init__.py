from sqlalchemy.exc import DataError
from datetime import datetime, timezone
from fastapi import Query
from sqlalchemy import ScalarResult, func
from sqlmodel import Session, SQLModel, select
from typing import List, Optional
from src.lib.db_con import get_session

from src.api.core.response import api_response
from src.api.core.operation.list_operation_helper import (
    applyFilters,
)


# Update only the fields that are provided in the request
# customFields = ["phone", "firstname", "lastname", "email"]
def updateOp(
    instance,
    request,
    session,
    customFields=None,
):
    # CASE 1: Only update custom fields
    if customFields:
        for field in customFields:
            if hasattr(request, field):
                value = getattr(request, field)
                if value is not None:
                    setattr(instance, field, value)

    else:
        # CASE 2: Auto-update all fields
        # Handle both Pydantic models AND plain classes
        if hasattr(request, "model_dump"):
            # Pydantic / SQLModel
            data = request.model_dump(exclude_unset=True)
        else:
            # Plain Class: extract fields with vars()
            data = {
                key: value for key, value in vars(request).items() if value is not None
            }

        # Apply updates
        for key, value in data.items():
            if hasattr(instance, key):  # if the key is in the model
                setattr(instance, key, value)

    # Update timestamp
    if hasattr(instance, "updated_at"):
        instance.updated_at = datetime.now(timezone.utc)

    session.add(instance)
    return instance


def _exec(session, statement, Model):
    result = session.exec(statement)
    # If it's already Model objects, just return .all()
    if isinstance(result, ScalarResult):  # SQLAlchemy 2.x ScalarResult
        return result.all()
    else:
        # Fallback: try scalars (for select(Model))
        try:
            return result.scalars().all()
        except Exception:
            return result.all()


def listop(
    session: Session,
    Model: type[SQLModel],
    filters: dict[str, any],
    searchFields: List[str],
    join_options: list = [],
    page: int = None,
    skip: int = 0,
    limit: int = Query(10, ge=1, le=200),
    Statement=None,
    otherFilters=None,
    sort=None,
):

    # Compute skip based on page
    if page is not None and page > 0:
        skip = (page - 1) * limit

    # ✅ Fix: avoid boolean check on SQLAlchemy statements
    statement = Statement if Statement is not None else select(Model)

    # Apply JOINs (like selectinload)
    if join_options:
        for option in join_options:
            statement = statement.options(option)

    searchTerm = filters.get("searchTerm")
    columnFilters = filters.get("columnFilters")
    dateRange = filters.get("dateRange")
    numberRange = filters.get("numberRange")
    customFilters = filters.get("customFilters")
    stringArrayFilters = filters.get("stringArrayFilters")
    objectArrayFilters = filters.get("objectArrayFilters")
    geoFilters = filters.get("geoFilters")
    deepFilters = filters.get("deepFilters")

    # Apply Filters
    statement = applyFilters(
        statement,
        Model=Model,
        searchTerm=searchTerm,
        searchFields=searchFields,
        columnFilters=columnFilters,
        dateRange=dateRange,
        numberRange=numberRange,
        customFilters=customFilters,
        otherFilters=otherFilters,
        sort=sort if sort else '["created_at", "desc"]',
        stringArrayFilters=stringArrayFilters,
        objectArrayFilters=objectArrayFilters,
        geoFilters=geoFilters,
        deepFilters=deepFilters,
    )

    # Total count (before pagination) — count in the DB, don't load every row
    count_stmt = select(func.count()).select_from(statement.order_by(None).subquery())
    total_count = session.exec(count_stmt).one()

    # Now apply pagination (skip/limit)
    paginated_stmt = statement.offset(skip).limit(limit)
    results = _exec(session, paginated_stmt, Model)

    return {"data": results, "total": total_count}


def listRecords(
    query_params: dict,
    searchFields: list[str],
    Model,
    customFilters: Optional[List[List[str]]] = None,
    join_options: list = [],
    Schema: type[SQLModel] = None,
    otherFilters=None,
    geo_filters: Optional[List[List[str]]] = None,
    Statement=None,
):
    session = next(get_session())  # get actual Session object
    try:
        # Extract params from query dict
        dateRange = query_params.get("dateRange")
        numberRange = query_params.get("numberRange")
        searchTerm = query_params.get("searchTerm")
        columnFilters = query_params.get("columnFilters")
        stringArrayFilters = query_params.get("stringArrayFilters")
        objectArrayFilters = query_params.get("objectArrayFilters")
        deepFilters = query_params.get("deepFilters")
        page = int(query_params.get("page", 1))
        skip = int(query_params.get("skip", 0))
        limit = int(query_params.get("limit", 10))
        sort = query_params.get("sort")

        filters = {
            "searchTerm": searchTerm,
            "columnFilters": columnFilters,
            "dateRange": dateRange,
            "numberRange": numberRange,
            "customFilters": customFilters,
            "stringArrayFilters": stringArrayFilters,
            "objectArrayFilters": objectArrayFilters,
            "deepFilters": deepFilters,
            "geoFilters": geo_filters,
        }

        result = listop(
            session=session,
            Model=Model,
            searchFields=searchFields,
            filters=filters,
            skip=skip,
            page=page,
            limit=limit,
            join_options=join_options,
            otherFilters=otherFilters,
            Statement=Statement,
            sort=sort,
        )

        # Convert each SQLModel Model instance into a ModelRead Pydantic model
        # Zero matching rows is a valid result for a list endpoint, not an
        # error — data: [] / total: 0 falls through the same success path.
        if not Schema:
            return result

        list_data = [Schema.model_validate(prod) for prod in result["data"]]
        return api_response(
            200,
            f"data found",
            list_data,
            result["total"],
        )
    except DataError as e:
        # This will catch OFFSET/limit errors and send proper API response
        return api_response(
            400,
            f"Invalid pagination values: {str(e).splitlines()[0]}",
        )
    finally:
        # This session is obtained via next(get_session()) rather than
        # FastAPI's Depends() — meaning get_session()'s own `finally:
        # session.close()` never runs on its own here, since a generator
        # advanced with next() only reaches its `yield`, never its cleanup,
        # unless something explicitly drives it to completion. Every one of
        # this app's list endpoints goes through listRecords(), so leaving
        # this uncommented (as it was) leaked one DB connection, permanently
        # "idle in transaction", on every single list request — which is
        # exactly what was piling up and blocking ALTER TABLE migrations.
        session.close()


def serialize_obj(obj):
    """Convert object into JSON-serializable form safely."""
    if isinstance(obj, (str, int, float, bool, type(None))):
        return obj
    elif isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, list):
        return [serialize_obj(o) for o in obj]
    elif isinstance(obj, dict):
        return {k: serialize_obj(v) for k, v in obj.items()}
    elif hasattr(obj, "__dict__"):
        # Only serialize "public" attributes (skip internal SQLAlchemy stuff)
        return {
            k: serialize_obj(v)
            for k, v in obj.__dict__.items()
            if not k.startswith("_") and k != "metadata"
        }
    else:
        # fallback: convert to string
        return str(obj)
