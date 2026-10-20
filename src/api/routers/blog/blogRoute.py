import re
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlsplit

import httpx
from fastapi import APIRouter, Depends, Query
from sqlalchemy import String, cast
from sqlalchemy.orm import selectinload
from sqlmodel import func, or_, select

from src.api.core.dependencies import GetSession, ListQueryParams
from src.api.core.html_sanitizer import (
    derive_title,
    expand_media,
    has_visible_content,
    media_filenames,
    relativize_media,
    sanitize_html,
)
from src.api.core.operation import listRecords
from src.api.core.operation.media import deleteMediaFiles, download_and_save_image
from src.api.core.response import api_response, raiseExceptions
from src.api.core.security import get_user_permissions, require_signin_user
from src.api.core.utility import slugify
from src.api.models.blog_model.blogModel import (
    Blog,
    BlogCreate,
    BlogListRead,
    BlogRead,
    BlogUpdate,
)
from src.api.models.mediaModel import Media

router = APIRouter(prefix="/blog", tags=["Blog"])

PERMISSION = "blog:manage"
ADMIN_PERMISSIONS = {PERMISSION, "system:*"}

MAX_CONTENT_CHARS = 2_000_000
PUBLIC_PAGE_LIMIT = 50


# ==========================================================================
# helpers
# ==========================================================================
def _is_blog_admin(user: dict) -> bool:
    return bool(get_user_permissions(user) & ADMIN_PERMISSIONS)


def _blog_author(user: dict = Depends(require_signin_user)) -> dict:
    """Who may post: site admins (`blog:manage` / root) and any shop member
    (they post their own stock / sale news). Shop members can only touch
    their own posts — see _check_owner."""
    if _is_blog_admin(user) or user.get("default_shop"):
        return user
    return api_response(403, "Permission denied")


def _check_owner(blog: Blog, user: dict):
    if not _is_blog_admin(user) and blog.author_id != user.get("id"):
        api_response(403, "You can only change your own posts")


def _title_for(content: str, video: dict | None = None) -> str:
    """Title from the content. A post with no text takes its video's title,
    else a dated one — never a bare "New post"."""
    title = derive_title(content)
    if title == "New post":
        if video and video.get("title"):
            return video["title"][:191]
        return f"Update {datetime.now(timezone.utc):%d %b %Y}"
    return title


def _card(blog: Blog) -> BlogListRead:
    return BlogListRead.model_validate(blog)


def _read(blog: Blog) -> BlogRead:
    """ORM row → full read schema, media URLs expanded to absolute."""
    read = BlogRead.model_validate(blog)
    read.content = expand_media(read.content)
    return read


def _unique_slug(session, wanted: str, exclude_id: int | None = None) -> str:
    base = (slugify(wanted)[:100].strip("-")) or "post"
    slug, n = base, 2
    while True:
        stmt = select(Blog.id).where(Blog.slug == slug)
        if exclude_id is not None:
            stmt = stmt.where(Blog.id != exclude_id)
        if session.exec(stmt).first() is None:
            return slug
        slug = f"{base}-{n}"
        n += 1


def _clean_content(content: str) -> str:
    if len(content) > MAX_CONTENT_CHARS:
        api_response(400, "Content is too large")
    return relativize_media(sanitize_html(content))


def _resolve_cover(session, filename: str) -> dict:
    media = session.exec(select(Media).where(Media.filename == filename)).first()
    if not media:
        api_response(400, "Cover image not found — upload it first")
    return media.model_dump(include={"id", "filename", "original", "media_type"})


def _referenced_elsewhere(session, filename: str, exclude_id: int | None) -> bool:
    stmt = select(Blog.id).where(
        or_(
            Blog.content.like(f"%/media/{filename}%"),
            cast(Blog.cover_image, String).like(f"%{filename}%"),
        )
    )
    if exclude_id is not None:
        stmt = stmt.where(Blog.id != exclude_id)
    return session.exec(stmt).first() is not None


async def _free_media(session, filenames: set[str], exclude_id: int | None):
    """Delete uploaded files a post no longer uses — but only ones that are
    site uploads (no shop_id, i.e. came from /media/create) and aren't used
    by another post. A removed file can't be rolled back, so this is
    deliberately conservative."""
    if not filenames:
        return
    rows = session.exec(
        select(Media.filename).where(
            Media.filename.in_(list(filenames)), Media.shop_id.is_(None)
        )
    ).all()
    doomed = [f for f in rows if not _referenced_elsewhere(session, f, exclude_id)]
    if doomed:
        await deleteMediaFiles(session, doomed)


