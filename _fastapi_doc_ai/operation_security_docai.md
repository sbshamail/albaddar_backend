# My way to code Fastapi Doc Ai For Operation,Security Func, Media etc

## in this project we use latest fastapi method, uv package manager, sql model for schemas

## Operations

//=========================================

## Update Operation

// =======================================

```
from src.api.core.operation import listRecords, updateOp
```

```py
# Update only the fields that are provided in the request
# customFields = ["phone", "firstname", "lastname", "email"]
def updateOp(
    instance,
    request,
    session,
    customFields=None,
):
    # CASE 1: Only update custom fields
    if customFields:
        for field in customFields:
            if hasattr(request, field):
                value = getattr(request, field)
                if value is not None:
                    setattr(instance, field, value)

    else:
        # CASE 2: Auto-update all fields
        # Handle both Pydantic models AND plain classes
        if hasattr(request, "model_dump"):
            # Pydantic / SQLModel
            data = request.model_dump(exclude_unset=True)
        else:
            # Plain Class: extract fields with vars()
            data = {
                key: value for key, value in vars(request).items() if value is not None
            }

        # Apply updates
        for key, value in data.items():
            if hasattr(instance, key):  # if the key is in the model
                setattr(instance, key, value)

    # Update timestamp
    if hasattr(instance, "updated_at"):
        instance.updated_at = datetime.now(timezone.utc)

    session.add(instance)
    return instance

```

<!-- //////////////////////////////////// -->

# Scalor

<!-- ////////////////////////////////////////// -->

```py
def _exec(session, statement, Model):
    result = session.exec(statement)
    # If it's already Model objects, just return .all()
    if isinstance(result, ScalarResult):  # SQLAlchemy 2.x ScalarResult
        return result.all()
    else:
        # Fallback: try scalars (for select(Model))
        try:
            return result.scalars().all()
        except Exception:
            return result.all()
```

<!-- /////////////////////////////////////////// -->

# Media

<!-- ///////////////////////////////////////////// -->

