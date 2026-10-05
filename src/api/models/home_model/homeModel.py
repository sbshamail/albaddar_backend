import re
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

from fastapi import File, Form, UploadFile
from pydantic import BaseModel
from sqlalchemy import JSON, Column
from sqlmodel import Field, Relationship, SQLModel
from starlette.datastructures import UploadFile as StarletteUploadFile

from src.api.models.baseModel import TimeStampedModel, TimeStampReadModel
from src.api.models.mediaModel import MediaRead
from src.api.models.utils import to_bool, to_int


# The only background shapes accepted (what the admin's GradientPicker
# emits). Strict on purpose: the value is rendered into an inline style on
# the storefront, so anything free-form (url(), expression, `;`) is rejected.
_HEX = r"#[0-9a-fA-F]{6}"
_BACKGROUND_RE = re.compile(
    rf"^(?:{_HEX}|linear-gradient\((?:[0-9]|[1-9][0-9]|[1-3][0-9]{{2}})deg, {_HEX} \d{{1,3}}%, {_HEX} \d{{1,3}}%\))$"
)


def validate_background(value: Optional[str]) -> bool:
    return value is None or _BACKGROUND_RE.fullmatch(value) is not None


class HomeSectionType(str, Enum):
    """What a homepage section renders. The storefront maps each value to
    one component, so adding a new section kind = a new value here + one
    entry in the storefront's section registry."""

    HERO = "hero"  # the classic featured-product hero slider
    CAROUSEL = "carousel"  # admin-made slides (image / rich text / link)
    BANNER_ROW = "banner_row"  # N banners side by side (default 4)
    FEATURED_PRODUCTS = "featured_products"
    PRODUCT_LIST = "product_list"


# Section kinds whose content is a set of Banner rows.
BANNER_SECTION_TYPES = {HomeSectionType.CAROUSEL, HomeSectionType.BANNER_ROW}


class HomeSection(TimeStampedModel, table=True):
    """One block of the storefront homepage. Rendered top-to-bottom by
    `position`; `is_active=False` hides it without deleting its content."""

    __tablename__ = "home_sections"

    id: Optional[int] = Field(default=None, primary_key=True)
    type: str = Field(max_length=50, index=True)

    # Optional heading shown above the section (product sections use it as
    # their title; banner sections only show it when set).
    title: Optional[str] = Field(default=None, max_length=191)

    position: int = Field(default=0, index=True)
    is_active: bool = Field(default=True, index=True)

    # One width/height pair applies to EVERY banner in the section, so a row
    # stays uniform. Pixels. They define the banner's aspect ratio (and max
    # width) — the storefront scales that ratio fluidly, so it stays
    # responsive. Both optional: unset = the component's built-in sizing.
    width: Optional[int] = Field(default=None)
    height: Optional[int] = Field(default=None)

    # Escape the page's max-w container (carousel / hero edge-to-edge).
    full_width: bool = Field(default=False)

    # banner_row: banners per row on desktop (mobile collapses automatically).
    columns: Optional[int] = Field(default=None)

    # carousel / hero: auto-advance slides.
    autoplay: bool = Field(default=True)

    # featured_products / product_list: how many to show, and an optional
    # category scope (any depth) for product_list.
    product_limit: Optional[int] = Field(default=None)
    category_id: Optional[int] = Field(
        default=None, foreign_key="categories.id", index=True
    )

    banners: List["Banner"] = Relationship(
        back_populates="section",
        sa_relationship_kwargs={
            "cascade": "all, delete-orphan",
            "order_by": "Banner.position",
        },
    )


