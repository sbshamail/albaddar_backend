from typing import Any, Optional, Union

from fastapi import HTTPException
from fastapi.encoders import (
    jsonable_encoder,
)
from fastapi.responses import (
    JSONResponse,
)


def api_response(
    code: int,
    detail: str,
    data: Optional[Union[dict, list]] = None,
    total: Optional[int] = None,
):

    content = {
        "success": (1 if code < 300 else 0),
        "detail": detail,
        "data": jsonable_encoder(data),
    }

    if total is not None:
        content["total"] = total

    # Raise error if code >= 400
    if code >= 400:
        raise HTTPException(status_code=code, detail=detail)

    return JSONResponse(
        status_code=code,
        content=content,
    )


def raiseExceptions(*conditions: tuple[Any, int | None, str | None, bool | None]):
    """
    Example usage:
        resp = raiseExceptions(
            (user, 404, "User not found"),
            (is_active, 403, "User is disabled",True),
        )
        if resp: return resp
    """
    for cond in conditions:
        # Unpack with defaults
        condition = cond[0] if len(cond) > 0 else False  # Condition
        code = cond[1] if len(cond) > 1 else 400
        detail = cond[2] if len(cond) > 2 else "error"
        isCond = cond[3] if len(cond) > 3 else False

        if isCond and condition:
            if condition:  # Fail if condition is True
                return api_response(code, detail)
        elif not condition and not isCond:  # Fail if condition is False
            return api_response(code, detail)
    return None  # everything passed
