from fastapi import APIRouter
from sqlmodel import select

from src.api.models.role_model.roleModel import Role
from src.api.core.security import invalidate_user_session
from src.api.core.operation import listRecords
from src.api.core.response import api_response, raiseExceptions
from src.api.core.dependencies import (
    GetSession,
    ListQueryParams,
    requirePermission,
    requireAdmin,
)
from src.api.models.role_model.userRoleModel import (
    UserRole,
    UserRoleCreate,
    UserRoleRead,
)

router = APIRouter(prefix="/user-role", tags=["User Role"])


@router.post("/create")
def create_role(
    request: UserRoleCreate,
    session: GetSession,
    user=requirePermission(["role_create"]),
):
    role = session.get(Role, request.role_id)
    raiseExceptions((role, 404, "Role not found"))

    user_role = UserRole(
        **request.model_dump()
    )  # Similar to new Role(req.body) in Mongoose

    session.add(user_role)
    session.commit()
    session.refresh(user_role)
    invalidate_user_session(user_role.user_id)
    return api_response(
        201, "Role Created Successfully", UserRoleRead.model_validate(user_role)
    )


@router.get("/read/{id}")
def get_role(id: int, session: GetSession, user=requirePermission(["role_view"])):
    role = session.get(UserRole, id)
    raiseExceptions((role, 404, "Role not found"))
    return api_response(200, "Role Found", UserRoleRead.model_validate(role))


@router.delete("/delete/{id}")
def delete_role(
    id: int,
    session: GetSession,
    user=requirePermission("role_delete"),
):
    role = session.get(UserRole, id)
    raiseExceptions((role, 404, "User Role not found"))

    user_id = role.user_id
    session.delete(role)
    session.commit()
    invalidate_user_session(user_id)
    return api_response(200, f"Role {role.id} deleted successfully")


@router.get("/list", response_model=list[UserRoleRead])
def list(
    query_params: ListQueryParams,
    user=requirePermission("role_view"),
):
    query_params = vars(query_params)
    searchFields = ["name"]

    return listRecords(
        query_params=query_params,
        searchFields=searchFields,
        Model=UserRole,
        Schema=UserRoleRead,
    )
