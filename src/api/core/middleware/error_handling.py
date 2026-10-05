from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import IntegrityError, OperationalError
import re

from src.api.core.response import api_response


def register_exception_handlers(app):

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ):
        return api_response(422, "Validation error", data={"errors": exc.errors()})

    @app.exception_handler(IntegrityError)
    async def integrity_exception_handler(request: Request, exc: IntegrityError):
        msg = str(exc.orig) if exc.orig else str(exc)
        if "duplicate key value violates unique constraint" in msg:
            m = re.search(r"Key \((.*?)\)=\((.*?)\)", msg)
            if m:
                field, value = m.groups()
                msg = f"Duplicate entry: {field} = {value}"
            else:
                msg = "Duplicate key violation"
        return api_response(409, msg)

    @app.exception_handler(OperationalError)
    async def operational_exception_handler(request: Request, exc: OperationalError):
        return api_response(503, "Database unavailable, try again later")

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception):
        print(f"[ERROR] {exc}")  # or use logging
        return api_response(500, "Internal Server Error")
