from fastapi import APIRouter
from sqlmodel import func, select

from src.api.core.dependencies import GetSession, requireDefaultShop
from src.api.core.response import api_response
from src.api.models.category_model import Category
from src.api.models.order_model.orderItemModel import OrderItem, OrderItemStatus
from src.api.models.product_model.productModel import Product

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/counts")
def get_counts(session: GetSession, user: requireDefaultShop):
    """Sidebar badge counts. One round trip instead of three separate list
    calls — a plain COUNT(*) per resource, no rows fetched."""
    shop_id = user.get("default_shop_id")

    products = session.exec(
        select(func.count(Product.id)).where(Product.shop_id == shop_id)
    ).one()

    # "Orders" badge = actionable count, not a forever-growing total.
    pending_orders = session.exec(
        select(func.count(OrderItem.id)).where(
            OrderItem.shop_id == shop_id,
            OrderItem.status == OrderItemStatus.pending.value,
        )
    ).one()

    # Categories aren't shop-scoped (same tree for every shop, like /category/list).
    categories = session.exec(select(func.count(Category.id))).one()

    return api_response(
        200,
        "Counts found",
        {
            "products": products,
            "orders": pending_orders,
            "categories": categories,
        },
    )
