"""Allowlist HTML sanitizer for admin-authored rich text that the storefront
renders with `dangerouslySetInnerHTML` (blog posts).

The editor (Tiptap) only ever emits a small, known set of tags — so instead
of trusting whatever a client posts, anything outside that set is dropped
here before it is stored. Rebuilt from a parse (not regex-stripped), so
malformed / nested tricks can't smuggle a tag through.

Also holds the small helpers that go with it: media-URL normalisation (the
DB stores `/media/<file>`; clients get `<DOMAIN>/media/<file>`), plain-text
extraction and reading time.
"""

import math
import re
from html import escape, unescape
from html.parser import HTMLParser
from typing import Optional
from urllib.parse import urlsplit

from src.config import DOMAIN

# ---------------------------------------------------------------- allowlist
ALLOWED_TAGS = {
    "p", "br", "hr",
    "h1", "h2", "h3", "h4", "h5", "h6",
    "strong", "b", "em", "i", "u", "s", "strike", "code", "pre",
    "blockquote",
    "ul", "ol", "li",
    "a", "img",
    "figure", "figcaption",
}
VOID_TAGS = {"br", "hr", "img"}
# Tags whose whole subtree is discarded (not just the tag itself).
DROP_WITH_CONTENT = {
    "script", "style", "iframe", "object", "embed", "noscript", "template",
    "svg", "math", "textarea", "select", "form", "button", "audio", "video",
    "applet", "frame", "frameset",
}

_CONTROL = re.compile(r"[\x00-\x20\x7f]")
_DIGITS = re.compile(r"^\d{1,5}$")
_CODE_CLASS = re.compile(r"^language-[\w-]{1,30}$")


def _safe_url(value: str, *, allow_mailto: bool = False) -> Optional[str]:
    """http(s) or a single-slash site-relative path; never javascript:/data:."""
    value = value.strip()
    compact = _CONTROL.sub("", value).lower()
    if not compact:
        return None
    if compact.startswith("//"):
        return None  # scheme-relative → points at an arbitrary host
    if compact.startswith(("/", "#")):
        return value
    scheme = urlsplit(compact).scheme
    allowed = {"http", "https"} | ({"mailto", "tel"} if allow_mailto else set())
    return value if scheme in allowed else None


def _clean_attr(tag: str, name: str, value: str) -> Optional[str]:
    if tag == "a":
        if name == "href":
            return _safe_url(value, allow_mailto=True)
        if name == "title":
            return value
        if name == "target":
            return "_blank" if value == "_blank" else None
    elif tag == "img":
        if name == "src":
            return _safe_url(value)
        if name in ("alt", "title"):
            return value
        if name in ("width", "height"):
            return value if _DIGITS.match(value) else None
    elif tag == "code" and name == "class":
        return value if _CODE_CLASS.match(value) else None
    elif tag == "ol" and name == "start":
        return value if _DIGITS.match(value) else None
    return None