```py
# Model
class Media(TimeStampedModel, table=True):
    __tablename__ = "media"
    id: Optional[int] = Field(default=None, primary_key=True)
    filename: str
    extension: str
    original: str
    media_type: str  # "image" | "video" | "doc"
    size_mb: Optional[float] = Field(default=None)
    thumbnail: Optional[str] = Field(default=None)
    # Which shop this media belongs to (products/variants pass this through
    # so media can be scoped/filtered/cleaned-up per shop later).
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

# Reusable Function
import os
import time
from src.api.core.response import api_response
from PIL import Image, UnidentifiedImageError, ImageOps
from starlette.datastructures import UploadFile

from src.api.core.dependencies import GetSession
from src.api.models.mediaModel import Media
from sqlalchemy import func
import os
from typing import Any, List, Optional, TypedDict, Union
from sqlmodel import select

BASE_DIR = "/var/www"
SUB_DIR = "buyagainmedia"
MEDIA_DIR = os.path.join(BASE_DIR, SUB_DIR)

ALLOWED_RAW_EXT = [".webp", ".avif", ".ico", ".svg"]
MAX_SIZE = 2 * 1024 * 1024  # 1 MB
THUMBNAIL_SIZE = (300, 300)  # max width/height
MAX_SIZE_MB = MAX_SIZE / (1024 * 1024)


class MediaType(TypedDict):
    filename: str
    extension: str
    original: str
    size_mb: float
    thumbnail: Optional[str]
    media_type: str

def entryMedia(
    session: GetSession, files: List[MediaType], shop_id: Optional[int] = None
):
    records = []
    for file_info in files:
        existing_media = session.scalar(
            select(Media).where(Media.filename == file_info["filename"])
        )

        if existing_media:
            # ✅ Update existing record
            existing_media.extension = file_info["extension"]
            existing_media.original = file_info["original"]
            existing_media.size_mb = file_info["size_mb"]
            existing_media.thumbnail = file_info.get("thumbnail")
            existing_media.media_type = "image"
            # Only overwrite shop_id when a caller actually passes one —
            # otherwise an unrelated re-upload of the same filename would
            # silently null out an existing shop_id.
            if shop_id is not None:
                existing_media.shop_id = shop_id
            session.add(existing_media)
            records.append(existing_media)
        else:
            # ✅ Create new record
            media = Media(
                filename=file_info["filename"],
                extension=file_info["extension"],
                original=file_info["original"],
                size_mb=file_info["size_mb"],
                thumbnail=file_info.get("thumbnail"),
                media_type="image",
                shop_id=shop_id,
            )
            session.add(media)
            session.flush()  # ensures ID assigned
            records.append(media)
    return records


async def uploadImage(files, thumbnail, unique=True):
    saved_files = []

    for file in files:
        original_name = os.path.splitext(file.filename)[0]
        ext = os.path.splitext(file.filename)[1].lower()

        timestamp = str(int(time.time() * 1000))

        # Apply unique filename BEFORE any conversion
        if unique:
            base_name = f"{original_name}-{timestamp}"
        else:
            base_name = original_name

        # RAW image handling
        if ext in ALLOWED_RAW_EXT:
            with open(file_path, "wb") as buffer:
                buffer.write(await file.read())
        else:
            try:
                img = Image.open(file.file)
                icc_profile = img.info.get("icc_profile")

                img = ImageOps.exif_transpose(img)

                # Convert to webp with unique naming
                output_filename = base_name + ".webp"
                file_path = os.path.join(MEDIA_DIR, output_filename)

                img.save(
                    file_path,
                    "webp",
                    quality=95,
                    method=6,
                    icc_profile=icc_profile,
                    lossless=False,
                )
                ext = ".webp"

            except UnidentifiedImageError:
                raise api_response(
                    400,
                    f"File type {ext} is not a supported image format.",
                )

        # Validate file size
        size_bytes = os.path.getsize(file_path)
        if size_bytes > MAX_SIZE:
            os.remove(file_path)
            size_mb = round(size_bytes / (1024 * 1024), 2)
            return api_response(
                400,
                f"{file.filename} is still larger than {MAX_SIZE_MB} MB after optimization ({size_mb} MB)",
            )

        # File info response
        file_info = {
            "filename": os.path.basename(file_path),
            "extension": ext,
            "original": f"/media/{os.path.basename(file_path)}",
            "size_mb": round(size_bytes / (1024 * 1024), 2),
        }

        # Thumbnail creation
        if thumbnail and ext in [".jpg", ".jpeg", ".png", ".webp"]:
            thumb_name = base_name + "_thumb.webp"
            thumb_path = os.path.join(MEDIA_DIR, thumb_name)

            with Image.open(file_path) as thumb:
                thumb.thumbnail(THUMBNAIL_SIZE)
                thumb.save(
                    thumb_path,
                    "webp",
                    quality=85,
                    method=6,
                )

            file_info["thumbnail"] = f"/media/{thumb_name}"

        saved_files.append(file_info)

    return saved_files


def delete_media_items(
    session: GetSession,
    ids: Optional[List[int]] = None,
    filenames: Optional[List[str]] = None,
) -> dict:
    """
    Delete media by IDs or filenames.
    - Skips deletion for media referenced in MediaTrack.
    - Removes files + thumbnails from disk and deletes DB rows.
    Returns a dict with deleted and skipped items.
    """
    if not ids and not filenames:
        raise ValueError("Must provide either ids or filenames to delete.")

    stmt = select(Media)
    if ids:
        stmt = stmt.where(Media.id.in_(ids))
    if filenames:
        stmt = stmt.where(
            func.lower(Media.filename).in_([f.lower() for f in filenames])
        )

    media_records = session.exec(stmt).all()
    if not media_records:
        return {"deleted": [], "skipped": [], "message": "No matching media found."}

    deleted_files = []

    for media in media_records:
        # --- Delete original file ---
        file_path = os.path.join(MEDIA_DIR, media.filename)
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass  # silently ignore file deletion error

        # -------------------------
        # Delete thumbnail
        # -------------------------
        if media.thumbnail:
            thumb_path = os.path.join(MEDIA_DIR, os.path.basename(media.thumbnail))
        else:
            base, _ = os.path.splitext(media.filename)
            thumb_path = os.path.join(MEDIA_DIR, f"{base}_thumb.webp")

        if os.path.exists(thumb_path):
            try:
                os.remove(thumb_path)
            except Exception:
                pass  # ignore thumbnail deletion error

        # --- Remove from DB ---
        session.delete(media)
        deleted_files.append(media.filename)

    session.flush()

    message = "Media deletion completed."

    return {
        "deleted": deleted_files,
        "message": message,
    }


async def uploadSingleMedia(file, session, shop_id: Optional[int] = None):
    if isinstance(file, UploadFile):
        files = [file]
        saved_files = await uploadImage(files, thumbnail=False)

        records = entryMedia(session, saved_files, shop_id=shop_id)

        return records[0].model_dump(
            include={"id", "filename", "original", "media_type"}
        )

    if isinstance(file, str):  # URL should be string, not URL type
        statement = select(Media).where(Media.filename == file)
        media = session.exec(statement).first()

        if media:
            return media.model_dump(
                include={"id", "filename", "original", "media_type"}
            )
    return None


# ⚠️ Must return plain dicts (via model_dump), same as uploadSingleMedia —
# these results get JSON-encoded straight into a JSON column later. Returning
# raw ORM `Media` objects here caused "Object of type Media is not JSON
# serializable" on product create (multi-image field), since the caller had
# no reason to re-serialize a value that already looked "done".
async def uploadMultiMedia(files, session, shop_id: Optional[int] = None):
    if isinstance(files, list):
        saved_files = await uploadImage(files, thumbnail=False)
        records = entryMedia(session, saved_files, shop_id=shop_id)
        return [
            r.model_dump(include={"id", "filename", "original", "media_type"})
            for r in records
        ]


async def uploadMediaFiles(session, data: dict, request, shop_id: Optional[int] = None):
    for field, new_value in vars(request).items():

        # skip empty
        if new_value is None:
            continue

        # -------------------------
        # SINGLE FILE
        # -------------------------
        if isinstance(new_value, (UploadFile, str)):
            uploaded = await uploadSingleMedia(new_value, session, shop_id=shop_id)

            if uploaded:
                data[field] = uploaded

        # -------------------------
        # MULTI FILE
        # -------------------------
        elif isinstance(new_value, list):
            if any(isinstance(i, UploadFile) for i in new_value):

                uploaded_list = await uploadMultiMedia(
                    new_value, session, shop_id=shop_id
                )

                if uploaded_list:
                    data[field] = uploaded_list

    return data


async def deleteMediaFiles(
    session,
    *files: Union[dict, str, List[Union[dict, str]], None],
):
    filenames_to_delete: List[str] = []

    def extract_filename(file: Any):
        if not file:
            return

        # Case 1: dict (your stored media)
        if isinstance(file, dict):
            filename = file.get("filename")
            if filename:
                filenames_to_delete.append(filename)

        # Case 2: string (filename)
        elif isinstance(file, str):
            filenames_to_delete.append(file)

        # Case 3: list (multiple files)
        elif isinstance(file, list):
            for f in file:
                extract_filename(f)

    # loop over all inputs
    for file in files:
        extract_filename(file)

    # remove duplicates
    filenames_to_delete = list(set(filenames_to_delete))

    # delete if exists
    if filenames_to_delete:
        return delete_media_items(session, filenames=filenames_to_delete)

    return {"deleted": [], "message": "No files to delete"}


```

