from fastapi import APIRouter

from sqlmodel import select
from src.api.core.operation import listRecords, updateOp
from src.api.core.response import api_response, raiseExceptions
from src.api.core.dependencies import (
    GetSession,
    ListQueryParams,
    requirePermission,
    requireAdmin,
)
from src.api.models.role_model.roleModel import Role, RoleCreate, RoleRead, RoleUpdate
from src.api.models.role_model.userRoleModel import UserRole
from src.api.core.utility import slugify, uniqueSlugify

router = APIRouter(prefix="/role", tags=["Role"])


@router.post("/create")
def create_role(
    request: RoleCreate,
    session: GetSession,
    user=requirePermission(["role:create"]),
):
    # Generate slug
    slug = uniqueSlugify(session, Role, request.name)

    role_data = request.model_dump()
    role_data["slug"] = slug
    print(f"role_data: {user}")
    role_data["user_id"] = user["id"]  # Current user creating the role

    role = Role(**role_data)
    session.add(role)
    session.commit()
    session.refresh(role)
    return api_response(201, "Role Created Successfully", RoleRead.model_validate(role))


@router.put("/update/{id}")
def update_role(
    id: int,
    request: RoleUpdate,
    session: GetSession,
    user=requirePermission(["role:create"]),
):
    role = session.get(Role, id)
    raiseExceptions((role, 404, "Role not found"))

    # Check name uniqueness if name is being updated
    if "name" in role and role["name"] != role.name:
        existing_role = session.exec(
            select(Role).where(Role.name == role["name"])
        ).first()
        if existing_role:
            return api_response(400, "Role name already exists")

    updated_user = updateOp(role, request, session)

    session.commit()
    session.refresh(updated_user)
    return api_response(200, "Role Updated Successfully", RoleRead.model_validate(role))


@router.get("/read/{id}")
def get_role(id: int, session: GetSession, user=requirePermission(["role_view"])):
    role = session.get(Role, id)
    raiseExceptions((role, 404, "Role not found"))
    return api_response(200, "Role Found", RoleRead.model_validate(role))


@router.delete("/delete/{id}")
def delete_role(
    id: int,
    session: GetSession,
    user=requirePermission("role:delete"),
):
    role = session.get(Role, id)
    raiseExceptions((role, 404, "Role not found"))

    # Check if role is assigned to any users
    user_roles = session.exec(select(UserRole).where(UserRole.role_id == id)).all()

    if user_roles:
        return api_response(400, "Cannot delete role assigned to users")

    session.delete(role)
    session.commit()
    return api_response(200, f"Role {role.name} deleted successfully")


@router.get("/list", response_model=list[RoleRead])
def list(user: requireAdmin, query_params: ListQueryParams):
    query_params = vars(query_params)
    searchFields = ["name"]

    return listRecords(
        query_params=query_params,
        searchFields=searchFields,
        Model=Role,
        Schema=RoleRead,
    )
