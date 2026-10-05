# Initialize the FastAPI app with the custom lifespan
from fastapi import FastAPI, Request
from fastapi.openapi.docs import get_swagger_ui_html

from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.exc import IntegrityError
from os import getenv
from pydantic import ValidationError
from sqlmodel import SQLModel, create_engine

from src.config import DATABASE_URL
from src.api.routers.product import productRoute, productVariantRoute, productAiRoute
from src.api.routers.order import OrderRoute, orderItemRoute
from src.api.routers.dashboard import dashboardRoute

from src.api.routers.category import categoryRoute
from src.api.routers.home import bannerRoute, homeSectionRoute
from src.api.routers.auth.role_route import (
    roleRoute,
    shopRoleRoute,
    userRoleRoute,
    shopUserRoleRoute,
)
from src.api.routers.shop import shopRoute, shopChildRoute
from src.api.routers.auth import (
    authRoute,
    userRoute,
    verifymeRoute,
)
from src.api.routers.cart import cartRoute, cartItemRoute

from src.api.routers import addressRoute, mediaRoute

# DATABASE_URL = getenv("DATABASE_URL", "sqlite:///./database.db")
# engine = create_engine(DATABASE_URL, echo=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Runs once on startup ---
    # print("🟢 Checking if tables exist...")

    # # Create all tables that are missing (safe – only creates non-existent ones)
    # SQLModel.metadata.create_all(engine)
    # print("✅ All tables verified / created.")
    # # --- Runs once on shutdown ---
    # print("🔴 App shutting down...")

    yield  # 👈 after this, FastAPI starts handling requests


app = FastAPI(
    lifespan=lifespan,
    root_path="/api",
    docs_url=None,
)
# Local dev origins (exact match) + buyagain.pk and any of its subdomains
# (allow_origins only matches exact strings — wildcard subdomains need
# allow_origin_regex instead; CORSMiddleware allows a request if it matches
# either list).
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:3002",
        "http://localhost:3003",
    ],
    # (:\d+)? — an optional trailing port, so a subdomain accessed with a
    # non-default port (e.g. test.buyagain.pk:3000 for local dev via
    # /etc/hosts) still matches; without it the Origin header's port made
    # this regex reject an otherwise-correct buyagain.pk subdomain.
    allow_origin_regex=r"^https?://([a-zA-Z0-9-]+\.)*buyagain\.pk(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(ValidationError)
async def validation_exception_handler(request: Request, exc: ValidationError):
    return JSONResponse(
        status_code=422, content={"data": exc.errors(), "message": "Validation failed"}
    )


@app.exception_handler(IntegrityError)
async def integrity_exception_handler(request: Request, exc: IntegrityError):
    msg = str(exc.orig)
    if "duplicate key" in msg or "UNIQUE constraint failed" in msg:
        error_msg = "Duplicate entry — record already exists."
    elif "violates not-null constraint" in msg:
        error_msg = "Required field missing in database insert."
    else:
        error_msg = "Database integrity error."
    return JSONResponse(status_code=422, content={"data": msg, "message": error_msg})


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    # This catches model assignment errors like "User has no field ..."
    if "has no field" in str(exc):
        message = str(exc).split('"')[-2] + " is not a valid field name."
    else:
        message = str(exc)

    print(message)
    return JSONResponse(
        status_code=400,
        content={"message": message},
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    return JSONResponse(status_code=400, content={"message": str(exc)})


@app.get("/")
def root():
    return {"message": "Hello, FastAPI with uv!"}


@app.get("/docs", include_in_schema=False)
async def custom_docs():
    html = get_swagger_ui_html(openapi_url=app.openapi_url, title="Dark API Docs")

    # Inject dark CSS manually
    dark_css = """
    <style>
        body {
            background-color: #121212;
            color: #ffffff;
        }
        .swagger-ui {
            filter: invert(1) hue-rotate(270deg);
        }
        .swagger-ui img {
            filter: invert(1) hue-rotate(270deg);
        }
        
    </style>
    """

    return HTMLResponse(
        html.body.decode("utf-8").replace("</head>", dark_css + "</head>")
    )


# auth
app.include_router(authRoute.router)
app.include_router(userRoute.router)
app.include_router(verifymeRoute.router)
app.include_router(mediaRoute.router)
# relate
app.include_router(addressRoute.router)
# role
app.include_router(roleRoute.router)
app.include_router(userRoleRoute.router)
app.include_router(shopRoleRoute.router)
app.include_router(shopUserRoleRoute.router)
# main
app.include_router(shopRoute.router)
app.include_router(shopChildRoute.router)
app.include_router(categoryRoute.router)
app.include_router(productRoute.router)
app.include_router(productVariantRoute.router)
app.include_router(productAiRoute.router)
app.include_router(cartRoute.router)
app.include_router(cartItemRoute.router)
app.include_router(OrderRoute.router)
app.include_router(orderItemRoute.router)
app.include_router(dashboardRoute.router)
app.include_router(homeSectionRoute.router)
app.include_router(bannerRoute.router)
