# My way to code Fastapi Doc Ai For Utility Reusable Function

## in this project we use latest fastapi method, uv package manager, sql model for schemas

## Reusable Utility Methods

//=========================================

## Configuraion

// =======================================

<!-- Db -->

```py
from contextlib import contextmanager
from sqlmodel import (
    Session,
    create_engine,
)

from src.config import DATABASE_URL


engine = create_engine(
    DATABASE_URL,
    echo=True,
    pool_pre_ping=True,  # checks if connection is alive
    pool_recycle=1800,  # refresh stale connections
)


def get_session():
    session = Session(engine)
    try:
        yield session
    finally:
        session.close()

```

<!-- Config Filter -->

```py
import os

from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
SECRET_KEY = os.getenv("SECRET_KEY")
ACCESS_TOKEN_EXPIRE_MINUTES = int(
    os.getenv(
        "ACCESS_TOKEN_EXPIRE_MINUTES",
        30,
    )
)
DOMAIN = os.getenv("DOMAIN", "https://api.ctspk.com")

```

//=========================================

## dependencies

// =======================================

```py
from typing import Annotated, Any, Dict, Optional

from fastapi import Depends, Query
from sqlmodel import Session

from src.api.core.dependencies.query_params import list_query_params
from src.lib.db_con import get_session
from src.api.core.security import (
    is_authenticated,
    require_permission,
    require_signin,
    require_admin,
    verified_user,
)

GetSession = Annotated[Session, Depends(get_session)]

requireSignin = Annotated[dict, Depends(require_signin)]
requireAdmin = Annotated[dict, Depends(require_admin)]
verifiedUser = Annotated[dict, Depends(verified_user)]
isAuthenticated = Annotated[dict | None, Depends(is_authenticated)]
ListQueryParams = Annotated[dict, Depends(list_query_params)]


def requirePermission(*permissions: str):
    return Depends(require_permission(*permissions))

```

//=========================================

## Response

// =======================================

```py
from typing import Any, Optional, Union

from fastapi import HTTPException
from fastapi.encoders import (
    jsonable_encoder,
)
from fastapi.responses import (
    JSONResponse,
)


def api_response(
    code: int,
    detail: str,
    data: Optional[Union[dict, list]] = None,
    total: Optional[int] = None,
):

    content = {
        "success": (1 if code < 300 else 0),
        "detail": detail,
        "data": jsonable_encoder(data),
    }

    if total is not None:
        content["total"] = total

    # Raise error if code >= 400
    if code >= 400:
        raise HTTPException(status_code=code, detail=detail)

    return JSONResponse(
        status_code=code,
        content=content,
    )


def raiseExceptions(*conditions: tuple[Any, int | None, str | None, bool | None]):
    """
    Example usage:
        resp = raiseExceptions(
            (user, 404, "User not found"),
            (is_active, 403, "User is disabled",True),
        )
        if resp: return resp
    """
    for cond in conditions:
        # Unpack with defaults
        condition = cond[0] if len(cond) > 0 else False  # Condition
        code = cond[1] if len(cond) > 1 else 400
        detail = cond[2] if len(cond) > 2 else "error"
        isCond = cond[3] if len(cond) > 3 else False

        if isCond and condition:
            if condition:  # Fail if condition is True
                return api_response(code, detail)
        elif not condition and not isCond:  # Fail if condition is False
            return api_response(code, detail)
    return None  # everything passed

```

//=========================================

## Helpers

// =======================================

```py
from datetime import datetime, timezone
import json
import re
from typing import Any, List
import unicodedata

from fastapi import UploadFile


date_formats = [
    "%d-%m-%Y",
    "%d/%m/%Y",
    "%-d/%-m/%Y",
    "%d/%-m/%Y",
    "%-d/%m/%Y",
    "%d-%-m-%Y",
    "%-d-%m-%Y",
    "%-d-%-m-%Y",
    "%-d-%b-%y",
    "%d-%b-%y",
    "%-d-%b-%Y",
    "%Y-%m-%dT%H:%M:%S.%fZ",
    "%Y-%m-%dT%H:%M:%S.%f",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M",
    "%Y-%m-%dT%H",
    "%Y-%m-%d",
]


def parse_date(date_str: str) -> datetime:
    for fmt in date_formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    raise ValueError(f"Date '{date_str}' is not in a valid UTC format.")


# slug = slugify("ACME Industries Inc.")
# print(slug)  # acme-industries-inc
def slugify(text: str) -> str:
    """
    Convert text into a URL-friendly slug.
    Example: "ACME Industries Inc." -> "acme-industries-inc"
    """
    if not text:
        return ""

    # Normalize unicode (e.g., remove accents like café → cafe)
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")

    # Lowercase
    text = text.lower()

    # Replace non-alphanumeric characters with hyphens
    text = re.sub(r"[^a-z0-9]+", "-", text)

    # Remove leading/trailing hyphens
    text = text.strip("-")

    return text


def uniqueSlugify(session, model, name: str, slug_field: str = "slug") -> str:
    base_slug = slugify(name)
    slug = base_slug
    counter = 1

    while session.query(model).filter(getattr(model, slug_field) == slug).first():
        slug = f"{base_slug}-{counter}"
        counter += 1

    return slug


def Print(data, title="Result"):
    print(f"{title}\n", json.dumps(data, indent=2, default=str))


def parse_list(value):
    """
    Convert a string like "a,b,c" or ["a,b,c"] into ["a","b","c"]
    """
    if not value:
        return []

    if isinstance(value, list):
        # list with one comma-joined string
        if len(value) == 1 and isinstance(value[0], str):
            return [v.strip() for v in value[0].split(",") if v.strip()]
        # already normal list
        return [v.strip() for v in value]

    if isinstance(value, str):
        return [v.strip() for v in value.split(",") if v.strip()]

    return []

```
