from datetime import datetime, timezone
import json
import re
from typing import Any, List
import unicodedata

from fastapi import UploadFile

date_formats = [
    "%d-%m-%Y",
    "%d/%m/%Y",
    "%-d/%-m/%Y",
    "%d/%-m/%Y",
    "%-d/%m/%Y",
    "%d-%-m-%Y",
    "%-d-%m-%Y",
    "%-d-%-m-%Y",
    "%-d-%b-%y",
    "%d-%b-%y",
    "%-d-%b-%Y",
    "%Y-%m-%dT%H:%M:%S.%fZ",
    "%Y-%m-%dT%H:%M:%S.%f",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M",
    "%Y-%m-%dT%H",
    "%Y-%m-%d",
]


def parse_date(date_str: str) -> datetime:
    for fmt in date_formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    raise ValueError(f"Date '{date_str}' is not in a valid UTC format.")


# slug = slugify("ACME Industries Inc.")
# print(slug)  # acme-industries-inc
def slugify(text: str) -> str:
    """
    Convert text into a URL-friendly slug.
    Example: "ACME Industries Inc." -> "acme-industries-inc"
    """
    if not text:
        return ""

    # Normalize unicode (e.g., remove accents like café → cafe)
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")

    # Lowercase
    text = text.lower()

    # Replace non-alphanumeric characters with hyphens
    text = re.sub(r"[^a-z0-9]+", "-", text)

    # Remove leading/trailing hyphens
    text = text.strip("-")

    return text


def uniqueSlugify(session, model, name: str, slug_field: str = "slug") -> str:
    base_slug = slugify(name)
    slug = base_slug
    counter = 1

    while session.query(model).filter(getattr(model, slug_field) == slug).first():
        slug = f"{base_slug}-{counter}"
        counter += 1

    return slug


def Print(data, title="Result"):
    print(
        f"====================={title}====================\n",
        json.dumps(data, indent=2, default=str),
    )


def parse_list(value):
    """
    Convert a string like "a,b,c" or ["a,b,c"] into ["a","b","c"]
    """
    if not value:
        return []

    if isinstance(value, list):
        # list with one comma-joined string
        if len(value) == 1 and isinstance(value[0], str):
            return [v.strip() for v in value[0].split(",") if v.strip()]
        # already normal list
        return [v.strip() for v in value]

    if isinstance(value, str):
        return [v.strip() for v in value.split(",") if v.strip()]

    return []
