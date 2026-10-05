from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import selectinload
from sqlmodel import func, select

from src.api.core.dependencies import GetSession, requirePermission
from src.api.core.operation.media import deleteMediaFiles
from src.api.core.response import api_response, raiseExceptions
from src.api.models.category_model import Category
from src.api.models.home_model.homeModel import (
    BANNER_SECTION_TYPES,
    HomeSection,
    HomeSectionCreate,
    HomeSectionRead,
    HomeSectionType,
    HomeSectionUpdate,
    ReorderRequest,
)

router = APIRouter(prefix="/home-section", tags=["Home Section"])

PERMISSION = "homepage:manage"

# Sane bounds so a typo can't produce a 1px or 100,000px banner.
MAX_DIMENSION = 4000
MAX_COLUMNS = 6
MAX_PRODUCT_LIMIT = 48


def _validate(session, data: dict):
    """Range-check the optional numeric fields (None = unset, always fine)."""
    for field in ("width", "height"):
        v = data.get(field)
        if v is not None and not 1 <= v <= MAX_DIMENSION:
            api_response(400, f"{field} must be between 1 and {MAX_DIMENSION}")
    v = data.get("columns")
    if v is not None and not 1 <= v <= MAX_COLUMNS:
        api_response(400, f"columns must be between 1 and {MAX_COLUMNS}")
    v = data.get("product_limit")
    if v is not None and not 1 <= v <= MAX_PRODUCT_LIMIT:
        api_response(400, f"product_limit must be between 1 and {MAX_PRODUCT_LIMIT}")
    cid = data.get("category_id")
    if cid and not session.get(Category, cid):
        api_response(400, "Category not found")


def _load_sections(session, only_active: bool):
    stmt = (
        select(HomeSection)
        .options(selectinload(HomeSection.banners))
        .order_by(HomeSection.position, HomeSection.id)
    )
    if only_active:
        stmt = stmt.where(HomeSection.is_active == True)  # noqa: E712
    return session.exec(stmt).all()


@router.post("/create")
def create_section(
    request: HomeSectionCreate,
    session: GetSession,
    user=requirePermission(PERMISSION),
):
    data = request.model_dump()
    data["title"] = (data["title"] or "").strip() or None
    _validate(session, data)

    last = session.exec(select(func.max(HomeSection.position))).one()
    section = HomeSection(
        **{**data, "type": request.type.value},
        position=(last if last is not None else -1) + 1,
    )
    session.add(section)
    session.commit()
    session.refresh(section)

    return api_response(200, "Section created", HomeSectionRead.model_validate(section))


@router.put("/update/{id}")
def update_section(
    id: int,
    request: HomeSectionUpdate,
    session: GetSession,
    user=requirePermission(PERMISSION),
):
    section = session.get(HomeSection, id)
    raiseExceptions((section, 404, "Section not found"))

    # Only keys present in the body — omitted = untouched, null = cleared.
    data = request.model_dump(exclude_unset=True)
    if "title" in data:
        data["title"] = (data["title"] or "").strip() or None
    # These columns are NOT NULL — null makes no sense for them.
    for k in ("full_width", "autoplay", "is_active"):
        if k in data and data[k] is None:
            api_response(400, f"{k} cannot be null")
    _validate(session, data)

    for k, v in data.items():
        setattr(section, k, v)

    section.updated_at = datetime.now(timezone.utc)
    session.add(section)
    session.commit()
    session.refresh(section)

    return api_response(200, "Section updated", HomeSectionRead.model_validate(section))


@router.delete("/delete/{id}")
async def delete_section(
    id: int,
    session: GetSession,
    user=requirePermission(PERMISSION),
):
    section = session.get(HomeSection, id)
    raiseExceptions((section, 404, "Section not found"))

    # Banner rows go via the ORM cascade; their uploaded images need an
    # explicit cleanup or they'd be orphaned on disk.
    await deleteMediaFiles(session, [b.image for b in section.banners])
    session.delete(section)
    session.commit()

    return api_response(200, "Section deleted")


@router.put("/reorder")
def reorder_sections(
    body: ReorderRequest,
    session: GetSession,
    user=requirePermission(PERMISSION),
):
    """`ids` is the full desired order, top to bottom."""
    sections = {s.id: s for s in session.exec(select(HomeSection)).all()}
    raiseExceptions(
        (
            set(body.ids) <= set(sections),
            400,
            "Unknown section id in the order list",
        )
    )
    for position, section_id in enumerate(body.ids):
        sections[section_id].position = position
        session.add(sections[section_id])
    session.commit()

    return api_response(
        200,
        "Order saved",
        [HomeSectionRead.model_validate(s) for s in _load_sections(session, False)],
    )


@router.get("/list")
def list_sections(
    session: GetSession,
    user=requirePermission(PERMISSION),
):
    """Admin view — every section (inactive included) with all its banners."""
    sections = _load_sections(session, only_active=False)
    return api_response(
        200,
        "Sections found",
        [HomeSectionRead.model_validate(s) for s in sections],
        len(sections),
    )


@router.get("/public")
def public_layout(session: GetSession):
    """Storefront view — active sections, in order, with only their active
    banners (image and/or text). A banner section left with no visible banners is dropped, so
    the page never renders an empty frame."""
    result = []
    for section in _load_sections(session, only_active=True):
        read = HomeSectionRead.model_validate(section)
        # Text-only banners (info cards) are valid — require an image OR copy.
        read.banners = [
            b
            for b in read.banners
            if b.is_active and (b.image or b.title or (b.content or "").strip())
        ]
        if HomeSectionType(section.type) in BANNER_SECTION_TYPES and not read.banners:
            continue
        result.append(read)
    return api_response(200, "Home layout", result, len(result))
