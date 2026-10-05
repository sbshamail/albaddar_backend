import json
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

from fastapi import File, Form, UploadFile
from pydantic import BaseModel, EmailStr, model_validator
from sqlalchemy import JSON, Column, Enum
from sqlmodel import Field, Index, Relationship, SQLModel, text

from src.api.models.role_model.roleModel import RoleRead
from src.api.models.baseModel import TimeStampReadModel, TimeStampedModel
from pydantic import computed_field

if TYPE_CHECKING:
    from src.api.models.addressModel import UserAddress
    from api.models.product_model.productModel import Product
    from src.api.models.shop_model.ShopChildModel import ShopUser
    from src.api.models.role_model.userRoleModel import UserRole

    from src.api.models.role_model.roleModel import Role

    from src.api.models.shop_model.shopModel import Shop


class UserPhone(SQLModel):
    # Saved only when fully verified
    phone: Optional[str] = Field(
        default=None, index=True, description="Verified unique phone"
    )

    verified: bool = Field(default=False)


class User(
    TimeStampedModel,
    UserPhone,
    table=True,
):
    __tablename__ = "users"
    id: int | None = Field(default=None, primary_key=True)
    email: EmailStr = Field(
        max_length=191, index=True, unique=True, description="Email address of the user"
    )

    email_verified: bool = Field(default=False, description="Email verification status")

    # Nullable — OTP registration only collects an email up front; name,
    # password, country/currency etc. get filled in later (e.g. at checkout,
    # via /user/update) rather than being required at signup.
    full_name: Optional[str] = Field(
        default=None, index=True, description="Full name of the user"
    )
    contactinfo: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    image: Optional[Dict[str, Any]] = Field(
        default=None, sa_column=Column(JSON), description="Image of the user"
    )
    is_root: bool = Field(default=False)
    is_active: bool = Field(default=True)
    password: Optional[str] = Field(default=None, description="Hashed password")

    use_token: Optional[str] = Field(default=None)

    country: Optional[str] = Field(
        default="Pakistan", description="Country name (e.g., Pakistan)"
    )
    country_code: Optional[str] = Field(
        default="PK", description="Country code (e.g., PK)"
    )
    currency_code: Optional[str] = Field(
        default="PKR", description="Currency code (e.g., PKR)"
    )
    currency_symbol: Optional[str] = Field(
        default="Rs", description="Currency symbol (e.g., ₨)"
    )
    default_shop_id: Optional[int] = Field(
        default=None, foreign_key="shops.id", index=True
    )
    token_version: Optional[int] = Field(default=0)
    # Relationships
    user_roles: list["UserRole"] = Relationship(back_populates="user")

    __table_args__ = (
        # Conditional unique index for verified phones
        Index(
            "uq_users_phone_verified",
            "phone",
            unique=True,
            postgresql_where=text("verified = true"),
        ),
        # ✅ Unique verified email only
        Index(
            "uq_users_verified_email",
            "email",
            unique=True,
            postgresql_where=text("email_verified = true"),
        ),
    )
    # owner relationship
    shop: Optional["Shop"] = Relationship(
        back_populates="owner",
        sa_relationship_kwargs={"foreign_keys": "[Shop.owner_id]"},
    )

    # default shop
    default_shop: Optional["Shop"] = Relationship(
        sa_relationship_kwargs={"foreign_keys": "[User.default_shop_id]"}
    )
    shop_memberships: list["ShopUser"] = Relationship(back_populates="user")
    created_products: list["Product"] = Relationship(back_populates="creator")
    addresses: list["UserAddress"] = Relationship(back_populates="user")

    # @property
    # def roles(self) -> list["Role"]:
    #     """Return Role objects directly"""
    #     return [ur.role for ur in self.user_roles if ur.role]

    @property
    def roles(self) -> list[dict]:
        result = []

        for ur in self.user_roles:
            if not ur.role:
                continue

            result.append(
                {
                    "id": ur.role.id,
                    "name": ur.role.name,
                    "permissions": ur.role.permissions,
                    "shop_id": ur.shop_id,
                }
            )

        return result

    @property
    def role_names(self) -> list[str]:
        return [role.name for role in self.roles]

    @property
    def permissions(self) -> list[str]:
        perms = set()

        for ur in self.user_roles:
            if ur.role:
                perms.update(ur.role.permissions or [])

        return list(perms)

    @property
    def shops_member(self):
        return [
            membership.shop for membership in self.shop_memberships if membership.shop
        ]


