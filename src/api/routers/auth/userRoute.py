from typing import Optional
from fastapi import APIRouter, Depends, Query, Request
from sqlmodel import select
from starlette.datastructures import UploadFile as StarletteUploadFile

from src.api.models.role_model.userRoleModel import UserRole
from sqlalchemy.orm import selectinload

from src.api.core.operation import listop
from src.api.core.operation.media import delete_media_items, entryMedia, uploadImage
from src.api.core.security import (
    hash_password,
    invalidate_user_session,
    require_signin_user,
)
from src.api.routers.auth.function import exist_verified_email, send_verification_email
from src.api.core import updateOp, requireSignin
from src.api.core.dependencies import GetSession, requireAdmin
from src.api.core.response import api_response, raiseExceptions

from src.api.models.userModel import (
    UpdateUserByAdmin,
    User,
    UserRead,
    UserUpdateForm,
)

router = APIRouter(prefix="/user", tags=["user"])


@router.get("/me")
def get_me(user_data=Depends(require_signin_user)):
    return user_data


@router.get("/read", response_model=UserRead)
def get_user(
    user: requireSignin,
    session: GetSession,
):
    user_id = user.get("id")
    db_user = session.get(User, user_id)  # Like findById
    raiseExceptions((db_user, 400, "User not found"))
    user_read = UserRead.model_validate(db_user)
    return api_response(200, "User Found", user_read)


@router.get("/read/{id}", response_model=UserRead)
def get_user(
    id: int,
    session: GetSession,
):
    user_id = id
    db_user = session.get(User, user_id)  # Like findById
    raiseExceptions((db_user, 400, "User not found"))
    user_read = UserRead.model_validate(db_user)
    return api_response(200, "User Found", user_read)


@router.put("/update", response_model=UserRead)
async def update_user(
    user: requireSignin,
    session: GetSession,
    request: UserUpdateForm = Depends(),
):
    user_id = user.get("id")
    db_user = session.get(User, user_id)  # Like findById
    raiseExceptions((db_user, 404, "User not found"))
    # 🔥 Validate password match manually
    if request.password and request.password != request.confirm_password:
        return api_response(400, "Passwords do not match")

    if isinstance(request.image, StarletteUploadFile):
        if db_user.image:
            delete_media_items(session, filenames=[db_user.image["filename"]])

        files = [request.image]
        saved_files = await uploadImage(files, thumbnail=False)

        records = entryMedia(session, saved_files)

        request.image = records[0].model_dump(
            include={"id", "filename", "original", "media_type"}
        )

    else:
        if hasattr(request, "image"):
            delattr(request, "image")

    if (
        request.email
        and request.email != user.get("email")
        and exist_verified_email(session, request.email)
    ):
        return api_response(
            400,
            "This email is already registered and verified.",
        )

    updated_user = updateOp(db_user, request, session)
    # Token version update
    updated_user.token_version = (
        db_user.token_version + 1 if db_user.token_version else 1
    )

    if request.password:
        updated_user.password = hash_password(request.password)
    # ✅ Handle password hash only if password provided

    if request.phone and request.phone != user.get("phone"):
        updated_user.verified = False
    if request.email and request.email != user.get("email"):
        updated_user.email_verified = False
        send_verification_email(db_user)

    session.commit()
    session.refresh(updated_user)
    invalidate_user_session(user_id)
    return api_response(
        200, "User Update Successfully", UserRead.model_validate(updated_user)
    )


@router.put("/update_by_admin/{user_id}", response_model=UserRead)
def update_user(
    user: requireAdmin,
    request: UpdateUserByAdmin,
    user_id: int,
    session: GetSession,
):
    if user_id is None:
        raise api_response(400, "User ID is required")
    db_user = session.get(User, user_id)  # Like findById
    raiseExceptions((db_user, 404, "User not found"))
    updated_user = updateOp(db_user, request, session)
    # ✅ Handle password hash only if password provided
    if request.password:
        updated_user.password = hash_password(request.password)

    session.commit()
    session.refresh(db_user)
    invalidate_user_session(user_id)
    return api_response(200, "User Found", UserRead.model_validate(db_user))


# ✅ READ ALL
@router.get("/list", response_model=list[UserRead])  # no response_model
def list_users(
    user: requireAdmin,
    session: GetSession,
    dateRange: Optional[
        str
    ] = None,  # JSON string like '["created_at", "01-01-2025", "01-12-2025"]'
    numberRange: Optional[str] = None,  # JSON string like '["amount", "0", "100000"]'
    searchTerm: str = None,
    columnFilters: Optional[str] = Query(
        None
    ),  # e.g. '[["name","car"],["description","product"]]'
    objectArrayFilters: Optional[str] = Query(
        None,
        description='Example: [[ "attributes", ["name","color"], ["values", ["value","Red"]]]]',
    ),
    deepFilters: Optional[str] = Query(
        None,
        description="""
        Format: [["field.path", value or [values]]]. 
        Supports string (exact/like), boolean, number, JSON array (permissions), 
        and deep relations. 
        Example: [["user_roles.role.name","admin"],["users.is_active",true],["user_roles.role.permissions",["all","user-create"]]]
    """,
    ),
    page: int = None,
    skip: int = 0,
    limit: int = Query(10, ge=1, le=200),
):

    filters = {
        "searchTerm": searchTerm,
        "columnFilters": columnFilters,
        "dateRange": dateRange,
        "numberRange": numberRange,
        "objectArrayFilters": objectArrayFilters,
        "deepFilters": deepFilters,
        # "customFilters": customFilters,
    }

    searchFields = ["name", "phone", "email"]
    result = listop(
        session=session,
        Model=User,
        searchFields=searchFields,
        filters=filters,
        skip=skip,
        page=page,
        limit=limit,
    )
    if not result["data"]:
        return api_response(404, "No User found")
    data = [UserRead.model_validate(prod) for prod in result["data"]]

    return api_response(
        200,
        "User found",
        data,
        result["total"],
    )
