from typing import Optional

from pydantic import BaseModel, field_serializer
from sqlmodel import SQLModel, Field

from src.api.models.baseModel import TimeStampedModel
from src.config import DOMAIN


class Media(TimeStampedModel, table=True):
    __tablename__ = "media"
    id: Optional[int] = Field(default=None, primary_key=True)
    filename: str
    extension: str
    original: str
    media_type: str  # "image" | "video" | "doc"
    size_mb: Optional[float] = Field(default=None)
    thumbnail: Optional[str] = Field(default=None)
    shop_id: Optional[int] = Field(default=None, foreign_key="shops.id")


class MediaRead(BaseModel):
    id: int
    filename: str
    # extension: Optional[str] = None
    original: str
    # size_mb: Optional[float] = None
    thumbnail: Optional[str] = None
    media_type: str
    shop_id: Optional[int] = None

    @field_serializer("original")
    def add_domain_to_url(self, v: Optional[str], _info):
        return f"{DOMAIN}{v}" if v else None

    @field_serializer("thumbnail")
    def add_domain_to_thumbnail(self, v: Optional[str], _info):
        return f"{DOMAIN}{v}" if v else None

    class Config:
        from_attributes = True
