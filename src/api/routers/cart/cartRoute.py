from fastapi import APIRouter, Depends
from sqlalchemy.orm import selectinload
from sqlmodel import select
from src.api.models.product_model.ProductVariantModel import ProductVariant
from src.api.models.product_model.productModel import Product

from src.api.core.operation import listRecords
from src.api.core.response import api_response, raiseExceptions
from src.api.core.dependencies import (
    GetSession,
    ListQueryParams,
    requireSignin,
)
from src.api.models.cart_model.cartModel import (
    Cart,
    CartForm,
    CartAndItemsRead,
    CartShopRead,
)
from src.api.models.cart_model.cartItemModel import CartItem

router = APIRouter(prefix="/cart", tags=["Cart"])


def get_shop_variant(session: GetSession, variant_id: int, shop_id: int):
    return session.exec(
        select(ProductVariant)
        .join(Product)
        .where(ProductVariant.id == variant_id, Product.shop_id == shop_id)
    ).first()


@router.post("/create", response_model=CartAndItemsRead)
async def create_cart(
    current_user: requireSignin,
    db: GetSession,
    cart_form: CartForm = Depends(),
):
    # Check existing cart
    cart = db.exec(
        select(Cart).where(
            Cart.user_id == current_user["id"],
            Cart.shop_id == cart_form.shop_id,
        )
    ).first()

    # Create if not exists
    if not cart:
        cart = Cart(
            user_id=current_user["id"],
            shop_id=cart_form.shop_id,
            status=cart_form.status or "active",
        )
        db.add(cart)
        db.flush()

    # Add items
    if cart_form.items:
        for item_data in cart_form.items:
            variant_id = item_data.get("product_variant_id")
            raiseExceptions((variant_id, 404, "Product Variant Id not found"))
            # Get product variant
            variant = get_shop_variant(db, variant_id, cart_form.shop_id)
            raiseExceptions((variant, 404, "Product Variant not found"))
            qty = item_data.get("quantity", 1)

            existing_item = db.exec(
                select(CartItem).where(
                    CartItem.cart_id == cart.id,
                    CartItem.product_variant_id == variant.id,
                )
            ).first()

            if existing_item:

                new_qty = existing_item.quantity + qty

                if new_qty > variant.stock:
                    return api_response(400, f"Only {variant.stock} items available")

                existing_item.quantity = new_qty
                db.add(existing_item)

            else:

                if qty > variant.stock:
                    return api_response(400, f"Only {variant.stock} items available")

                db.add(
                    CartItem(
                        cart_id=cart.id,
                        product_variant_id=variant.id,
                        quantity=qty,
                        product_id=variant.product_id,
                        variant_attributes=variant.attributes,
                    )
                )

        db.flush()

    db.add(cart)
    db.commit()
    db.refresh(cart)

    return api_response(
        200,
        "Cart updated successfully",
        CartAndItemsRead.model_validate(cart),
    )


@router.delete("/delete/{cart_id}")
def delete_cart(
    cart_id: int,
    current_user: requireSignin,
    db: GetSession,
):
    cart = db.get(Cart, cart_id)

    resp = raiseExceptions(
        (cart, 404, "Cart not found"),
        (cart.user_id == current_user["id"], 403, "Access denied", True),
    )
    if resp:
        return resp

    items = db.exec(select(CartItem).where(CartItem.cart_id == cart.id)).all()

    for item in items:
        db.delete(item)

    db.delete(cart)

    db.commit()

    return api_response(
        200,
        "Cart deleted successfully",
    )


@router.get("/read/{id}", response_model=CartAndItemsRead)
def read(
    id: int,
    user: requireSignin,
    session: GetSession,
):
    query = session.exec(
        select(Cart)
        .options(
            selectinload(Cart.items)
            .selectinload(CartItem.variant)
            .selectinload(ProductVariant.product),
        )
        .where(Cart.user_id == user["id"], Cart.id == id)
    ).first()
    raiseExceptions((query, 404, "Cart not found"))
    return api_response(
        200,
        "Cart Found",
        CartAndItemsRead.model_validate(query),
    )


@router.get("/list", response_model=list[CartShopRead])
def list_carts(
    user: requireSignin,
    session: GetSession,
    query_params: ListQueryParams,
):
    query_params = vars(query_params)
    searchFields = ["status"]
    return listRecords(
        query_params=query_params,
        searchFields=searchFields,
        Model=Cart,
        Schema=CartShopRead,
        customFilters=[["user_id", user["id"]]],
    )
