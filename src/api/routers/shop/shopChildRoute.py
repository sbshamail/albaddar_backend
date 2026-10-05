from typing import List

from fastapi import APIRouter, Depends
from sqlmodel import select
from starlette.datastructures import UploadFile
from src.api.models.shop_model.shopModel import Shop, ShopForm
from src.api.core.utility import uniqueSlugify
from src.api.core.operation import listRecords, updateOp
from src.api.core.response import api_response, raiseExceptions
from src.api.core.dependencies import (
    GetSession,
    ListQueryParams,
    require_shop_permission,
    requireShopAdmin,
)
from src.api.models.shop_model.ShopChildModel import (
    ShopUser,
    ShopUserRead,
    ShopUserCreate,
    ShopUserReadWithUser,
    ShopUserUpdate,
)
from src.api.models.userModel import User

router = APIRouter(prefix="/shop-users", tags=["Shop Users for Owner"])


@router.post("/create", response_model=ShopUserRead)
async def create(
    session: GetSession,
    request: ShopUserCreate,
    user: requireShopAdmin,
):
    # ✅ Get current shop from logged-in user
    current_shop = user.get("shop")

    print("Current Shop:", current_shop)  # Debugging line]

    if not current_shop:
        return api_response(400, "No active shop selected")

    shop_id = current_shop.id

    # ✅ Find user by email
    db_user = session.exec(select(User).where(User.email == request.email)).first()

    if not db_user:
        return api_response(404, "User not found")

    if db_user.id == user.get("id"):
        return api_response(400, "You cannot add yourself to the shop")

    # ✅ Create shop User
    # ✅ Assign shop_id + user_id
    shop_user = ShopUser(
        user_id=db_user.id,
        shop_id=shop_id,
        is_active=True,
    )

    session.add(shop_user)
    session.commit()
    session.refresh(shop_user)

    return api_response(
        201,
        "Shop Member Added Successfully",
        ShopUserReadWithUser.model_validate(shop_user),
    )


@router.put("/update/{user_id}", response_model=ShopUserRead)
async def update_ride(
    user_id: int,
    session: GetSession,
    request: ShopUserUpdate,
    user: requireShopAdmin,
):

    read = session.exec(
        select(ShopUser).where(
            ShopUser.user_id == user_id, ShopUser.shop_id == user.get("shop", {}).id
        )
    ).first()
    raiseExceptions((read, 404, "Shop User not found"))

    # ✅ update shop
    update_data = updateOp(read, request, session)

    session.commit()
    session.refresh(update_data)

    return api_response(
        200,
        "Shop Member Updated Successfully",
        ShopUserRead.model_validate(update_data),
    )


@router.get("/read/{user_id}/{shop_id}", response_model=ShopUserReadWithUser)
def findOne(
    user_id: int,
    shop_id: int,
    session: GetSession,
):

    read = session.exec(
        select(ShopUser).where(ShopUser.user_id == user_id, ShopUser.shop_id == shop_id)
    ).first()

    raiseExceptions((read, 404, "Shop User not found"))
    data = ShopUserReadWithUser.model_validate(read)

    return api_response(200, "Shop User Found", data)


@router.delete("/delete/{user_id}")
def findOne(
    user_id: int,
    session: GetSession,
    user: requireShopAdmin,
):

    shop_user = session.exec(
        select(ShopUser).where(
            ShopUser.user_id == user_id, ShopUser.shop_id == user.get("shop", {}).id
        )
    ).first()

    raiseExceptions((shop_user, 404, "Shop User not found"))
    session.delete(shop_user)
    session.commit()

    return api_response(200, f"Member {shop_user.user_id} deleted")


@router.delete("/delete-many")
def delete_many(
    user_ids: List[int],
    shop_ids: List[int],
    session: GetSession,
    user: requireShopAdmin,
):
    shop_users = session.exec(
        select(ShopUser).where(
            ShopUser.user_id.in_(user_ids), ShopUser.shop_id.in_(shop_ids)
        )
    ).all()

    if not shop_users:
        return api_response(404, "Shop Users not found")

    session.delete(shop_users)
    session.commit()

    return api_response(
        200,
        f"Deleted {len(shop_users)} shop users",
        [ShopUserReadWithUser.model_validate(su) for su in shop_users],
    )


@router.get("/list", response_model=list[ShopUserReadWithUser])
def list(
    query_params: ListQueryParams,
    user: requireShopAdmin,
):
    query_params = vars(query_params)
    searchFields = ["user.full_name", "user.email", "shop.name"]
    shop_id = user.get("shop", {}).id
    print("Shop ID for listing shop users:", shop_id)  # Debugging line

    return listRecords(
        query_params=query_params,
        searchFields=searchFields,
        Model=ShopUser,
        Schema=ShopUserReadWithUser,
        customFilters=[["shop_id", shop_id]],
    )
