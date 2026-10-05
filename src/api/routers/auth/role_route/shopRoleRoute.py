from fastapi import APIRouter
from sqlmodel import select

from src.api.core.dependencies import (
    GetSession,
    ListQueryParams,
    requireShopAdmin,
    requireShopPermission,
)
from src.api.core.dependencies import GetSession
from src.api.core.operation import listRecords, updateOp
from src.api.core.response import api_response, raiseExceptions
from src.api.core.utility import slugify, uniqueSlugify

from src.api.models.role_model.roleModel import (
    Role,
    Role,
    RoleCreate,
    RoleRead,
    RoleUpdate,
    RoleUpdate,
    ShopRoleCreate,
    ShopRoleUpdate,
)
from src.api.models.role_model.userRoleModel import UserRole


router = APIRouter(prefix="/role", tags=["Shop Role"])


@router.post(
    "/create-shop",
    summary="Create Shop Role",
    description="""
Create a new role for a shop.

### Available Permissions:
- product:create → Create new products
- product:update → Update products
- product:delete → Delete products
- order:view → View orders
- order:update → Update orders
- user:manage → Manage users
""",
)
def create_role(
    request: ShopRoleCreate,
    session: GetSession,
    user=requireShopPermission(["shop:*"]),
):
    # Generate slug

    role_data = request.model_dump()

    print(f"role_data: {user}")
    role_data["user_id"] = user["id"]  # Current user creating the role

    current_shop = user.get("default_shop")

    role_data["shop_id"] = current_shop.id

    role = Role(**role_data)
    session.add(role)
    session.commit()
    session.refresh(role)
    return api_response(201, "Role Created Successfully", RoleRead.model_validate(role))


@router.put("/update-shop/{id}")
def update_role(
    id: int,
    request: ShopRoleUpdate,
    session: GetSession,
    user=requireShopPermission(["shop:*"]),
):
    role = session.exec(
        select(Role).where(Role.id == id, Role.shop_id == user.get("shop").id)
    ).first()
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


@router.get("/read-shop/{id}")
def get_role(
    id: int,
    session: GetSession,
    user=requireShopPermission(["shop:*"]),
):
    role = session.exec(
        select(Role).where(Role.id == id, Role.shop_id == user.get("shop").id)
    ).first()
    raiseExceptions((role, 404, "Role not found"))
    return api_response(200, "Role Found", RoleRead.model_validate(role))


@router.delete("/delete-shop/{id}")
def delete_role(
    id: int,
    session: GetSession,
    user=requireShopPermission(["shop:*"]),
):
    role = session.exec(
        select(Role).where(Role.id == id, Role.shop_id == user.get("shop").id)
    ).first()
    raiseExceptions((role, 404, "Role not found"))

    # Check if role is assigned to any users
    user_roles = session.exec(select(UserRole).where(UserRole.role_id == id)).all()

    if user_roles:
        return api_response(400, "Cannot delete role assigned to users")

    session.delete(role)
    session.commit()
    return api_response(200, f"Role {role.name} deleted successfully")


@router.get("/list-shop", response_model=list[RoleRead])
def list(
    query_params: ListQueryParams,
    user=requireShopPermission(["shop:*"]),
):
    query_params = vars(query_params)
    searchFields = ["name"]

    return listRecords(
        query_params=query_params,
        searchFields=searchFields,
        Model=Role,
        Schema=RoleRead,
        customFilters=[["shop_id", user.get("shop").id]],
    )