class UserCreate(SQLModel):
    full_name: str
    email: EmailStr
    phone: str
    password: str
    confirm_password: str
    country: Optional[str] = "Pakistan"
    country_code: Optional[str] = "PK"
    currency_code: Optional[str] = "PKR"
    currency_symbol: Optional[str] = "Rs"

    @model_validator(mode="before")
    def check_password_match(cls, values):
        if values.get("password") != values.get("confirm_password"):
            raise ValueError("Passwords do not match")
        return values


class UserUpdateForm:
    def __init__(
        self,
        email: Optional[str] = Form(None),
        phone: Optional[str] = Form(None),
        full_name: Optional[str] = Form(None),
        address: Optional[str] = Form(None),
        contactinfo: Optional[str] = Form(None),
        password: Optional[str] = Form(None),
        confirm_password: Optional[str] = Form(None),
        country: Optional[str] = Form(None),
        country_code: Optional[str] = Form(None),
        currency_code: Optional[str] = Form(None),
        currency_symbol: Optional[str] = Form(None),
        # image upload
        image: Optional[Union[UploadFile, str]] = File(None),
    ):
        # Convert empty → None
        def clean(v):
            if v is None:
                return None
            if isinstance(v, str) and v.strip() == "":
                return None
            return v

        def clean_json(v):
            v = clean(v)
            if v is None:
                return None
            try:
                return json.loads(v)
            except Exception:
                raise ValueError(f"Invalid JSON: {v}")

        self.email = clean(email)
        self.phone = clean(phone)
        self.full_name = clean(full_name)
        self.address = clean(address)
        self.contactinfo = clean_json(contactinfo)
        self.password = clean(password)
        self.confirm_password = clean(confirm_password)
        self.country = clean(country)
        self.country_code = clean(country_code)
        self.currency_code = clean(currency_code)
        self.currency_symbol = clean(currency_symbol)
        self.image: Optional[Union[UploadFile, str]] = image


class DefaultShopId(SQLModel):
    shop_id: int


class UserRoleRead(SQLModel):
    id: int
    name: str
    permissions: list[str]


class UserShopRead(SQLModel):
    id: int
    name: str
    slug: str
    owner_id: int  # must be included

    @computed_field
    @property
    def is_owner(self) -> bool:
        # fallback (will override using context)
        return False


class UserReadBase(TimeStampReadModel):
    id: int
    full_name: Optional[str] = None
    phone: Optional[str] = None
    email: EmailStr
    email_verified: bool
    # is_active: bool
    is_root: bool
    image: Optional[Dict[str, Any]] = None
    contactinfo: Optional[Dict[str, Any]] = None
    country: Optional[str] = None
    country_code: Optional[str] = None
    verified: bool
    currency_code: Optional[str] = None
    currency_symbol: Optional[str] = None
    default_shop_id: Optional[int] = None


class UserRead(SQLModel, UserReadBase):
    roles: Optional[List[UserRoleRead]] = None
    shop: Optional[UserShopRead] = None
    default_shop: Optional[UserShopRead] = None
    shops_member: Optional[List[UserShopRead]] = None
    pass


class LoginRequest(BaseModel):
    identifier: str  # phone OR email
    password: str


class EmailOtpRequest(BaseModel):
    email: EmailStr


class EmailOtpVerifyRequest(BaseModel):
    email: EmailStr
    otp: str


class ResetPasswordWithOTPRequest(BaseModel):
    email: EmailStr
    otp: str
    new_password: str
    confirm_password: str

    @model_validator(mode="before")
    def check_password_match(cls, values):
        password = values.get("new_password")
        confirm_password = values.get("confirm_password")

        # ✅ Only check if password provided
        if password and password != confirm_password:
            raise ValueError("Passwords do not match")

        return values


class UserUpdate(SQLModel):
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    full_name: Optional[str] = None

    password: Optional[str] = None
    confirm_password: Optional[str] = None
    country: Optional[str] = str
    country_code: Optional[str] = str
    currency_code: Optional[str] = str
    currency_symbol: Optional[str] = str

    @model_validator(mode="before")
    def check_password_match(cls, values):
        password = values.get("password")
        confirm_password = values.get("confirm_password")

        # ✅ Only check if password provided
        if password and password != confirm_password:
            raise ValueError("Passwords do not match")

        return values


class UpdateUserByAdmin(UserUpdate):
    role_id: Optional[int] = None
    verified: Optional[bool] = None
    email_verified: Optional[bool] = None
    is_active: Optional[bool] = None
