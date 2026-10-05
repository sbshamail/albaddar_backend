from typing import TYPE_CHECKING, Optional, List, Union
from fastapi import File, Form, UploadFile
from pydantic import BaseModel, model_validator
from sqlmodel import JSON, SQLModel, Field, Relationship, Column


from src.api.models.mediaModel import MediaRead
from src.api.models.utils import clean, clean_json, to_bool, to_float, to_int
from src.api.models.baseModel import TimeStampReadModel, TimeStampedModel

if TYPE_CHECKING:
    from src.api.models import Product


class ProductVariant(TimeStampedModel, table=True):
    __tablename__ = "product_variants"

    id: Optional[int] = Field(default=None, primary_key=True)

    product_id: int = Field(foreign_key="products.id", index=True)

    # Variant Identity
    sku: Optional[str] = Field(default=None, index=True)

    # Pricing (override product)
    price: Optional[float] = None
    discount_price: Optional[float] = None

    # Inventory
    stock: int = Field(default=0)
    is_in_stock: bool = Field(default=True)

    # Shipping — kg, optional (not every product needs weight-based
    # shipping); snapshotted onto OrderItem at order time (see OrderRoute.py).
    weight: Optional[float] = None

    # Display order within the product's variant list.
    position: int = Field(default=0)

    # Variant Attributes (IMPORTANT)
    attributes: dict = Field(default_factory=dict, sa_column=Column(JSON))
    # Example: {"color": "Red", "size": "M"}

    # Media
    image: Optional[dict] = Field(default=None, sa_column=Column(JSON))

    # Relationships
    product: "Product" = Relationship(back_populates="variants")


class ProductVariantRead(SQLModel, TimeStampReadModel):
    id: int

    product_id: int

    # Variant Identity
    sku: Optional[str] = Field(default=None, index=True)

    # Pricing (override product)
    price: Optional[float] = None
    discount_price: Optional[float] = None

    # Inventory
    sku: Optional[str] = None
    stock: int
    is_in_stock: bool

    # Shipping (kg)
    weight: Optional[float] = None

    # Display order within the product's variant list.
    position: int = 0

    # Attributes
    attributes: Optional[dict] = None
    # Example: {"color": "Red", "size": "M"}

    # Media
    image: Optional[MediaRead] = None

    @model_validator(mode="before")
    @classmethod
    def fallback_to_product_thumbnail(cls, values):
        image = (
            values.get("image")
            if isinstance(values, dict)
            else getattr(values, "image", None)
        )
        if image:
            return values

        product = (
            values.get("product")
            if isinstance(values, dict)
            else getattr(values, "product", None)
        )
        thumbnail = getattr(product, "thumbnail", None) if product else None
        if thumbnail:
            if isinstance(values, dict):
                values = {**values, "image": thumbnail}
            else:
                values.image = thumbnail
        return values


class ProductVariantForm:
    def __init__(
        self,
        # -------------------------
        # Variant Identity
        # -------------------------
        sku: Optional[str] = Form(""),
        # -------------------------
        # Pricing
        # -------------------------
        price: Optional[float] = Form(None),
        discount_price: Optional[float] = Form(None),
        # -------------------------
        # Inventory
        # -------------------------
        stock: Optional[int] = Form(None),
        is_in_stock: Optional[bool] = Form(True),
        # -------------------------
        # Shipping
        # -------------------------
        weight: Optional[float] = Form(None),
        # -------------------------
        # Media
        # -------------------------
        image: Optional[Union[UploadFile, str]] = File(None),
        # -------------------------
        # JSON Fields
        # -------------------------
        attributes: Optional[str] = Form(
            {},
            description="JSON object containing variant attributes.",
            examples=['{"color": "Red", "size": "L"}'],
        ),
        # -------------------------
        # Status
        # -------------------------
        is_active: Optional[bool] = Form(True),
        # -------------------------
        # position
        # -------------------------
        position: Optional[int] = Form(0),
    ):

        # ==========================
        # Assign values
        # ==========================
        self.sku = clean(sku)

        self.price = to_float(price)
        self.discount_price = to_float(discount_price)

        self.stock = to_int(stock) or 0
        self.is_in_stock = to_bool(is_in_stock) if is_in_stock is not None else True

        self.weight = to_float(weight)

        # Media
        self.image = image

        # JSON
        self.attributes = clean_json(attributes) or {}

        # Status
        self.is_active = to_bool(is_active) if is_active is not None else True

        # position
        self.position = to_int(position)
