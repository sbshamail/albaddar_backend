from datetime import datetime, timedelta, timezone
from random import randint

from fastapi import Response

from src.config import ACCESS_TOKEN_EXPIRE_MINUTES, DOMAIN, SECRET_KEY
from src.api.core.security import (
    create_access_token,
    decode_token,
)
from src.api.core.smtp import send_email
from src.api.models.userModel import User, UserRead
from sqlmodel import select


def validate_default_shop(user_dict):
    default_shop = user_dict.default_shop

    if not default_shop:
        return None

    shop = user_dict.shop
    shops_member = user_dict.shop_memberships

    if shop and shop.id == default_shop.id:
        return default_shop.id

    if shops_member and any(s.shop_id == default_shop.id for s in shops_member):
        return default_shop.id

    return None


def exist_verified_email(session, email: str) -> bool:

    user = session.exec(
        select(User.id).where(
            User.email == email,
            User.email_verified == True,
        )
    ).first()
    return True if user else False


def send_verification_email(user: User) -> None:
    token = create_access_token({"id": user.id, "email": user.email})
    verify_url = f"{DOMAIN}/verify/verify-email?token={token}"

    with open("src/templates/email_verification.html") as f:
        html_template = f.read().replace("{{VERIFY_URL}}", verify_url)

    send_email(
        to_email=user.email,
        subject="Verify Your Email Address",
        body=html_template,
    )


def generate_and_send_otp(
    session, user: User, purpose: str, subject: str, message: str
) -> None:
    """Shared by register-otp and login-otp. `purpose` is embedded in the
    token so a code sent for one flow can't be replayed to complete the
    other (they share the single `use_token` slot on the user row)."""
    otp = f"{randint(100000, 999999)}"
    data = {"otp": otp, "email": user.email, "purpose": purpose}
    otp_token = create_access_token(user_data=data, expires=timedelta(minutes=10))
    user.use_token = otp_token
    session.add(user)
    session.commit()

    send_email(
        to_email=user.email,
        subject=subject,
        body=f"{message} {otp} (valid for 10 minutes)",
    )


def issue_login_tokens(user: User, response: Response) -> dict:
    """Shared by password login and OTP login — same token pair, cookie,
    and response shape either way."""
    # JWT payload stays minimal (just the id) — require_signin_user fetches
    # the full profile (roles, shop, permissions) fresh from the DB on every
    # request, so it can't go stale between login and token expiry.
    user_data = {"id": user.id}

    access_token = create_access_token(
        user_data=user_data, token_version=user.token_version
    )
    refresh_token = create_access_token(
        user_data=user_data,
        token_version=user.token_version,
        refresh=True,
    )

    exp_time = datetime.now(timezone.utc) + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )
    # cookie will test in postman and frontend only with tag credential:true
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        samesite="strict",
        max_age=30 * 24 * 60 * 60,  # 30 days
    )

    return {
        "message": "Login successful",
        "token_type": "bearer",
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user": UserRead.model_validate(user),
        "exp": exp_time.isoformat(),
    }


def verify_otp(user: User, otp: str, purpose: str) -> bool:
    if not user.use_token:
        return False
    decoded = decode_token(user.use_token)
    if not decoded:
        return False
    data = decoded.get("user", {})
    return (
        data.get("otp") == otp
        and data.get("email") == user.email
        and data.get("purpose") == purpose
    )
