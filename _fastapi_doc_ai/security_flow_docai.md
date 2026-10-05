# Security Flow — How Auth & Permissions Actually Work

This explains the *flow*: what runs, in what order, and why — for every
request that needs a logged-in user. The code itself lives in
`src/api/core/security.py` and is referenced (not duplicated) from
`operation_security_docai.md` and `multi_roles.md`.

## It's not "middleware" in the Starlette sense

There's no `app.add_middleware(...)` doing auth here. This project uses
FastAPI's **dependency injection** as the security layer instead — each
protected route declares a dependency (e.g. `user: requireSignin`), and
FastAPI resolves that dependency *before* your route function runs. If the
dependency raises, your route body never executes. That's why this doc calls
it "security middleware" loosely — it behaves like middleware (runs before
the handler, can short-circuit the request), but it's implemented as a chain
of `Depends()` functions in `src/api/core/security.py`, wired to short names
in `src/api/core/dependencies/__init__.py` (`requireSignin`, `requireAdmin`,
`requireShopPermission(...)`, etc.).

## Step 1 — Login issues a JWT

`POST /login` (in `authRoute.py`) verifies the password, then calls
`create_access_token(user_data, token_version=user.token_version)`. The JWT
payload is deliberately **minimal** — just `{"id": user.id}` — plus
`token_version` and an expiry. It does NOT carry roles, permissions, or shop
info. This matters: those things change (a role gets revoked, a shop
membership changes) and the token can't be "un-issued" once handed out, so
the token only proves *who you claim to be* — every request re-fetches the
*current* roles/permissions from the DB rather than trusting a stale JWT
payload.

A `refresh_token` (30-day expiry, `refresh=True` in payload) is set as an
httponly cookie and also returned in the login response body.

## Step 2 — Every protected request decodes the JWT and loads the user

This is the one function nearly everything else builds on:

```
require_signin_user(request, credentials, session)
```

What it does, in order:
1. Decode the JWT from the `Authorization: Bearer <token>` header.
2. Reject if the token is a refresh token (`refresh: true` can't be used as an access token).
3. Run **one** DB query: fetch the `User` row with `roles → role`,
   `shop`, and `shop_memberships → shop` all eagerly loaded via
   `selectinload(...)`.
4. Check `db_user.token_version == payload["token_version"]` — this is the
   session-invalidation check: if the user changed their password or was
   logged out server-side, `token_version` gets bumped, and every
   already-issued JWT instantly stops working even though it hasn't expired.
5. Build a plain `dict` (`user_data`) with everything downstream checks need:
   `roles`, `shop`, `shops_member`, `default_shop`, `default_shop_id`,
   `is_root`, etc.
6. **Cache it on `request.state.user_data`.** If a route depends on more than
   one security function in the same request (e.g. `requireShopPermission`
   depends on `require_default_shop` which depends on
   `require_signin_user`), the DB only gets hit once per request no matter
   how many guards stack.

> Earlier version of this function depended on a separate `require_signin`
> call that did its own lightweight DB lookup just to check `token_version`,
> then this function ran a second, heavier query for the same user right
> after — two round trips for one user. It's now merged into a single query.

## Step 3 — Everything else is a permission check layered on top

```
require_signin_user  ──┬─→ require_admin            ("is this user an admin?")
                        ├─→ require_permission(...)   ("does this user have permission X?")
                        └─→ require_shop_admin         ("is this user 'shop:*' admin on their default shop?")
                        └─→ require_default_shop  ──┬─→ require_shop_permission(...)
                                                     │    ("does this user have permission X on their default shop?")
```

- `require_signin` — a **separate**, lighter path (does NOT go through
  `require_signin_user`). Decodes the JWT and confirms the user row still
  exists + `token_version` matches, but returns only the raw token payload,
  not the full profile. Used when a route just needs "is this a valid,
  non-revoked login" and nothing about roles/shop (e.g. `/testauth`).
- `require_admin` — true only if the user has the `"root"` role, or
  `is_root`, or the `"system:*"` permission.
- `require_permission(*perms)` — global (not shop-scoped) permission check.
  `"system:*"` is always a match-anything shortcut.
- `require_default_shop` — just checks the user *has* a `default_shop` set
  (no permission check yet — it's the shop-scoped equivalent of
  `require_signin_user`, other shop checks build on it).
- `require_shop_admin` — true only if one of the user's roles has
  `shop_id == default_shop_id` AND the permission set includes `"shop:*"`.
- `require_shop_permission(*perms)` — like `require_permission`, but scoped:
  only roles whose `shop_id` matches the caller's `default_shop_id` are
  considered. A "shop:*" role match short-circuits; otherwise any of the
  named permissions must be present on a matching role.

## Where the short names come from

`src/api/core/dependencies/__init__.py` wraps the raw functions into
`Annotated[...]` type aliases so routes can write clean type hints instead
of `Depends(...)` everywhere:

```py
requireSignin      = Annotated[dict, Depends(require_signin)]
requireAdmin       = Annotated[dict, Depends(require_admin)]
requireDefaultShop = Annotated[dict, Depends(require_default_shop)]
requireShopAdmin   = Annotated[dict, Depends(require_shop_admin)]

def requirePermission(*permissions: str):
    return Depends(require_permission(*permissions))

def requireShopPermission(*permissions: str):
    return Depends(require_shop_permission(*permissions))
```

`requirePermission`/`requireShopPermission` are functions (not plain
aliases) because they take arguments — each route passes the specific
permission string(s) it requires, e.g.
`user=requireShopPermission(["product:create"])`.

## Known cost, and why Redis is coming next

Every authenticated request pays for the auth chain even when nothing about
the user changed since their last request one second ago:
- 1 query in `require_signin_user` (with 3 `selectinload` sub-queries under
  the hood: roles→role, shop, shop_memberships→shop — so really ~4 round
  trips, not 1).
- Then whatever the route itself needs (e.g. `listRecords`'s count + data
  queries).

None of that is wasted work exactly — it's always *correct* (never trusts a
stale token claim) — but it's the same ~4 DB round trips on every single
request from the same logged-in user, which is real latency if the DB isn't
on the same host. The planned fix: cache the resolved `user_data` dict in
Redis, keyed by user id (or by token), with a short TTL or invalidated
on logout / password change / role change. That turns the "always re-fetch"
guarantee into "re-fetch at most once per TTL window, or immediately on any
change that actually matters" — same correctness, far fewer round trips.
