from datetime import datetime, timedelta, timezone
import json
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
from src.api.core.utility import Print
from src.api.models.role_model.userRoleModel import UserRole
from src.lib.db_con import get_session
from src.lib.redis_con import cache_get, cache_set, clear_hash
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


# Cache TTL is a safety net only — the real invalidation is the explicit
# invalidate_user_session() call at every place that changes what's cached
# (profile update, role assign/unassign, shop membership change). Any code
# that changes `token_version` MUST call invalidate_user_session for that
# user, otherwise a revoked token could keep working off a stale cache entry
# until this TTL expires.
USER_SESSION_CACHE_TTL = 300  # seconds


def _user_session_key(user_id: int) -> str:
    return f"user_session:{user_id}"


def invalidate_user_session(user_id: int) -> None:
    """Call this anywhere a user's roles, shop membership, token_version, or
    profile changes — e.g. after updating a user, assigning/removing a role,
    or adding/removing them from a shop."""
    clear_hash(_user_session_key(user_id))


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
        return api_response(status.HTTP_401_UNAUTHORIZED, "Invalid token: no user data")

    if payload.get("refresh") is True:
        return api_response(401, "Refresh token is not allowed for this route")

    user_id = token_user.get("id")
    token_version = payload.get("token_version")

    # ✅ Redis cache — one hash per user, single "profile" field. A hit is
    # only trusted if its token_version still matches THIS token's payload —
    # that's what keeps "Session expired" revocation working through the cache.
    cache_key = _user_session_key(user_id)
    cached = cache_get(cache_key, "profile")
    if cached and cached.get("token_version") == token_version:
        request.state.user_data = cached
        return cached

    # single query: fetch user + roles + shop + shop_memberships + default_shop
    # together (this replaces the separate lightweight user lookup that
    # require_signin used to do just to check token_version — same check,
    # one DB round trip)
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
                selectinload(User.default_shop).load_only(Shop.id, Shop.name),
            )
            .where(User.id == user_id)
        )
        .scalars()
        .first()
    )  # Like findById
    raiseExceptions((db_user, 400, "User not found"))

    if db_user.token_version != token_version:
        return api_response(401, "Session expired. Please login again.")

    # build your user_data ONCE — flatten ORM relationship objects into plain
    # dicts so this is JSON-serializable for the cache (roles is already a
    # dict via the User.roles property, but shop/default_shop/shop_memberships
    # are still ORM objects).
    user_data = {
        "id": db_user.id,
        "email": db_user.email,
        "phone": db_user.phone or None,
        "verified": db_user.verified or False,
        "roles": db_user.roles,
        "shop": (
            db_user.shop.model_dump(include={"id", "name"}) if db_user.shop else None
        ),
        "shops_member": [
            s.model_dump(include={"id", "name"}) for s in db_user.shops_member
        ],
        "default_shop_id": db_user.default_shop_id,
        "default_shop": (
            db_user.default_shop.model_dump(include={"id", "name"})
            if db_user.default_shop
            else None
        ),
        "is_root": db_user.is_root,
        "token_version": token_version,
    }

    cache_set(cache_key, "profile", user_data, ttl=USER_SESSION_CACHE_TTL)

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

        print("====", user_permissions, flat_permissions)

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
