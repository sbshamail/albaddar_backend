"""Finds where each Media row is referenced.

Media is never linked by a real foreign key — other tables embed a copy of
the stored media dict ({id, filename, original, media_type}) in a JSON
column, and rich-text columns embed `/media/<file>` URLs. So "is this media
used?" means scanning those columns."""

import re
from collections import defaultdict
from typing import Any, Iterator

from sqlmodel import select

from src.api.models.blog_model.blogModel import Blog
from src.api.models.category_model import Category
from src.api.models.home_model.homeModel import Banner
from src.api.models.mediaModel import Media
from src.api.models.order_model.orderItemModel import OrderItem
from src.api.models.product_model.ProductVariantModel import ProductVariant
from src.api.models.product_model.productModel import Product
from src.api.models.shop_model.shopModel import Shop
from src.api.models.userModel import User

# (Model, JSON columns holding a media dict or a list of them)
JSON_MEDIA_COLUMNS = [
    (User, ["image"]),
    (Category, ["image"]),
    (Shop, ["cover_image", "logo"]),
    (Product, ["thumbnail", "images"]),
    (ProductVariant, ["image"]),
    (OrderItem, ["image"]),
    (Banner, ["image"]),
    (Blog, ["cover_image", "video"]),  # video.thumbnail is a nested media dict
]

# Text columns that may embed `/media/<file>` URLs (rich-text HTML)
TEXT_MEDIA_COLUMNS = [
    (Blog, ["content"]),
    (Product, ["short_description", "description", "whats_in_box"]),
]

_MEDIA_FILE = re.compile(r"/media/([A-Za-z0-9._\-]+)")


def _media_refs(value: Any) -> Iterator[tuple[Any, Any]]:
    """Yield (id, filename) for every media-shaped dict nested in `value`."""
    if isinstance(value, dict):
        if "filename" in value or ("id" in value and "original" in value):
            yield value.get("id"), value.get("filename")
        for v in value.values():
            if isinstance(v, (dict, list)):
                yield from _media_refs(v)
    elif isinstance(value, list):
        for item in value:
            yield from _media_refs(item)


def build_usage_map(session, medias: list[Media]) -> dict[int, list[dict]]:
    """{media_id: [{"table", "column", "row_id"}, ...]} — medias not
    referenced anywhere map to an empty list."""
    by_id = {m.id: m for m in medias}
    by_filename = {m.filename.lower(): m.id for m in medias}
    usage: dict[int, list[dict]] = defaultdict(list)
    seen: set[tuple] = set()

    def record(media_id, table, column, row_id):
        key = (media_id, table, column, row_id)
        if media_id in by_id and key not in seen:
            seen.add(key)
            usage[media_id].append(
                {"table": table, "column": column, "row_id": row_id}
            )

    for model, columns in JSON_MEDIA_COLUMNS:
        table = model.__tablename__
        for column in columns:
            attr = getattr(model, column)
            for row_id, value in session.exec(select(model.id, attr)).all():
                for ref_id, filename in _media_refs(value):
                    media_id = ref_id if ref_id in by_id else by_filename.get(
                        str(filename or "").lower()
                    )
                    if media_id is not None:
                        record(media_id, table, column, row_id)

    for model, columns in TEXT_MEDIA_COLUMNS:
        table = model.__tablename__
        for column in columns:
            attr = getattr(model, column)
            for row_id, text in session.exec(select(model.id, attr)).all():
                for filename in _MEDIA_FILE.findall(text or ""):
                    media_id = by_filename.get(filename.lower())
                    if media_id is not None:
                        record(media_id, table, column, row_id)

    return {m.id: usage.get(m.id, []) for m in medias}