def _blog_media(blog: Blog) -> set[str]:
    files = media_filenames(blog.content)
    if blog.cover_image and blog.cover_image.get("filename"):
        files.add(blog.cover_image["filename"])
    thumb = (blog.video or {}).get("thumbnail")
    if thumb and thumb.get("filename"):
        files.add(thumb["filename"])
    return files


# ==========================================================================
# admin / shop members
# ==========================================================================
@router.get("/list")
def list_blogs(
    query_params: ListQueryParams,
    user=Depends(_blog_author),
):
    """Own posts for a shop member; every post for a site admin (no body)."""
    return listRecords(
        query_params=vars(query_params),
        searchFields=["title", "slug"],
        Model=Blog,
        Schema=BlogListRead,
        otherFilters=None
        if _is_blog_admin(user)
        else (lambda stmt, _Model: stmt.where(Blog.author_id == user.get("id"))),
    )


@router.get("/read/{id}")
def read_blog(
    id: int,
    session: GetSession,
    user=Depends(_blog_author),
):
    blog = session.get(Blog, id)
    raiseExceptions((blog, 404, "Post not found"))
    _check_owner(blog, user)
    return api_response(200, "Post found", _read(blog))


@router.post("/create")
async def create_blog(
    request: BlogCreate,
    session: GetSession,
    user=Depends(_blog_author),
):
    content = _clean_content(request.content)

    video = None
    if (request.video_url or "").strip():
        video = await _resolve_video(request.video_url, session)
    if not has_visible_content(content) and not request.cover_image and not video:
        api_response(400, "Write something, or add a cover image or a video link")

    title = _title_for(content, video)
    blog = Blog(
        title=title,
        slug=_unique_slug(session, title),
        content=content,
        cover_image=_resolve_cover(session, request.cover_image)
        if request.cover_image
        else None,
        video=video,
        author_id=user.get("id"),
    )
    session.add(blog)
    session.commit()
    session.refresh(blog)

    return api_response(200, "Post created", _read(blog))


@router.put("/update/{id}")
async def update_blog(
    id: int,
    request: BlogUpdate,
    session: GetSession,
    user=Depends(_blog_author),
):
    blog = session.get(Blog, id)
    raiseExceptions((blog, 404, "Post not found"))
    _check_owner(blog, user)

    data = request.model_dump(exclude_unset=True)
    if "content" in data and data["content"] is None:
        api_response(400, "content cannot be null")

    before = _blog_media(blog)

    if "content" in data:
        blog.content = _clean_content(data["content"])
    if "video_url" in data:
        url = (data["video_url"] or "").strip()
        if not url:
            blog.video = None
        elif not blog.video or blog.video.get("url") != url:
            blog.video = await _resolve_video(url, session)
    if "content" in data or "video_url" in data:
        # Title follows the text / video; the slug stays put so shared links
        # keep working.
        blog.title = _title_for(blog.content, blog.video)
    if "cover_image" in data:
        filename = data["cover_image"]
        if not filename:
            blog.cover_image = None
        elif not blog.cover_image or blog.cover_image.get("filename") != filename:
            blog.cover_image = _resolve_cover(session, filename)

    if (
        not has_visible_content(blog.content)
        and not blog.cover_image
        and not blog.video
    ):
        api_response(400, "Write something, or add a cover image or a video link")

    blog.updated_at = datetime.now(timezone.utc)
    session.add(blog)
    session.commit()
    session.refresh(blog)

    # Only after the row is safely saved: drop files the post no longer uses.
    await _free_media(session, before - _blog_media(blog), exclude_id=blog.id)
    session.commit()

    return api_response(200, "Post updated", _read(blog))


@router.delete("/delete/{id}")
async def delete_blog(
    id: int,
    session: GetSession,
    user=Depends(_blog_author),
):
    blog = session.get(Blog, id)
    raiseExceptions((blog, 404, "Post not found"))
    _check_owner(blog, user)

    files = _blog_media(blog)
    session.delete(blog)
    session.commit()

    await _free_media(session, files, exclude_id=id)
    session.commit()

    return api_response(200, "Post deleted")


# ==========================================================================
# video link → provider / id / title / thumbnail
# ==========================================================================
_YT_ID = re.compile(r"^[\w-]{11}$")
_VIMEO_ID = re.compile(r"^\d{5,12}$")
_YT_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com",
             "youtube-nocookie.com", "www.youtube-nocookie.com", "youtu.be"}
