from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel
from sqlalchemy import JSON, Column
from sqlmodel import Field, Relationship, SQLModel

from src.api.core.html_sanitizer import derive_summary
from src.api.models.baseModel import TimeStampedModel
from src.api.models.mediaModel import MediaRead
from src.api.models.userModel import User


class Blog(TimeStampedModel, table=True):
    """A quick post — cover image + content, like a WhatsApp / Facebook
    update. Always live; written by site admins and shop members.

    Everything else search engines need (title, description, headings) is
    derived from `content`, so there are no separate SEO fields."""

    __tablename__ = "blogs"

    id: Optional[int] = Field(default=None, primary_key=True)
    # Derived from the content's first heading / line (see derive_title).
    title: str = Field(max_length=191)
    # URL identity (/blog/<slug>) — unique; fixed when the post is created.
    slug: str = Field(max_length=200, unique=True, index=True)
    # Sanitised HTML from the admin's RichTextEditor (images included). Media
    # URLs are stored as `/media/<file>`.
    content: str = Field(default="")
    # Stored media dict ({id, filename, original, media_type}).
    cover_image: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    # Optional YouTube / Vimeo link, resolved when the post is stored:
    # {provider, video_id, url, title, thumbnail: media dict}. The storefront
    # shows its thumbnail (click to play) instead of the cover.
    video: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))

    author_id: Optional[int] = Field(default=None, foreign_key="users.id", index=True)
    author: Optional[User] = Relationship()

    @property
    def author_name(self) -> Optional[str]:
        return self.author.full_name if self.author else None

    @property
    def excerpt(self) -> Optional[str]:
        """Computed (not stored): first paragraph, used on cards and as the
        meta description."""
        return derive_summary(self.content) or (
            (self.video or {}).get("title") or None
        )


# ==========================
# Read schemas
# ==========================
class BlogVideoRead(BaseModel):
    provider: str  # "youtube" | "vimeo"
    video_id: str
    url: str
    title: Optional[str] = None
    thumbnail: Optional[MediaRead] = None


class BlogListRead(SQLModel):
    """Card / table row — no body."""

    id: int
    title: str
    slug: str
    excerpt: Optional[str] = None
    cover_image: Optional[MediaRead] = None
    video: Optional[BlogVideoRead] = None
    author_name: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None


class BlogRead(BlogListRead):
    content: str = ""


# ==========================
# Request bodies (JSON)
# ==========================
class BlogCreate(BaseModel):
    content: str = ""
    # Filename of an already-uploaded media row (POST /media/create first).
    cover_image: Optional[str] = None
    # YouTube / Vimeo link — resolved (title + thumbnail saved) on store.
    video_url: Optional[str] = None


class BlogUpdate(BaseModel):
    """Partial update: an omitted key is left alone; `cover_image: null`
    removes the cover (`model_dump(exclude_unset=True)`)."""

    content: Optional[str] = None
    cover_image: Optional[str] = None
    video_url: Optional[str] = None
