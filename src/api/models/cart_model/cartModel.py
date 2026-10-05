from typing import TYPE_CHECKING, Optional, List

from fastapi import Form

from sqlmodel import Field, Relationship, SQLModel, UniqueConstraint

from src.api.models.cart_model.cartItemModel import CartItemRead
from src.api.models.utils import clean_json, to_int
from src.api.models.baseModel import TimeStampReadModel, TimeStampedModel

if TYPE_CHECKING:
    from src.api.models import User, Shop
    from src.api.models.cart_model.cartItemModel import CartItem


class Cart(TimeStampedModel, table=True):
    __tablename__ = "carts"

    id: Optional[int] = Field(default=None, primary_key=True)

    # Relations
    user_id: Optional[int] = Field(default=None, foreign_key="users.id", index=True)
    shop_id: Optional[int] = Field(
        default=None,
        foreign_key="shops.id",
        index=True,
    )

    # Status
    status: str = Field(default="active", index=True)

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "shop_id",
            "status",
            name="uq_cart_user_shop_status",
        ),
    )

    # Relationships
    items: List["CartItem"] = Relationship(
        back_populates="cart",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
    user: Optional["User"] = Relationship()
    shop: Optional["Shop"] = Relationship()

    @property
    def total_items(self) -> int:
        return sum(item.quantity or 0 for item in self.items)

    @property
    def subtotal(self) -> float:
        return sum((item.price or 0) * (item.quantity or 0) for item in self.items)


class CartRead(SQLModel, TimeStampReadModel):
    id: int
    user_id: Optional[int] = None
    shop_id: Optional[int] = None
    subtotal: float
    total_items: int
    status: str


class CartAndItemsRead(CartRead):
    items: List[CartItemRead] = []


class ShopReadCart(SQLModel):
    id: Optional[int]
    name: str
    is_active: bool


class CartShopRead(CartAndItemsRead):
    shop: Optional[ShopReadCart] = None

    class Config:
        from_attributes = True


class CartForm:
    def __init__(
        self,
        shop_id: Optional[int] = Form(None),
        status: Optional[str] = Form("active"),
        items: Optional[str] = Form(
            None,
            description="JSON array of cart items.",
            examples=['[{"product_variant_id": 1, "quantity": 2}]'],
        ),
    ):

        self.shop_id = to_int(shop_id)
        self.status = status or "active"
        self.items = clean_json(items) if items is not None else []
