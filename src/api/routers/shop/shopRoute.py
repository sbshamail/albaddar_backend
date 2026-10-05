from urllib import request

from fastapi import APIRouter, Depends
from sqlmodel import select
from starlette.datastructures import UploadFile
from src.api.models.role_model.userRoleModel import UserRole
from src.api.models.role_model.roleModel import Role
from src.api.models.shop_model.ShopChildModel import ShopUser
from src.api.models.userModel import DefaultShopId, User
from src.api.core.utility import slugify, uniqueSlugify
from src.api.core.operation import listRecords, serialize_obj, updateOp
from src.api.core.response import api_response, raiseExceptions
from src.api.core.dependencies import (
    GetSession,
    ListQueryParams,
    requirePermission,
    requireAdmin,
    requireDefaultShop,
    requireShopPermission,
    verifiedUser,
    requireSignin,
)
from src.api.models.shop_model.shopModel import (
    Shop,
    ShopForm,
    ShopRead,
    ShopReadWithOwner,
)
from src.api.core.operation.media import (
    deleteMediaFiles,
    uploadMediaFiles,
    uploadSingleMedia,
)

router = APIRouter(prefix="/shop", tags=["Shop"])


@router.post("/create", response_model=ShopRead)
async def create(
    user: verifiedUser,
    session: GetSession,
    request: ShopForm = Depends(),
):
    user_id = user.get("id")

    request.slug = uniqueSlugify(session, Shop, request.name)

    request.owner_id = user_id

    data = serialize_obj(request)
    await uploadMediaFiles(session, data, request)

    # ✅ Create shop
    shop = Shop(**data)

    session.flush()
    session.add(shop)

    shop_admin_role = session.exec(
        select(Role.id).where(Role.name == "Shop Admin")
    ).first()

    # Assign shop admin role to the user via UserRole
    shop_user_role = UserRole(
        user_id=user.get("id"),
        role_id=shop_admin_role,
        shop_id=shop.id,
    )
    session.add(shop_user_role)

    session.commit()
    session.refresh(shop)

    return api_response(
        201,
        "Shop Updated Successfully",
        ShopRead.model_validate(shop),
    )


@router.put("/update", response_model=ShopRead)
async def update_ride(
    user: verifiedUser,
    session: GetSession,
    request: ShopForm = Depends(),
):
    user_id = user.get("id")
    read = session.exec(select(Shop).where(Shop.owner_id == user_id)).first()

    raiseExceptions((read, 404, "Shop not found"))
    if request.name:
        request.slug = uniqueSlugify(session, Shop, request.name)

    if isinstance(request.cover_image, UploadFile):
        await deleteMediaFiles(session, read.cover_image)
        request.cover_image = await uploadSingleMedia(request.cover_image, session)

    if isinstance(request.logo, UploadFile):
        await deleteMediaFiles(session, read.logo)
        request.logo = await uploadSingleMedia(request.logo, session)

    # ✅ update shop
    update_data = updateOp(read, request, session)

    session.commit()
    session.refresh(update_data)

    return api_response(
        200,
        "Shop Updated Successfully",
        ShopRead.model_validate(update_data),
    )


@router.get("/read/owner", response_model=ShopRead)
def findOne(
    session: GetSession,
    user: verifiedUser,
):

    user_id = user.get("id")
    statement = select(Shop).where(Shop.owner_id == user_id)
    read = session.exec(statement).first()  # Like findById

    raiseExceptions((read, 404, "Shop not found"))
    data = ShopRead.model_validate(read)

    return api_response(200, "Shop Found", data)


@router.get("/read/default", response_model=ShopReadWithOwner)
def findOne(
    session: GetSession,
    user: requireDefaultShop,
):

    default_shop = user.get("default_shop")
    shop_id = default_shop["id"] if isinstance(default_shop, dict) else default_shop.id
    statement = select(Shop).where(Shop.id == shop_id)
    read = session.exec(statement).first()  # Like findById

    raiseExceptions((read, 404, "Shop not found"))
    data = ShopReadWithOwner.model_validate(read)

    return api_response(200, "Shop Found", data)


@router.get("/read/{id}", response_model=ShopReadWithOwner)
def findOne(
    id: int,
    session: GetSession,
):

    read = session.get(Shop, id)  # Like findById

    raiseExceptions((read, 404, "Shop not found"))
    data = ShopReadWithOwner.model_validate(read)

    if not data.owner or not data.owner.verified:
        return api_response(400, "User Not Verified")

    return api_response(200, "Shop Found", data)


@router.delete("/delete/{id}")
async def delete_role(
    id: int,
    session: GetSession,
    user=requireShopPermission("shop_delete"),
):
    shop = session.get(Shop, id)

    raiseExceptions((shop, 404, "Shop Data not found"))
    db_user = session.get(User, shop.owner_id)
    if db_user:
        db_user.default_shop_id = None
        session.add(db_user)

    await deleteMediaFiles(session, shop.cover_image, shop.logo)

    session.delete(shop)
    session.commit()
    return api_response(200, f"The Shop {shop.name} deleted")


@router.get("/list", response_model=list[ShopReadWithOwner])
def list(query_params: ListQueryParams):
    query_params = vars(query_params)
    searchFields = ["name", "slug", "description"]

    return listRecords(
        query_params=query_params,
        searchFields=searchFields,
        Model=Shop,
        Schema=ShopReadWithOwner,
    )


@router.post("/set-default-shop")
def set_default_shop(
    request: DefaultShopId,
    session: GetSession,
    user: requireSignin,
):
    # ✅ check membership
    membership = session.exec(
        select(ShopUser.id).where(
            ShopUser.user_id == user["id"],
            ShopUser.shop_id == request.shop_id,
        )
    ).first()
    shop = session.exec(
        select(Shop.id).where(Shop.owner_id == user["id"], Shop.id == request.shop_id)
    ).first()

    if not membership and not shop:
        return api_response(403, "You are not part of this shop")

    # ✅ update user
    db_user = session.get(User, user["id"])
    db_user.default_shop_id = request.shop_id

    session.add(db_user)
    session.commit()
    session.refresh(db_user)

    return api_response(200, "Default shop updated successfully")
