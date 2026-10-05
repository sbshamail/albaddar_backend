from typing import TYPE_CHECKING, Optional, List, Union

from fastapi import File, Form, UploadFile
from sqlalchemy import Column, JSON
from sqlmodel import Field, Relationship, SQLModel

from src.api.models.mediaModel import MediaRead
from src.api.models.utils import clean_json, to_int
from src.api.models.baseModel import TimeStampReadModel, TimeStampedModel

if TYPE_CHECKING:
    from src.api.models import Cart, Product, ProductVariant


class CartItem(TimeStampedModel, table=True):
    __tablename__ = "cart_items"

    id: Optional[int] = Field(default=None, primary_key=True)

    cart_id: int = Field(foreign_key="carts.id", index=True)
    product_id: Optional[int] = Field(
        default=None, foreign_key="products.id", index=True
    )
    product_variant_id: Optional[int] = Field(
        default=None, foreign_key="product_variants.id", index=True
    )

    # Cart Item Info
    quantity: int = Field(default=1)
    variant_attributes: Optional[dict] = Field(default=None, sa_column=Column(JSON))

    # Optional media snapshot
    # image: Optional[dict] = Field(default=None, sa_column=Column(JSON))

    # Relationships
    cart: "Cart" = Relationship(back_populates="items")
    product: Optional["Product"] = Relationship()
    variant: Optional["ProductVariant"] = Relationship()

    @property
    def price(self) -> Optional[float]:
        if not self.variant:
            return None

        if self.variant.discount_price is not None:
            return self.variant.discount_price

        return self.variant.price

    @property
    def actual_price(self) -> Optional[float]:
        if not self.variant:
            return None

        return self.variant.price

    @property
    def image(self) -> Optional[MediaRead]:
        if not self.variant:
            return None

        # Most variants never get their own per-variant image (that's only
        # set when a client explicitly uploads one) — fall back to the
        # product's thumbnail, which is the one image every product has.
        if self.variant.image:
            return self.variant.image

        return self.variant.product.thumbnail if self.variant.product else None

    @property
    def product_name(self) -> Optional[str]:
        if not self.variant:
            return None

        return self.variant.product.name


class CartItemRead(SQLModel, TimeStampReadModel):
    id: int
    cart_id: int
    product_id: Optional[int] = None
    product_variant_id: Optional[int] = None
    price: Optional[float] = None
    actual_price: Optional[float] = None
    quantity: int
    variant_attributes: Optional[dict] = None
    image: Optional[MediaRead] = None
    product_name: Optional[str] = None


class CartItemForm:
    def __init__(
        self,
        product_id: Optional[int] = Form(None),
        product_variant_id: Optional[int] = Form(None),
        quantity: Optional[int] = Form(1),
        variant_attributes: Optional[str] = Form(
            None,
            description="JSON object containing selected variant attributes.",
            examples=['{"color": "red", "size": "M"}'],
        ),
        # Media
        image: Optional[Union[UploadFile, str]] = File(None),
    ):
        self.product_id = to_int(product_id)
        self.product_variant_id = to_int(product_variant_id)
        self.quantity = to_int(quantity) or 1
        self.variant_attributes = (
            clean_json(variant_attributes) if variant_attributes is not None else None
        )
        self.image = image
