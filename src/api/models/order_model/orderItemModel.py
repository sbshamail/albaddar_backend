from enum import Enum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Column, JSON
from sqlmodel import Field, Relationship, SQLModel

from src.api.models.mediaModel import MediaRead
from src.api.models.baseModel import TimeStampReadModel, TimeStampedModel

if TYPE_CHECKING:
    from src.api.models import Order


class OrderItemStatus(str, Enum):
    pending = "pending"
    processing = "processing"
    shipped = "shipped"
    delivered = "delivered"
    cancelled = "cancelled"


class OrderItem(TimeStampedModel, table=True):
    __tablename__ = "order_items"

    id: Optional[int] = Field(default=None, primary_key=True)

    order_id: int = Field(
        foreign_key="orders.id",
        index=True,
    )

    shop_id: int = Field(
        foreign_key="shops.id",
        index=True,
    )

    product_id: int

    product_variant_id: int | None = None

    product_name: str

    # Fulfillment status lives per line item (not on the parent Order) since
    # a single order can span multiple shops, and each shop only controls
    # fulfillment of its own items.
    status: str = Field(default=OrderItemStatus.pending.value, index=True)

    quantity: int

    price: float
    actual_price: float

    # Snapshot of the variant's weight (kg) at order time — the variant
    # itself can change/be deleted later, this is what shipping was
    # actually calculated against for this order.
    weight: float | None = None

    # Snapshot of the variant's attributes dict at order time (matches
    # ProductVariant.attributes / CartItem.variant_attributes, both dicts).
    variant_attributes: dict | None = Field(
        default=None,
        sa_column=Column(JSON),
    )

    image: dict | None = Field(
        default=None,
        sa_column=Column(JSON),
    )

    # relationships
    order: "Order" = Relationship(back_populates="items")

    @property
    def shipping_address(self) -> Optional[dict]:
        return self.order.shipping_address if self.order else None


class OrderItemsRead(SQLModel, TimeStampReadModel):
    id: int
    order_id: int
    product_id: Optional[int] = None
    shop_id: Optional[int] = None
    product_variant_id: Optional[int] = None
    product_name: str
    status: str
    variant_attributes: Optional[dict] = None
    price: float
    actual_price: Optional[float] = None
    weight: Optional[float] = None
    quantity: int
    image: Optional[MediaRead] = None
    shipping_address: Optional[dict] = None

    class Config:
        from_attributes = True


class OrderItemStatusUpdate(SQLModel):
    status: OrderItemStatus