class _Sanitizer(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self.stack: list[str] = []  # open allowed tags, for balanced output
        self.dropping = 0  # >0 while inside a DROP_WITH_CONTENT subtree
        self.drop_tag: Optional[str] = None

    # -- tags
    def handle_starttag(self, tag, attrs):
        if self.dropping:
            if tag == self.drop_tag:
                self.dropping += 1
            return
        if tag in DROP_WITH_CONTENT:
            self.dropping, self.drop_tag = 1, tag
            return
        if tag not in ALLOWED_TAGS:
            return  # unwrap: keep the text, lose the tag

        clean: dict[str, str] = {}
        for name, raw in attrs:
            if raw is None:
                continue
            value = _clean_attr(tag, name.lower(), raw)
            if value is not None:
                clean[name.lower()] = value

        if tag == "a":
            if "href" not in clean:
                return  # an anchor without a usable href is just text
            if clean.get("target") == "_blank":
                clean["rel"] = "noopener noreferrer"
        if tag == "img":
            if "src" not in clean:
                return
            clean["loading"] = "lazy"

        attr_str = "".join(f' {k}="{escape(v, quote=True)}"' for k, v in clean.items())
        self.out.append(f"<{tag}{attr_str}>")
        if tag not in VOID_TAGS:
            self.stack.append(tag)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID_TAGS:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if self.dropping:
            if tag == self.drop_tag:
                self.dropping -= 1
                if not self.dropping:
                    self.drop_tag = None
            return
        if tag not in ALLOWED_TAGS or tag in VOID_TAGS or tag not in self.stack:
            return
        # close anything left open above the matching tag, then the tag itself
        while self.stack:
            top = self.stack.pop()
            self.out.append(f"</{top}>")
            if top == tag:
                break

    # -- text
    def handle_data(self, data):
        if not self.dropping:
            self.out.append(escape(data, quote=False))

    # comments / doctype / PIs: ignored by default (never emitted)

    def result(self) -> str:
        while self.stack:
            self.out.append(f"</{self.stack.pop()}>")
        return "".join(self.out)


def sanitize_html(html: Optional[str]) -> str:
    if not html:
        return ""
    parser = _Sanitizer()
    parser.feed(html)
    parser.close()
    return parser.result()


# ------------------------------------------------------------- media URLs
_DOMAIN = (DOMAIN or "").rstrip("/")
_MEDIA_ATTR_ABS = re.compile(r'(\b(?:src)=")' + re.escape(_DOMAIN) + r"/media/") if _DOMAIN else None
_MEDIA_ATTR_REL = re.compile(r'(\b(?:src)=")/media/')
_MEDIA_FILE = re.compile(r"/media/([A-Za-z0-9._\-]+)")


def relativize_media(html: str) -> str:
    """`https://api…/media/x.webp` → `/media/x.webp` before storing, so a
    domain change never breaks stored posts."""
    if not html or _MEDIA_ATTR_ABS is None:
        return html
    return _MEDIA_ATTR_ABS.sub(r"\1/media/", html)


def expand_media(html: str) -> str:
    """Inverse of relativize_media, applied on every read."""
    if not html or not _DOMAIN:
        return html
    return _MEDIA_ATTR_REL.sub(lambda m: f"{m.group(1)}{_DOMAIN}/media/", html)


def media_filenames(html: Optional[str]) -> set[str]:
    return set(_MEDIA_FILE.findall(html or ""))


# --------------------------------------------------------------- plain text
_TAGS = re.compile(r"<[^>]+>")


def plain_text(html: Optional[str]) -> str:
    text = unescape(_TAGS.sub(" ", html or ""))
    return re.sub(r"\s+", " ", text).strip()


def has_visible_content(html: Optional[str]) -> bool:
    """True if the post has any text or an image."""
    if not html:
        return False
    return bool(plain_text(html)) or "<img" in html


# ------------------------------------------------------------ SEO helpers
# The post form is just cover + content, so everything search engines see is
# derived from the (already sanitised) content: headings give the title,
# the first paragraph gives the description.
_HEADING = re.compile(r"<h[1-3]\b[^>]*>(.*?)</h[1-3]>", re.S | re.I)
_BLOCK = re.compile(r"<(p|h[1-6]|li|blockquote)\b[^>]*>(.*?)</\1>", re.S | re.I)
_PARAGRAPH = re.compile(r"<(p|blockquote)\b[^>]*>(.*?)</\1>", re.S | re.I)


def _cut(text: str, limit: int) -> str:
    """Cut on a word boundary, adding an ellipsis."""
    if len(text) <= limit:
        return text
    cut = text[: limit - 1]
    space = cut.rfind(" ")
    return (cut[:space] if space > limit // 2 else cut).rstrip(".,;:- ") + "…"


def derive_title(html: Optional[str], limit: int = 80) -> str:
    """First h1–h3 heading, else the first line of text (h1/h2 are what search
    engines weigh most, so a heading is the best title when there is one)."""
    for pattern in (_HEADING, _BLOCK):
        for match in pattern.finditer(html or ""):
            text = plain_text(match.group(match.lastindex))
            if len(text) >= 3:
                return _cut(text, limit)
    return "New post"


def derive_summary(html: Optional[str], limit: int = 160) -> Optional[str]:
    """First real paragraph (headings skipped) — the meta description."""
    for match in _PARAGRAPH.finditer(html or ""):
        text = plain_text(match.group(2))
        if len(text) >= 20:
            return _cut(text, limit)
    text = plain_text(html)
    return _cut(text, limit) if text else None
