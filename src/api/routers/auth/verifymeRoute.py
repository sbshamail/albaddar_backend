from fastapi import APIRouter
from sqlmodel import delete, select
from src.api.core.response import api_response
from src.api.core.security import decode_token
from src.api.core.dependencies import GetSession
from src.api.models.userModel import User

router = APIRouter(prefix="/verify", tags=["verify"])


@router.get("/verify-email")
def verify_email(token: str, session: GetSession):
    decode = decode_token(token)
    if not decode:
        return api_response(400, "Invalid or expired verification token")

    user_data = decode.get("user")
    if not user_data:
        return api_response(400, "Invalid token payload")

    user = session.exec(select(User).where(User.email == user_data["email"])).first()

    if not user:
        return api_response(400, "Invalid or expired verification token")

    # Already verified → idempotent success
    if user.email_verified:
        return api_response(200, "Email already verified")

    user.email_verified = True
    session.add(user)

    # ✅ DELETE all other unverified users with same email
    session.exec(
        delete(User).where(
            User.email == user.email,
            User.email_verified == False,
            User.id != user.id,
        )
    )

    session.commit()
    session.refresh(user)

    return api_response(200, "Email verified successfully!")
