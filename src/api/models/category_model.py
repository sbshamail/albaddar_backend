import json
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

from fastapi import File, Form, UploadFile
from pydantic import BaseModel
from sqlalchemy import JSON, Column, Enum, UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel

from src.api.models.utils import clean, to_bool, to_float, to_int
from src.api.models.baseModel import TimeStampReadModel, TimeStampedModel

if TYPE_CHECKING:
    from src.api.models import Product


class Category(TimeStampedModel, table=True):
    __tablename__ = "categories"
    __table_args__ = (
        UniqueConstraint("parent_id", "name", name="uq_category_name_per_parent"),
    )

    # ==========================
    # Primary Fields
    # ==========================
    id: Optional[int] = Field(default=None, primary_key=True)

    # Category name (e.g. "Electronics", "Mobiles")
    name: str = Field(max_length=191, index=True)

    # URL-friendly unique identifier (e.g. "electronics", "mobiles")
    slug: str = Field(max_length=191, index=True, unique=True)

    # Hierarchy level:
    # 1 = Root category
    # 2 = Sub-category
    # 3 = Sub-sub-category
    level: int = Field(default=1, index=True)

    # Optional UI icon (string path or icon class)
    icon: Optional[str] = Field(default=None, max_length=191)

    # Category image (stored as JSON: url, alt, etc.)
    image: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))

    # Long description / details
    details: Optional[str] = Field(default=None)

    # ==========================
    # Hierarchy (Self-referencing)
    # ==========================

    # Direct parent (NULL for root categories)
    parent_id: Optional[int] = Field(
        default=None, foreign_key="categories.id", index=True
    )

    # Root category reference (top-most ancestor)
    root_id: Optional[int] = Field(
        default=None, foreign_key="categories.id", index=True
    )

    # ==========================
    # Business Fields
    # ==========================

    # Commission percentage for admin
    admin_commission_rate: Optional[float] = Field(default=None)

    # Active / inactive toggle
    is_active: bool = Field(default=True, index=True)

    # ==========================
    # Relationships
    # ==========================

    # Parent category
    parent: Optional["Category"] = Relationship(
        back_populates="children",
        sa_relationship_kwargs={
            "remote_side": "Category.id",
            "foreign_keys": "[Category.parent_id]",
        },
    )

    # Child categories
    children: List["Category"] = Relationship(
        back_populates="parent",
        sa_relationship_kwargs={
            "foreign_keys": "[Category.parent_id]",
            "cascade": "all, delete",  # optional: auto-delete children
        },
    )

    # Root category (top-level ancestor)
    root: Optional["Category"] = Relationship(
        back_populates="descendants",
        sa_relationship_kwargs={
            "remote_side": "Category.id",  # parent relationship → needs remote_side ✅
            "foreign_keys": "[Category.root_id]",  # root relationship   → also needs remote_side ✅
        },
    )

    # All descendants under same root
    descendants: List["Category"] = Relationship(
        back_populates="root",
        sa_relationship_kwargs={
            "foreign_keys": "[Category.root_id]",
        },
    )

    # Products under this category
    products: List["Product"] = Relationship(back_populates="category")


class CategoryBase(TimeStampReadModel):
    name: str = Field(..., max_length=191)
    slug: str = Field(..., max_length=191)

    level: Optional[int] = 1

    icon: Optional[str] = None
    image: Optional[Union[UploadFile, str]] = (File(None),)
    details: Optional[str] = None

    parent_id: Optional[int] = None
    root_id: Optional[int] = None

    admin_commission_rate: Optional[float] = None
    is_active: Optional[bool] = True


class CategoryRead(SQLModel, CategoryBase):
    id: int

    class Config:
        from_attributes = True


class ProductRead(SQLModel):
    id: int
    name: str


class CategoryProductRead(SQLModel, CategoryBase):
    id: int
    products: List["ProductRead"] = []

    class Config:
        from_attributes = True


class CategoryTreeRead(CategoryRead):
    children: List["CategoryTreeRead"] = []


class CategoryForm:
    def __init__(
        self,
        # ==========================
        # Basic Info
        # ==========================
        name: Optional[str] = Form(None),
        details: Optional[str] = Form(None),
        # ==========================
        # Hierarchy
        # ==========================
        parent_id: Optional[int] = Form(None),
        # ==========================
        # Media
        # ==========================
        icon: Optional[str] = Form(None),
        image: Optional[Union[UploadFile, str]] = File(None),
        # ==========================
        # Business
        # ==========================
        admin_commission_rate: Optional[float] = Form(None),
        is_active: Optional[bool] = Form(True),
    ):
        # ==========================
        # Assign values
        # ==========================
        self.name = clean(name)

        self.details = clean(details)

        # ==========================
        # Hierarchy logic
        # ==========================
        self.parent_id = to_int(parent_id)

        # ==========================
        # Media
        # ==========================
        self.icon = clean(icon)
        self.image = image  # UploadFile or string (URL)

        # ==========================
        # Business
        # ==========================
        self.admin_commission_rate = to_float(admin_commission_rate)
        self.is_active = to_bool(is_active) if is_active is not None else True
