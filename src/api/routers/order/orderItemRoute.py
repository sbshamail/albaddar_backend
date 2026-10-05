from fastapi import APIRouter
from sqlmodel import select

from src.api.models.order_model.orderModel import Order
from src.api.core.dependencies import (
    GetSession,
    ListQueryParams,
    requireDefaultShop,
    requireShopPermission,
)
from src.api.core.operation import listRecords
from src.api.core.response import api_response, raiseExceptions
from src.api.models.order_model.orderItemModel import (
    OrderItem,
    OrderItemsRead,
    OrderItemStatusUpdate,
)
from sqlalchemy.orm import joinedload, selectinload

router = APIRouter(prefix="/order-item", tags=["Order Item"])


LIST_JOIN_OPTIONS = [
    # selectinload only works on relationships, and the query root here is
    # OrderItem, not Order — selectinload(Order.shipping_address) was
    # invalid on both counts (shipping_address is a plain JSON column, not
    # a relationship, and it isn't reachable directly from an OrderItem
    # query anyway). Go through OrderItem's actual `order` relationship,
    # and load_only fetches just that one column instead of the whole row.
    selectinload(OrderItem.order).load_only(Order.shipping_address),
]


@router.get("/list", response_model=list[OrderItemsRead])
def list_order_items(query_params: ListQueryParams, user: requireDefaultShop):
    shop_id = user.get("default_shop_id")
    query_params = vars(query_params)
    return listRecords(
        query_params=query_params,
        searchFields=["product_name", "status"],
        Model=OrderItem,
        Schema=OrderItemsRead,
        customFilters=[["shop_id", shop_id]],
        join_options=LIST_JOIN_OPTIONS,
    )


@router.get("/read/{id}", response_model=OrderItemsRead)
def read_order_item(id: int, session: GetSession, user: requireDefaultShop):
    shop_id = user.get("default_shop_id")
    item = session.exec(
        select(OrderItem)
        .options(*LIST_JOIN_OPTIONS)
        .where(OrderItem.id == id, OrderItem.shop_id == shop_id)
    ).first()
    raiseExceptions((item, 404, "Order item not found"))
    return api_response(200, "Order item found", OrderItemsRead.model_validate(item))


@router.patch("/update-status/{id}", response_model=OrderItemsRead)
def update_order_item_status(
    id: int,
    request: OrderItemStatusUpdate,
    session: GetSession,
    user=requireShopPermission("order:update"),
):
    shop_id = user.get("default_shop_id")
    item = session.exec(
        select(OrderItem).where(OrderItem.id == id, OrderItem.shop_id == shop_id)
    ).first()
    raiseExceptions((item, 404, "Order item not found"))
    item.status = request.status.value
    session.add(item)
    session.commit()
    session.refresh(item)
    return api_response(
        200, "Order item status updated", OrderItemsRead.model_validate(item)
    )