_VIMEO_HOSTS = {"vimeo.com", "www.vimeo.com", "player.vimeo.com"}


def _youtube_id(parts) -> str | None:
    host = (parts.hostname or "").lower()
    segments = [s for s in parts.path.split("/") if s]
    candidate = None
    if host == "youtu.be":
        candidate = segments[0] if segments else None
    elif segments and segments[0] in ("embed", "shorts", "live", "v"):
        candidate = segments[1] if len(segments) > 1 else None
    else:
        candidate = (parse_qs(parts.query).get("v") or [None])[0]
    return candidate if candidate and _YT_ID.match(candidate) else None


def _vimeo_id(parts) -> str | None:
    segments = [s for s in parts.path.split("/") if s]
    if segments and segments[0] == "video":  # player.vimeo.com/video/<id>
        segments = segments[1:]
    candidate = segments[0] if segments else None
    return candidate if candidate and _VIMEO_ID.match(candidate) else None


async def _oembed(client: httpx.AsyncClient, endpoint: str, params: dict) -> dict:
    try:
        res = await client.get(endpoint, params=params)
        res.raise_for_status()
        return res.json()
    except (httpx.HTTPError, ValueError):
        api_response(
            400, "Couldn't load that video — check the link and that it's public"
        )


async def _resolve_video(url: str, session) -> dict:
    """Resolve a pasted YouTube / Vimeo link.

    Confirms the video exists (the provider's public oEmbed), then downloads
    its thumbnail into our own media storage (no hotlinking). Only the fixed
    hosts above are ever fetched — never an arbitrary URL. The new Media row
    is only staged; the caller commits.
    """
    url = (url or "").strip()
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        api_response(400, "Enter a full video link starting with https://")
    host = parts.hostname.lower()

    thumb_candidates: list[str] = []

    async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
        if host in _YT_HOSTS:
            video_id = _youtube_id(parts)
            if not video_id:
                api_response(400, "That doesn't look like a YouTube video link")
            provider = "youtube"
            info = await _oembed(
                client,
                "https://www.youtube.com/oembed",
                {"url": f"https://www.youtube.com/watch?v={video_id}", "format": "json"},
            )
            thumb_candidates = [
                f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg",
                f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
            ]
            canonical = f"https://www.youtube.com/watch?v={video_id}"
        elif host in _VIMEO_HOSTS:
            video_id = _vimeo_id(parts)
            if not video_id:
                api_response(400, "That doesn't look like a Vimeo video link")
            provider = "vimeo"
            info = await _oembed(
                client,
                "https://vimeo.com/api/oembed.json",
                {"url": f"https://vimeo.com/{video_id}", "width": 1280},
            )
            remote = info.get("thumbnail_url") or ""
            if (urlsplit(remote).hostname or "").endswith("vimeocdn.com"):
                thumb_candidates = [remote]
            canonical = f"https://vimeo.com/{video_id}"
        else:
            api_response(400, "Unsupported link — use a YouTube or Vimeo link")

    title = info.get("title")
    thumb = None
    for candidate in thumb_candidates:
        thumb = await download_and_save_image(candidate, session, title=title)
        if thumb:
            break
    if not thumb:
        api_response(400, "Couldn't fetch the video's thumbnail — try another link")

    return {
        "provider": provider,
        "video_id": video_id,
        "url": canonical,
        "title": title,
        "thumbnail": thumb,  # media dict ({id, filename, original, ...})
    }


# ==========================================================================
# public (storefront)
# ==========================================================================
@router.get("/public/list")
def public_list(
    session: GetSession,
    page: int = Query(1, ge=1),
    limit: int = Query(12, ge=1, le=PUBLIC_PAGE_LIMIT),
):
    total = session.exec(select(func.count()).select_from(Blog)).one()
    rows = session.exec(
        select(Blog)
        .options(selectinload(Blog.author))
        .order_by(Blog.created_at.desc(), Blog.id.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    ).all()

    return api_response(
        200,
        "Posts found",
        [_card(b) for b in rows],
        total,
    )


@router.get("/public/{slug}")
def public_read(slug: str, session: GetSession):
    blog = session.exec(
        select(Blog).options(selectinload(Blog.author)).where(Blog.slug == slug)
    ).first()
    raiseExceptions((blog, 404, "Post not found"))
    return api_response(200, "Post found", _read(blog))
