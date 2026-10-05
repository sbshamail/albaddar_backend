from fastapi import APIRouter, Form
from sqlmodel import select

from src.api.core.dependencies import GetSession, requireSignin
from src.api.core.response import api_response, raiseExceptions
from src.api.models.cart_model.cartModel import Cart
from src.api.models.cart_model.cartItemModel import CartItem, CartItemRead
from src.api.models.product_model.ProductVariantModel import ProductVariant

router = APIRouter(prefix="/cart-item", tags=["Cart Item"])


@router.put("/update/{item_id}", response_model=CartItemRead)
def update_cart_item(
    item_id: int,
    user: requireSignin,
    db: GetSession,
    quantity: int = Form(..., ge=1),
):
    item = db.get(CartItem, item_id)
    resp = raiseExceptions((item, 404, "Cart item not found"))
    if resp:
        return resp

    cart = db.get(Cart, item.cart_id)
    if not cart or cart.user_id != user["id"]:
        return api_response(403, "Access denied")

    variant = db.get(ProductVariant, item.product_variant_id)
    if variant and quantity > variant.stock:
        return api_response(400, f"Only {variant.stock} items available")

    item.quantity = quantity
    db.add(item)
    db.commit()
    db.refresh(item)

    return api_response(200, "Cart item updated", CartItemRead.model_validate(item))


@router.delete("/delete/{item_id}")
def delete_cart_item(
    item_id: int,
    user: requireSignin,
    db: GetSession,
):
    item = db.get(CartItem, item_id)
    resp = raiseExceptions((item, 404, "Cart item not found"))
    if resp:
        return resp

    cart = db.get(Cart, item.cart_id)
    if not cart or cart.user_id != user["id"]:
        return api_response(403, "Access denied")

    db.delete(item)
    db.commit()

    return api_response(200, "Cart item removed")
