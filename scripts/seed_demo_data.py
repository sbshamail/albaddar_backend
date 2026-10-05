"""One-off seed script — NOT a permanent API route, run manually.

    uv run python scripts/seed_demo_data.py [--count 24]

What it does, in order:
1. Creates the real category tree this shop actually needs (Electrical,
   Hardware, Security Cameras, Clothes, Gadgets, Smart Phones + subs).
2. Re-points any product still sitting on the old placeholder "test" /
   "test sub" categories onto the new real "Power Tools" leaf, then deletes
   those 3 placeholder categories.
3. Seeds `--count` demo products from the Platzi Fake Store API
   (https://api.escuelajs.co), downloading their images into real Media
   records via download_and_save_image() (same pipeline as a real upload),
   distributed round-robin across the new leaf categories.

Demo products are tagged "demo" in their `tags` field specifically so they
can be bulk-deleted later without touching real data, e.g.:

    DELETE FROM products WHERE tags::jsonb @> '["demo"]'::jsonb;
    -- (tags is a plain JSON column, not JSONB, so the cast is required)

or via the existing deep-filter list endpoint: deepFilters=[["tags",["demo"]]]
"""

import argparse
import asyncio
import random

import httpx
from sqlmodel import Session, delete, select

from src.lib.db_con import engine
from src.api.core.operation.media import download_and_save_image
from src.api.core.utility import uniqueSlugify
from src.api.models.category_model import Category
from src.api.models.product_model.productModel import Product
from src.api.models.product_model.ProductVariantModel import ProductVariant
from src.api.routers.category.fn import calculate_category_level

SHOP_ID = 1
CREATED_BY = 1

CATEGORY_TREE = {
    "Electrical": [
        "Wiring & Cables",
        "Switches & Sockets",
        "Circuit Breakers & Panels",
        "Lighting",
    ],
    "Hardware": [
        "Hand Tools",
        "Power Tools",
        "Fasteners",
        "Locks & Security Hardware",
    ],
    "Security Cameras": [
        "CCTV Cameras",
        "Video Doorbells",
        "NVR/DVR Systems",
        "Camera Accessories",
    ],
    "Clothes": ["Men's Clothing", "Women's Clothing", "Kids' Clothing"],
    "Gadgets": [
        "Smart Watches",
        "Earbuds & Headphones",
        "Power Banks",
        "Smart Home Devices",
    ],
    "Smart Phones": ["Android Phones", "iPhones", "Phone Accessories"],
}

PLATZI_API = "https://api.escuelajs.co/api/v1/products"
OLD_TEST_CATEGORY_NAMES = ["test", "test sub"]
FALLBACK_LEAF_NAME = "Power Tools"


def create_category(session, name, parent_id=None) -> Category:
    level = calculate_category_level(session, parent_id)
    slug = uniqueSlugify(session, Category, name)
    category = Category(name=name, slug=slug, level=level, parent_id=parent_id)
    session.add(category)
    session.flush()

    if parent_id:
        parent = session.get(Category, parent_id)
        category.root_id = parent.root_id or parent.id
    else:
        category.root_id = category.id
    session.add(category)
    session.flush()
    return category


def get_or_create_category(session, name, parent_id=None) -> Category:
    existing = session.exec(
        select(Category).where(
            Category.name == name, Category.parent_id == parent_id
        )
    ).first()
    if existing:
        return existing
    return create_category(session, name, parent_id)


def build_category_tree(session) -> list[int]:
    # idempotent — safe to re-run without duplicating categories
    leaf_ids = []
    for root_name, subs in CATEGORY_TREE.items():
        root = get_or_create_category(session, root_name)
        for sub_name in subs:
            sub = get_or_create_category(session, sub_name, parent_id=root.id)
            leaf_ids.append(sub.id)
    return leaf_ids


def replace_test_categories(session) -> None:
    fallback = session.exec(
        select(Category).where(Category.name == FALLBACK_LEAF_NAME)
    ).first()
    if not fallback:
        print(f"WARNING: no '{FALLBACK_LEAF_NAME}' category found, skipping cleanup")
        return

    old_ids = session.exec(
        select(Category.id).where(Category.name.in_(OLD_TEST_CATEGORY_NAMES))
    ).all()
    if not old_ids:
        return

    orphaned = session.exec(
        select(Product).where(Product.category_id.in_(old_ids))
    ).all()
    for product in orphaned:
        print(f"  re-pointing product #{product.id} '{product.name}' -> {FALLBACK_LEAF_NAME}")
        product.category_id = fallback.id
        session.add(product)
    session.flush()

    # Raw bulk delete by id — going through session.delete() on these ORM
    # objects trips SQLAlchemy's dependency-cycle detector, because
    # Category.root_id is self-referential (row 1's root_id points at
    # itself) at the same time other rows' parent_id/root_id point at row
    # 1, and the automatic delete-ordering can't resolve that as anything
    # but a cycle. A raw statement bypasses relationship-aware ordering
    # entirely, which is fine here since we already re-pointed every
    # dependent product above.
    session.exec(delete(Category).where(Category.id.in_(old_ids)))
    session.flush()
    print(f"  deleted {len(old_ids)} placeholder categories")


def _clean_image_url(url: str) -> str:
    return url.strip().strip('"[]')


async def seed_products(session, leaf_ids: list[int], count: int) -> int:
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(PLATZI_API, params={"offset": 0, "limit": count})
        resp.raise_for_status()
        items = resp.json()

    created = 0
    for index, item in enumerate(items):
        name = item.get("title")
        if not name:
            continue

        slug = uniqueSlugify(session, Product, name)
        category_id = leaf_ids[index % len(leaf_ids)]

        raw_urls = [
            _clean_image_url(u) for u in (item.get("images") or []) if u
        ]
        raw_urls = [u for u in raw_urls if u.startswith("http")][:3]

        thumbnail = None
        images = []
        for pos, url in enumerate(raw_urls):
            saved = await download_and_save_image(url, session, shop_id=SHOP_ID)
            if not saved:
                continue
            if pos == 0:
                thumbnail = saved
            images.append(saved)
            await asyncio.sleep(0.3)  # be polite to imgur, avoid tripping rate limits

        product = Product(
            shop_id=SHOP_ID,
            created_by=CREATED_BY,
            category_id=category_id,
            name=name,
            slug=slug,
            description=item.get("description"),
            thumbnail=thumbnail,
            images=images,
            attributes=[],
            tags=["demo"],
            is_active=True,
        )
        session.add(product)
        session.flush()

        variant = ProductVariant(
            product_id=product.id,
            price=item.get("price") or 0,
            discount_price=None,
            stock=random.randint(10, 100),
            is_in_stock=True,
            sku=f"DEMO-{product.id}",
            attributes={},
            position=0,
        )
        session.add(variant)

        print(f"  #{product.id} {name} -> category {category_id}, {len(images)} image(s)")
        created += 1

    session.commit()
    return created


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=24)
    args = parser.parse_args()

    with Session(engine) as session:
        print("Building real category tree...")
        leaf_ids = build_category_tree(session)
        session.commit()
        print(f"Created {len(leaf_ids)} leaf categories.")

        print("Cleaning up placeholder test categories...")
        replace_test_categories(session)
        session.commit()

        print(f"Seeding {args.count} demo products from Platzi...")
        created = asyncio.run(seed_products(session, leaf_ids, args.count))
        print(f"Done. Created {created} demo products.")


if __name__ == "__main__":
    main()
