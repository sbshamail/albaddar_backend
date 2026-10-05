from typing import Annotated, Any, Dict, Optional

from fastapi import Depends, Query
from sqlmodel import Session

from src.api.core.dependencies.query_params import list_query_params
from src.lib.db_con import get_session
from src.api.core.security import (
    is_authenticated,
    require_permission,
    require_shop_admin,
    require_default_shop,
    require_shop_permission,
    require_signin,
    require_admin,
    verified_user,
)


GetSession = Annotated[Session, Depends(get_session)]

requireSignin = Annotated[dict, Depends(require_signin)]
requireAdmin = Annotated[dict, Depends(require_admin)]
verifiedUser = Annotated[dict, Depends(verified_user)]
isAuthenticated = Annotated[dict | None, Depends(is_authenticated)]
ListQueryParams = Annotated[dict, Depends(list_query_params)]
requireDefaultShop = Annotated[dict, Depends(require_default_shop)]
requireShopAdmin = Annotated[dict, Depends(require_shop_admin)]


def requirePermission(*permissions: str):
    return Depends(require_permission(*permissions))


def requireShopPermission(*permissions: str):
    return Depends(require_shop_permission(*permissions))
