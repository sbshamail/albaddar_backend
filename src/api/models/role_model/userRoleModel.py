from typing import TYPE_CHECKING, Literal, Optional


from pydantic import BaseModel
from sqlmodel import Field, Relationship, SQLModel, UniqueConstraint


from src.api.models.baseModel import TimeStampedModel


if TYPE_CHECKING:
    from src.api.models.userModel import User
    from src.api.models.role_model.roleModel import Role


#  Database Table Model
class UserRole(TimeStampedModel, table=True):
    __tablename__ = "user_roles"

    id: Optional[int] = Field(default=None, primary_key=True)  # type: ignore
    user_id: int = Field(foreign_key="users.id")
    role_id: int = Field(foreign_key="roles.id")
    shop_id: Optional[int] = Field(foreign_key="shops.id")

    __table_args__ = (UniqueConstraint("user_id", "role_id", name="uq_user_role"),)

    # relationships
    user: "User" = Relationship(back_populates="user_roles")
    role: "Role" = Relationship(back_populates="user_roles")


# Request Schema/Pydantic Model
class UserRoleCreate(SQLModel):
    role_id: int
    user_id: int


class RoleRead(SQLModel):
    id: int
    name: str
    permissions: list[str]


class UserRead(SQLModel):
    id: int
    full_name: str
    email: str


class UserRoleRead(UserRoleCreate):
    id: int
    role: Optional[RoleRead] = None
    user: Optional[UserRead] = None
