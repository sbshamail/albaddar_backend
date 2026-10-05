import json
from typing import TYPE_CHECKING, Optional, Union

from fastapi import File, Form, UploadFile
from sqlalchemy import JSON, Column
from sqlmodel import Field, Relationship, SQLModel

from src.api.models.mediaModel import MediaRead

from src.api.models.utils import clean, clean_json
from src.api.models.baseModel import TimeStampReadModel, TimeStampedModel

if TYPE_CHECKING:
    from src.api.models import User, Product, ShopUser


class Shop(TimeStampedModel, table=True):
    __tablename__ = "shops"

    id: Optional[int] = Field(default=None, primary_key=True)
    owner_id: int = Field(foreign_key="users.id", unique=True)
    name: str = Field(default=None, max_length=191, unique=True)
    slug: str = Field(default=None, max_length=191, index=True, unique=True)
    description: Optional[str] = None
    cover_image: Optional[dict] = Field(
        default=None, sa_column=Column(JSON), description="Cover Image"
    )
    logo: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    is_active: bool = Field(default=False)
    address: Optional[dict] = Field(default=None, sa_column=Column(JSON))

    # Relationships
    owner: "User" = Relationship(
        back_populates="shop",
        sa_relationship_kwargs={"foreign_keys": "[Shop.owner_id]"},
    )
    products: list["Product"] = Relationship(back_populates="shop")
    members: list["ShopUser"] = Relationship(back_populates="shop")


class ShopForm:
    def __init__(
        self,
        name: Optional[str] = Form(None),
        description: Optional[str] = Form(None),
        cover_image: Optional[Union[UploadFile, str]] = File(None),
        logo: Optional[Union[UploadFile, str]] = File(None),
        address: Optional[str] = Form(None),
    ):

        self.name = clean(name)
        self.description = clean(description)
        self.cover_image = cover_image
        self.logo = logo
        self.address = clean_json(address)


class ShopRead(SQLModel, TimeStampReadModel):
    id: Optional[int]
    name: str
    slug: str
    description: Optional[str] = None
    address: Optional[dict] = None
    cover_image: Optional[MediaRead] = None
    logo: Optional[MediaRead] = None
    is_active: bool


class UserReadShop(SQLModel):
    id: int
    full_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    verified: bool


class ShopReadWithOwner(ShopRead):
    owner: UserReadShop
