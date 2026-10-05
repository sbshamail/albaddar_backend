# Multi-Role / Multi-Shop Permission Model

> 📌 For the full request-by-request flow (JWT → user_data → permission
> check), see [`security_flow_docai.md`](./security_flow_docai.md). This file
> is the data model + the permission-check building blocks only.

## User Model — Relationships

```py
user_roles: list["UserRole"] = Relationship(back_populates="user")
```

## Role Model

```py
class Role(TimeStampedModel, table=True):
    __tablename__ = "roles"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=50, unique=True)
    slug: str = Field(max_length=60, unique=True, index=True)
    description: Optional[str] = None
    permissions: list[str] = Field(
        default_factory=list,
        sa_type=JSON,
    )
    user_id: int = Field(foreign_key="users.id")
    is_active: bool = Field(default=True)

    # relationships
    user_roles: list["UserRole"] = Relationship(back_populates="role")

    @property
    def roles(self):
        """Return roles directly (not UserRole objects)."""
        return [ur.role for ur in self.user_roles if ur.role]
```

## UserRole — Join Table (many-to-many between User and Role)

A `Role` can carry a `shop_id` (see `require_shop_permission` below), which is
what makes the same user able to hold different roles on different shops —
"Shop Admin" on shop A, plain "Member" on shop B, etc.

```py
if TYPE_CHECKING:
    from src.api.models.userModel import User
    from src.api.models.role_model.roleModel import Role


class UserRole(TimeStampedModel, table=True):
    __tablename__ = "user_roles"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id")
    role_id: int = Field(foreign_key="roles.id")

    # relationships
    user: "User" = Relationship(back_populates="user_roles")
    role: "Role" = Relationship(back_populates="user_roles")
```

## Security — Permission-Check Building Blocks

All of these depend on `require_signin_user` (defined in
`src/api/core/security.py`), which does ONE DB query — decode JWT, fetch the
user with roles/shop/shop_memberships eagerly loaded via `selectinload`, and
check `token_version` — then caches the result on `request.state` for the
rest of the request. See `operation_security_docai.md`'s Security section for
the full current implementation; the snippets below are just the
permission-check helpers built on top of it.

```py
def get_user_permissions(user: dict) -> set[str]:
    roles = user.get("roles", [])

    permissions = set()
    for role in roles:
        permissions.update(role.get("permissions", []))

    return permissions


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

        # ✅ Match ANY permission
        if any(p in user_permissions for p in permissions):
            return user

        return api_response(403, "Permission denied")

    return permission_checker


# Shop-scoped variant — a Role can carry a shop_id, so this only grants
# access when the matching role's shop_id equals the caller's default shop.
def require_shop_permission(*permissions: str):
    def checker(user: dict = Depends(require_default_shop)):
        default_shop = user.get("default_shop")
        default_shop_id = (
            default_shop["id"] if isinstance(default_shop, dict) else default_shop.id
        )

        roles = user.get("roles", [])
        user_permissions = get_user_permissions(user)

        for role in roles:
            if role.get("shop_id") != default_shop_id:
                continue
            if "shop:*" in user_permissions:
                return user
            if any(p in user_permissions for p in permissions):
                return user

        return api_response(403, "Permission denied")

    return checker
```

## Test Auth

```py
@router.get("/testauth", response_model=dict)
def test_auth(
    user: requireSignin,
):
    return api_response(
        200,
        "Token is valid",
        {"user": user},
    )


@router.get("/testadmin")
def get_admin_data(
    user: requireAdmin,
):

    return {"message": f"Hello Admin {user['email']}", "user": user}


@router.get("/testpermission")
def get_admin_data(
    user=requirePermission("system:*"),
):
    return {"message": f"Hello Admin {user}"}

```
