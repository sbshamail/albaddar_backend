from fastapi import APIRouter, Depends
from starlette.datastructures import UploadFile as FormUploadFile
from sqlmodel import delete, func, select
from src.api.models.cart_model.cartItemModel import CartItem
from src.api.core.operation import listRecords, serialize_obj, updateOp
from src.api.core.response import api_response, raiseExceptions
from src.api.core.dependencies import (
    GetSession,
    ListQueryParams,
    requireShopPermission,
)
from src.api.models.product_model.ProductVariantModel import (
    ProductVariant,
    ProductVariantRead,
    ProductVariantForm,
)
from src.api.models.product_model.productModel import Product


from src.api.core.operation.media import (
    deleteMediaFiles,
    uploadMediaFiles,
    uploadSingleMedia,
)

router = APIRouter(prefix="/product-variant", tags=["Product Variant"])


@router.post("/create/{product_id}", response_model=ProductVariantRead)
async def create_product(
    session: GetSession,
    product_id: int,
    user=requireShopPermission(["product:create"]),
    request: ProductVariantForm = Depends(),
):
    shop_id = user.get("default_shop_id")
    product = session.exec(
        select(Product).where(Product.id == product_id, Product.shop_id == shop_id)
    ).first()
    raiseExceptions((product, 404, "Product not found"))

    # ==========================
    # Prepare data
    # ==========================
    request.product_id = product_id

    data = serialize_obj(request)

    await uploadMediaFiles(session, data, request, shop_id=shop_id)

    # ==========================
    # Add product Variant
    # ==========================
    productVariant = ProductVariant(**data)

    session.add(productVariant)
    session.commit()
    session.refresh(productVariant)

    return api_response(
        201,
        "Product Variant Add Successfully",
        ProductVariantRead.model_validate(productVariant),
    )


@router.post("/update/{id}", response_model=ProductVariantRead)
async def update_product_variant(
    id: int,
    session: GetSession,
    user=requireShopPermission(["product:create", "product:update"]),
    request: ProductVariantForm = Depends(),
):

    shop_id = user.get("default_shop_id")
    productVariant = session.exec(
        select(ProductVariant)
        .join(Product)
        .where(ProductVariant.id == id, Product.shop_id == shop_id)
    ).first()
    raiseExceptions((productVariant, 404, "Product Variant not found"))

    if isinstance(request.image, FormUploadFile):
        await deleteMediaFiles(session, productVariant.image)
        request.image = await uploadSingleMedia(
            request.image, session, shop_id=shop_id
        )

    # ==========================
    # UPDATE
    # ==========================

    updated_product = updateOp(productVariant, request, session)

    session.commit()
    session.refresh(updated_product)

    return api_response(
        200,
        "Product Variant Updated Successfully",
        ProductVariantRead.model_validate(updated_product),
    )


@router.delete("/delete/{id}")
async def delete_product_variant(
    id: int,
    session: GetSession,
    user=requireShopPermission(["product:delete"]),
):
    shop_id = user.get("default_shop_id")
    productVariant = session.exec(
        select(ProductVariant)
        .join(Product)
        .where(ProductVariant.id == id, Product.shop_id == shop_id)
    ).first()
    raiseExceptions((productVariant, 404, "Product Variant not found"))

    variant_count = session.exec(
        select(func.count()).where(ProductVariant.product_id == productVariant.product_id)
    ).one()
    if variant_count <= 1:
        return api_response(
            400,
            "This is the only variant left. Delete the whole product instead.",
        )

    # Deleting a variant that's still in someone's cart violates the
    # cart_items -> product_variants foreign key, so drop those rows first.
    session.exec(delete(CartItem).where(CartItem.product_variant_id == id))

    if productVariant.image:
        await deleteMediaFiles(session, productVariant.image)

    session.delete(productVariant)
    session.commit()

    return api_response(200, "Product Variant deleted successfully")


@router.get("/read/{id}", response_model=ProductVariantRead)
def read_product_variant(
    id: int,
    session: GetSession,
):
    productVariant = session.get(ProductVariant, id)
    raiseExceptions((productVariant, 404, "Product Variant not found"))

    return api_response(
        200,
        "Product Variant Found",
        ProductVariantRead.model_validate(productVariant),
    )


@router.get("/list", response_model=list[ProductVariantRead])
def list_product_variants(
    query_params: ListQueryParams,
):
    query_params = vars(query_params)
    searchFields = ["sku"]

    return listRecords(
        query_params=query_params,
        searchFields=searchFields,
        Model=ProductVariant,
        Schema=ProductVariantRead,
    )


@router.get("/list/{product_id}", response_model=list[ProductVariantRead])
def list_product_variants_by_product(
    product_id: int,
    query_params: ListQueryParams,
    session: GetSession,
):
    product = session.get(Product, product_id)
    raiseExceptions((product, 404, "Product not found"))

    query_params = vars(query_params)
    searchFields = ["sku"]

    def otherFilters(statement, Model):
        return statement.where(Model.product_id == product_id)

    return listRecords(
        query_params=query_params,
        searchFields=searchFields,
        Model=ProductVariant,
        Schema=ProductVariantRead,
        otherFilters=otherFilters,
    )