<!-- ///////////////////////////////// -->

# How to Use of Media in Form

<!-- ///////////////////////////////////// -->

> ⚠️ **Gotcha:** never type a multi-file field as `Optional[List[UploadFile]] = File(None)`.
> That makes the OpenAPI schema nullable (`anyOf`), and Swagger UI falls back to
> rendering a plain text box instead of a file-upload widget — anything typed into
> that box then fails validation on the backend. Use `List[UploadFile] = File(default_factory=list)`
> instead: still optional (empty list when nothing is sent), but keeps a clean
> "array of file" schema so Swagger renders real file pickers.

```py
class UserRideForm:
    def __init__(
        self,
        # file upload
        car_pic: Optional[Union[UploadFile, str]] = File(None),
        other_images: List[UploadFile] = File(default_factory=list),
        delete_images: Optional[List[str]] = Form(None),
    ):
        # Convert empty → None
        # Convert empty string → None
        def clean(v):
            if v is None:
                return None
            if isinstance(v, str) and v.strip() == "":
                return None
            return v

        # Convert "true"/"false"/"1"/"0" → boolean
        def to_bool(v):
            v = clean(v)
            if v is None:
                return None
            val = str(v).lower()
            if val in ["true", "1", "yes"]:
                return True
            if val in ["false", "0", "no"]:
                return False
            return None  # fallback

        # Convert JSON string → dict
        def clean_json(v):

            v = clean(v)
            if v is None:
                return None
            try:
                return json.loads(v)
            except Exception:
                raise ValueError(f"Invalid JSON: {v}")

        # Convert to int
        def to_int(v):
            v = clean(v)
            if v is None:
                return None
            try:
                return int(v)
            except:
                return None

        # Convert to float
        def to_float(v):
            v = clean(v)
            if v is None:
                return None
            try:
                return float(v)
            except:
                return None

        # Assign fields
        # normalize empty string → None
        self.car_pic = car_pic

        # ✅ Better normalization
        self.other_images = other_images or []  # ✅ Simple fallback

        self.delete_images = clean(delete_images)

```

