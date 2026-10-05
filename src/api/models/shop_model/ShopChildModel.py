from pydantic import EmailStr

from src.api.models.shop_model.shopModel import UserReadShop
from src.api.models.baseModel import TimeStampReadModel, TimeStampedModel
from typing import TYPE_CHECKING, Optional, Union
from sqlmodel import Field, Relationship, SQLModel, UniqueConstraint

if TYPE_CHECKING:
    from src.api.models import User, Product, Shop


class ShopUser(TimeStampedModel, table=True):
    __tablename__ = "shop_users"

    id: Optional[int] = Field(default=None, primary_key=True)

    user_id: int = Field(foreign_key="users.id", index=True)
    shop_id: int = Field(foreign_key="shops.id", index=True)

    is_active: bool = Field(default=True)

    __table_args__ = (UniqueConstraint("user_id", "shop_id", name="uq_shop_user"),)

    # Relationships
    user: "User" = Relationship(back_populates="shop_memberships")
    shop: "Shop" = Relationship(back_populates="members")


class ShopUserRead(SQLModel, TimeStampReadModel):
    id: int
    user_id: int
    shop_id: int
    is_active: Optional[bool]


class ShopUserReadWithUser(ShopUserRead):
    id: int
    user: UserReadShop = None
    shop_id: int
    is_active: Optional[bool]


class ShopUserCreate(SQLModel):
    email: EmailStr = Field(description="Email of the user to be added")

    is_active: Optional[bool] = True


class ShopUserUpdate(SQLModel):
    is_active: Optional[bool]
