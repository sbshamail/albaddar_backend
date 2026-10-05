import os

from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
MEDIA_FOLDER = os.getenv("MEDIA_FOLDER", "media")
SECRET_KEY = os.getenv("SECRET_KEY")
ACCESS_TOKEN_EXPIRE_MINUTES = int(
    os.getenv(
        "ACCESS_TOKEN_EXPIRE_MINUTES",
        30,
    )
)
ACCESS_TOKEN_EXPIRE = int(
    os.getenv(
        "ACCESS_TOKEN_EXPIRE",
        30,
    )
)
DOMAIN = os.getenv("DOMAIN")

REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")

# AI providers — product-listing text generation (src/api/core/ai/).
# Model name is env-overridable since Google retires/renames model ids
# faster than this code changes (already had to bump this once).
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY")  # not wired up yet — key only, for later


# Email
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USER = os.getenv("SMTP_USER", "youremail@gmail.com")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "yourpassword")
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USER)
RESET_URL = os.getenv("RESET_URL", f"{DOMAIN}/reset-password")



AUTH_PASSWORD = os.getenv("AUTH_PASSWORD")

BCC_EMAILS = os.getenv("BCC_EMAILS")