//=========================================

## Security

// =======================================

> 📌 For the conceptual flow (what calls what, and why), see
> [`security_flow_docai.md`](./security_flow_docai.md). This section is just
> the current reference implementation.

```py
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from passlib.context import CryptContext
from jose import JWTError, jwt
from sqlalchemy import select
from sqlmodel import Session
from fastapi import (
    Depends,
    HTTPException,
    Header,
    Request,
    Security,
    status,
)
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer,
)


from src.api.models.shop_model.shopModel import Shop
from src.api.models.role_model.roleModel import Role
from src.api.models.shop_model.ShopChildModel import ShopUser
from src.api.models.role_model.userRoleModel import UserRole
from src.lib.db_con import get_session
from src.api.models.userModel import User, UserRead
from sqlalchemy.orm import selectinload


from src.config import SECRET_KEY, ACCESS_TOKEN_EXPIRE
from src.api.core.response import api_response, raiseExceptions


ALGORITHM = "HS256"

pwd_context = CryptContext(
    schemes=["argon2"],
    deprecated="auto",
)


## get user
def exist_user(db: Session, email: str):
    from src.api.models.userModel import User

    user = db.exec(select(User).where(User.email == email)).first()
    return user


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(
    user_data: dict,
    token_version: Optional[int] = None,
    refresh: Optional[bool] = False,
    expires: Optional[timedelta] = None,
):

    if refresh:
        expire = datetime.now(timezone.utc) + timedelta(days=30)
    else:
        expire = datetime.now(timezone.utc) + (
            expires or timedelta(days=ACCESS_TOKEN_EXPIRE)
        )

    payload = {
        "user": user_data,
        "exp": int(expire.timestamp()),
        "refresh": refresh,
        "token_version": token_version,
    }
    token = jwt.encode(
        payload,
        SECRET_KEY,
        algorithm=ALGORITHM,
    )
    return token


def verify_refresh_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


def decode_token(
    token: str,
) -> Optional[Dict]:
    try:
        decode = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM],
            options={"verify_exp": True},  # Ensure expiration is verified
        )

        return decode

    except JWTError as e:
        print(f"Token decoding failed: {e}")
        return None


def is_authenticated(authorization: Optional[str] = Header(None)):
    """
    Extract user from Bearer token.
    Return None if token is missing or invalid.
    """
    if not authorization:
        return None  # No token means offline or guest user

    # Expect format: "Bearer <token>"
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None

    token = parts[1]
    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM],
            options={"verify_exp": True},  # verifies expiration
        )
        user = payload.get("user")
        return user
    except JWTError:
        return None


# require_signin: light check only — decode + confirm the DB row still
# exists and token_version matches (session-invalidation check). Used
# standalone where you only need "is this a valid, non-revoked token", not
# the full profile (e.g. is_authenticated-style routes).
def require_signin(
    session: Session = Depends(get_session),
    credentials: HTTPAuthorizationCredentials = Security(HTTPBearer()),
) -> Dict:
    token = credentials.credentials  # Extract token from Authorization header

    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM],
        )
        user = payload.get("user")

        if user is None:
            api_response(
                status.HTTP_401_UNAUTHORIZED,
                "Invalid token: no user data",
            )
        db_user = session.get(User, user["id"])
        if db_user is None:
            api_response(
                status.HTTP_401_UNAUTHORIZED,
                "Invalid token: no user data",
            )

        if payload.get("refresh") is True:
            api_response(
                401,
                "Refresh token is not allowed for this route",
            )

        if db_user.token_version != payload.get("token_version"):
            return api_response(401, "Session expired. Please login again.")

        return user

    except JWTError as e:
        print(e)
        return api_response(status.HTTP_401_UNAUTHORIZED, "Invalid token", data=str(e))


# require_signin_user: the workhorse most permission checks build on.
# Decodes the JWT itself (does NOT depend on require_signin — that used to
# cause a duplicate user lookup, one lightweight query in require_signin
# just to check token_version, then this function ran a second, heavier
# query for the same user right after). Now it's ONE query total: fetch the
# user plus roles → role, shop, and shop_memberships → shop, all via
# selectinload, then check token_version against the already-loaded row.
# Also caches onto `request.state` so multiple Depends() in the same
# request (e.g. a route depending on both requireSignin-style checks and a
# permission check) don't re-hit the DB.
def require_signin_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Security(HTTPBearer()),
    session: Session = Depends(get_session),
):
    # ✅ CACHE inside request (IMPORTANT)
    if hasattr(request.state, "user_data"):
        return request.state.user_data

    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError as e:
        return api_response(status.HTTP_401_UNAUTHORIZED, "Invalid token", data=str(e))

    token_user = payload.get("user")
    if token_user is None:
        return api_response(
            status.HTTP_401_UNAUTHORIZED, "Invalid token: no user data"
        )

    if payload.get("refresh") is True:
        return api_response(
            401, "Refresh token is not allowed for this route"
        )

    user_id = token_user.get("id")

    db_user = (
        session.exec(
            select(User)
            .options(
                selectinload(User.user_roles)
                .selectinload(UserRole.role)
                .load_only(
                    Role.id,
                    Role.name,
                    Role.permissions,
                    Role.is_active,
                ),
                selectinload(User.shop).load_only(Shop.id, Shop.name),
                selectinload(User.shop_memberships)
                .selectinload(ShopUser.shop)
                .load_only(Shop.id, Shop.name),
            )
            .where(User.id == user_id)
        )
        .scalars()
        .first()
    )  # Like findById
    raiseExceptions((db_user, 400, "User not found"))

    if db_user.token_version != payload.get("token_version"):
        return api_response(401, "Session expired. Please login again.")

    # build your user_data ONCE
    user_data = {
        "id": db_user.id,
        "email": db_user.email,
        "phone": db_user.phone or None,
        "verified": db_user.verified or False,
        "roles": db_user.roles,
        "shop": db_user.shop,
        "shops_member": db_user.shop_memberships,
        "default_shop_id": db_user.default_shop_id,
        "default_shop": db_user.default_shop,
        "is_root": db_user.is_root,
    }

    # 🔥 store in request cache
    request.state.user_data = user_data

    return user_data


def verified_user(user: dict = Depends(require_signin_user)):
    if user.get("verified") is False or user.get("phone") is None:
        api_response(
            status.HTTP_423_LOCKED,
            "User is not verified",
        )
    return user


# fn
def get_user_permissions(user: dict) -> set[str]:
    roles = user.get("roles", [])

    permissions = set()
    for role in roles:
        permissions.update(role.get("permissions", []))

    return permissions


# fn
def has_role(user: dict, role_name: str) -> bool:
    roles = user.get("roles", [])
    return any(r.get("name") == role_name for r in roles)


def require_admin(
    user: dict = Depends(require_signin_user),
):
    try:
        roles = user.get("roles", [])

        if not roles and not user.get("is_root"):
            return api_response(
                status.HTTP_401_UNAUTHORIZED,
                "Access denied: no roles found",
            )

        user_permissions = get_user_permissions(user)

        # ✅ Admin logic
        if (
            not has_role(user, "root")
            and user.get("is_root") is False
            and "system:*" not in user_permissions
        ):
            return api_response(
                status.HTTP_403_FORBIDDEN,
                "Access denied: Admins only",
            )

        return user

    except JWTError:
        return api_response(
            status.HTTP_401_UNAUTHORIZED,
            "Invalid or expired token",
        )


def require_permission(*permissions: str):
    def permission_checker(
        user: dict = Depends(require_signin_user),
    ):
        roles = user.get("roles", [])

        if not roles:
            return api_response(403, "Permission denied")

        user_permissions = get_user_permissions(user)

        # ✅ admin shortcut
        if "system:*" in user_permissions:
            return user

            # 🔥 Flatten if someone passed list
        flat_permissions = []
        for p in permissions:
            if isinstance(p, list):
                flat_permissions.extend(p)
            else:
                flat_permissions.append(p)

        # ✅ Match ANY permission
        if any(p in user_permissions for p in flat_permissions):
            return user

        return api_response(403, "Permission denied")

    return permission_checker


def require_shop_admin(user: dict = Depends(require_signin_user)):
    default_shop = user.get("default_shop")

    if not default_shop:
        api_response(403, "No active shop selected")

    default_shop_id = (
        default_shop["id"] if isinstance(default_shop, dict) else default_shop.id
    )

    roles = user.get("roles", [])

    user_permissions = get_user_permissions(user)

    is_admin = any(
        "shop:*" in user_permissions and r.get("shop_id") == default_shop_id
        for r in roles
    )

    if not is_admin:
        api_response(403, "Shop admin access required")

    return user


def require_default_shop(user: dict = Depends(require_signin_user)):
    default_shop = user.get("default_shop")

    if not default_shop:
        api_response(403, "No active shop selected")

    return user


def require_shop_permission(*permissions: str):
    def checker(user: dict = Depends(require_default_shop)):
        default_shop = user.get("default_shop")

        default_shop_id = (
            default_shop["id"] if isinstance(default_shop, dict) else default_shop.id
        )

        roles = user.get("roles", [])

        user_permissions = get_user_permissions(user)

        # ✅ admin shortcut
        for role in roles:
            if role.get("shop_id") != default_shop_id:
                continue
            if role.get("shop_id") == default_shop_id and "shop:*" in user_permissions:
                return user

            flat_permissions = []
            for p in permissions:
                if isinstance(p, list):
                    flat_permissions.extend(p)
                else:
                    flat_permissions.append(p)

            if any(p in user_permissions for p in flat_permissions):
                return user

        api_response(403, "Permission denied")

    return checker

```
