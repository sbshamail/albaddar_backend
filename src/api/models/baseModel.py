from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel
from sqlmodel import Field, SQLModel


class TimeStampedModel(SQLModel):
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: Optional[datetime] = None


class TimeStampReadModel(BaseModel):
    created_at: datetime
    updated_at: Optional[datetime] = None

    # model_config = ConfigDict(from_attributes=True)
