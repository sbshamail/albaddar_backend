from typing import TYPE_CHECKING, List, Optional

from pydantic import field_validator
from sqlalchemy import JSON
from sqlmodel import Field, Index, Relationship, SQLModel, UniqueConstraint, text
from enum import Enum

from src.api.models.baseModel import TimeStampReadModel, TimeStampedModel

if TYPE_CHECKING:
    from src.api.models.role_model.userRoleModel import UserRole


class Role(TimeStampedModel, table=True):
    __tablename__ = "roles"
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=50)

    description: Optional[str] = None
    permissions: list[str] = Field(
        default_factory=list,
        sa_type=JSON,
    )
    user_id: int = Field(foreign_key="users.id")
    shop_id: Optional[int] = Field(default=None, foreign_key="shops.id", index=True)
    is_system: Optional[bool] = Field(default=False)  # root roles
    is_active: bool = Field(default=True)
    # relationships
    user_roles: list["UserRole"] = Relationship(back_populates="role")

    __table_args__ = (
        # ✅ Unique per shop
        UniqueConstraint("name", "shop_id", name="uq_role_name_shop"),
        # ✅ Global unique when shop_id IS NULL
        Index(
            "uq_role_name_global",
            "name",
            unique=True,
            postgresql_where=text("shop_id IS NULL"),
        ),
    )

    @property
    def roles(self):
        """Return roles directly (not UserRole objects)."""
        return [ur.role for ur in self.user_roles if ur.role]


class SitePermissionEnum(str, Enum):
    ROLE_CREATE = "role:create"
    ROLE_DELETE = "role:delete"

    HOMEPAGE_MANAGE = "homepage:manage"


class ShopPermissionEnum(str, Enum):
    PRODUCT_CREATE = "product:create"
    PRODUCT_UPDATE = "product:update"
    PRODUCT_DELETE = "product:delete"

    ORDER_VIEW = "order:view"
    ORDER_UPDATE = "order:update"

    USER_MANAGE = "user:manage"


class RoleReadBase(TimeStampReadModel):
    id: int
    name: str
    permissions: list[str]
    user_id: int
    shop_id: Optional[int]
    is_active: bool
    description: Optional[str]


class RoleRead(SQLModel, RoleReadBase):
    """Full role info returned in UserRead"""

    pass

    class Config:
        from_attributes = True


class RoleCreate(SQLModel):
    name: str
    description: Optional[str] = None
    permissions: list[str] = []


class RoleUpdate(SQLModel):
    name: Optional[str] = None
    description: Optional[str] = None
    permissions: Optional[list[str]] = None


class ShopRoleCreate(SQLModel):
    name: str
    permissions: List[ShopPermissionEnum]

    @field_validator("permissions")
    def validate_permissions(cls, v):
        if not v:
            raise ValueError("At least one permission required")
        return list(set(v))


class ShopRoleUpdate(SQLModel):
    name: Optional[str] = None
    description: Optional[str] = None
    permissions: Optional[List[ShopPermissionEnum]] = None