class Banner(TimeStampedModel, table=True):
    """A single banner / slide inside a banner_row or carousel section."""

    __tablename__ = "banners"

    id: Optional[int] = Field(default=None, primary_key=True)
    section_id: int = Field(foreign_key="home_sections.id", index=True)

    # Stored media dict ({id, filename, original, media_type}), same shape
    # as Category.image. Optional — a banner may be text-only, but it needs
    # an image or text (enforced in the routes).
    image: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))

    # Alt text / admin label.
    title: Optional[str] = Field(default=None, max_length=191)
    # Rich text (HTML from the admin's RichTextEditor), laid over the image.
    content: Optional[str] = Field(default=None)

    # Background behind the image / text-only card: a solid `#rrggbb` or a
    # two-stop `linear-gradient(...)` string (shape enforced by
    # validate_background). None → the storefront uses its theme `bg-card`.
    background: Optional[str] = Field(default=None, max_length=200)

    # Click action. Internal paths ("/product/12") or absolute URLs.
    link_url: Optional[str] = Field(default=None, max_length=500)
    open_in_new_tab: bool = Field(default=False)

    position: int = Field(default=0, index=True)
    is_active: bool = Field(default=True, index=True)

    section: Optional[HomeSection] = Relationship(back_populates="banners")


# ==========================
# Read schemas
# ==========================
class BannerRead(SQLModel):
    id: int
    section_id: int
    image: Optional[MediaRead] = None
    title: Optional[str] = None
    content: Optional[str] = None
    background: Optional[str] = None
    link_url: Optional[str] = None
    open_in_new_tab: bool = False
    position: int = 0
    is_active: bool = True


class HomeSectionRead(SQLModel):
    id: int
    type: str
    title: Optional[str] = None
    position: int = 0
    is_active: bool = True
    width: Optional[int] = None
    height: Optional[int] = None
    full_width: bool = False
    columns: Optional[int] = None
    autoplay: bool = True
    product_limit: Optional[int] = None
    category_id: Optional[int] = None
    banners: List[BannerRead] = []

    class Config:
        from_attributes = True


class ReorderRequest(BaseModel):
    ids: List[int]


# ==========================
# Request bodies (JSON)
# ==========================
class HomeSectionCreate(BaseModel):
    """JSON body — a section carries no file, so no multipart needed."""

    type: HomeSectionType
    title: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    full_width: bool = False
    columns: Optional[int] = None
    autoplay: bool = True
    product_limit: Optional[int] = None
    category_id: Optional[int] = None
    is_active: bool = True


class HomeSectionUpdate(BaseModel):
    """JSON body, partial update: a key that is omitted is left alone, a key
    sent as null clears it (applied via `model_dump(exclude_unset=True)`).
    `type` is not editable — a section's kind is fixed once created."""

    title: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    full_width: Optional[bool] = None
    columns: Optional[int] = None
    autoplay: Optional[bool] = None
    product_limit: Optional[int] = None
    category_id: Optional[int] = None
    is_active: Optional[bool] = None


# ==========================
# Form schemas (banner only — it uploads an image)
# ==========================
class BannerForm:
    """Multipart/Form payload. On update, text fields distinguish omitted
    (None → untouched) from whitespace-only (→ cleared; an empty string is
    dropped by FastAPI before it gets here)."""

    def __init__(
        self,
        section_id: Optional[int] = Form(None),
        title: Optional[str] = Form(None),
        content: Optional[str] = Form(None),
        background: Optional[str] = Form(None),
        link_url: Optional[str] = Form(None),
        open_in_new_tab: Optional[bool] = Form(None),
        is_active: Optional[bool] = Form(None),
        image: Optional[Union[UploadFile, str]] = File(None),
        remove_image: Optional[bool] = Form(None),
    ):
        self.section_id = to_int(section_id)
        self.title = title
        self.content = content
        # None = omitted; whitespace-only = clear (see update route).
        self.background = background.strip() if isinstance(background, str) else None
        self.link_url = link_url.strip() if isinstance(link_url, str) else None
        self.open_in_new_tab = to_bool(open_in_new_tab)
        self.is_active = to_bool(is_active)
        # Update only: drop the current image (a text-only banner).
        self.remove_image = to_bool(remove_image)
        # Only a real upload counts; "" / a string means "keep the image".
        # (isinstance against Starlette's class: that's what the multipart
        # parser actually produces — fastapi.UploadFile is only a subclass
        # used for annotations.)
        self.image = image if isinstance(image, StarletteUploadFile) else None
