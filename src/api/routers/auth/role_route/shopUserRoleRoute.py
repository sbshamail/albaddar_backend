from fastapi import APIRouter
from sqlmodel import select

from src.api.models.userModel import User
from src.api.models.role_model.roleModel import Role
from src.api.core.security import invalidate_user_session
from src.api.core.operation import listRecords
from src.api.core.response import api_response, raiseExceptions
from src.api.core.dependencies import (
    GetSession,
    ListQueryParams,
    requireShopPermission,
    requireAdmin,
)
from src.api.models.role_model.userRoleModel import (
    UserRole,
    UserRoleCreate,
    UserRoleRead,
)

router = APIRouter(prefix="/user-role", tags=["Shop User Role"])


def getShopId(user):
    default_shop = user.get("default_shop")
    shop_id = default_shop["id"] if isinstance(default_shop, dict) else default_shop.id
    return shop_id


@router.post("/create-shop")
def create_role(
    request: UserRoleCreate,
    session: GetSession,
    user=requireShopPermission(["role_create"]),
):
    shop_id = getShopId(user)
    role = session.exec(
        select(Role).where(Role.id == request.role_id, Role.shop_id == shop_id)
    ).first()
    raiseExceptions((role, 404, "Role not found"))
    # ✅ Check target user exists
    db_user = session.get(User, request.user_id)
    raiseExceptions((db_user, 404, "User not found"))

    user_role = UserRole(
        user_id=request.user_id,
        role_id=request.role_id,
        shop_id=shop_id,
    )  # Similar to new Role(req.body) in Mongoose

    session.add(user_role)
    session.commit()
    session.refresh(user_role)
    invalidate_user_session(user_role.user_id)
    return api_response(
        201, "Role Created Successfully", UserRoleRead.model_validate(user_role)
    )


@router.get("/read-shop/{id}")
def get_role(id: int, session: GetSession, user=requireShopPermission(["role_view"])):
    shop_id = getShopId(user)
    role = session.exec(
        select(UserRole).where(UserRole.id == id, UserRole.shop_id == shop_id)
    ).first()
    raiseExceptions((role, 404, "Role not found"))
    return api_response(200, "Role Found", UserRoleRead.model_validate(role))


@router.delete("/delete-shop/{id}")
def delete_role(
    id: int,
    session: GetSession,
    user=requireShopPermission(["role_delete"]),
):
    shop_id = getShopId(user)
    role = session.exec(
        select(UserRole).where(UserRole.id == id, UserRole.shop_id == shop_id)
    ).first()
    raiseExceptions((role, 404, "User Role not found"))

    user_id = role.user_id
    session.delete(role)
    session.commit()
    invalidate_user_session(user_id)
    return api_response(200, f"Role {role.id} deleted successfully")


@router.get("/list-shop", response_model=list[UserRoleRead])
def list(
    query_params: ListQueryParams,
    user=requireShopPermission(["role_view"]),
):
    query_params = vars(query_params)
    searchFields = ["name"]

    return listRecords(
        query_params=query_params,
        searchFields=searchFields,
        Model=UserRole,
        Schema=UserRoleRead,
        customFilters=[["shop_id", getShopId(user)]],
    )
