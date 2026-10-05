from fastapi import APIRouter
from sqlmodel import select

from src.api.core.dependencies import GetSession, ListQueryParams, requireSignin
from src.api.core.operation import listRecords, updateOp
from src.api.core.response import api_response, raiseExceptions
from src.api.models.addressModel import (
    AddressCreate,
    AddressRead,
    AddressUpdate,
    UserAddress,
)

router = APIRouter(prefix="/address", tags=["Address"])


def _clear_default_addresses(
    session: GetSession,
    user_id: int,
    skip_id: int | None = None,
):
    statement = select(UserAddress).where(
        UserAddress.user_id == user_id,
        UserAddress.default == 1,
    )
    if skip_id is not None:
        statement = statement.where(UserAddress.id != skip_id)

    for address in session.exec(statement).all():
        address.default = 0
        session.add(address)


def _has_user_address(session: GetSession, user_id: int) -> bool:
    return (
        session.exec(
            select(UserAddress.id).where(UserAddress.user_id == user_id)
        ).first()
        is not None
    )


@router.post("/create", response_model=AddressRead)
def create_address(
    request: AddressCreate,
    user: requireSignin,
    session: GetSession,
):
    has_address = _has_user_address(session, user["id"])
    is_default = (
        request.default if request.default is not None else (0 if has_address else 1)
    )

    if is_default == 1:
        _clear_default_addresses(session, user["id"])

    address = UserAddress(
        user_id=user["id"],
        address=request.address.model_dump(),
        location=request.location.model_dump() if request.location else None,
        default=is_default,
    )
    session.add(address)
    session.commit()
    session.refresh(address)

    return api_response(
        200,
        "Address created successfully",
        AddressRead.model_validate(address),
    )


@router.put("/update/{id}", response_model=AddressRead)
def update_address(
    id: int,
    request: AddressUpdate,
    user: requireSignin,
    session: GetSession,
):
    address = session.get(UserAddress, id)
    resp = raiseExceptions(
        (address, 404, "Address not found"),
        (address and address.user_id != user["id"], 403, "Access denied", True),
    )
    if resp:
        return resp

    if request.default == 1:
        _clear_default_addresses(session, user["id"], skip_id=id)

    updateOp(address, request, session)
    session.commit()
    session.refresh(address)

    return api_response(
        200,
        "Address updated successfully",
        AddressRead.model_validate(address),
    )


@router.post("/set-default/{id}", response_model=AddressRead)
def set_default_address(
    id: int,
    user: requireSignin,
    session: GetSession,
):
    address = session.get(UserAddress, id)
    resp = raiseExceptions(
        (address, 404, "Address not found"),
        (address and address.user_id != user["id"], 403, "Access denied", True),
    )
    if resp:
        return resp

    _clear_default_addresses(session, user["id"], skip_id=id)
    address.default = 1
    session.add(address)
    session.commit()
    session.refresh(address)

    return api_response(
        200,
        "Default address updated successfully",
        AddressRead.model_validate(address),
    )


@router.get("/read/{id}", response_model=AddressRead)
def read_address(
    id: int,
    user: requireSignin,
    session: GetSession,
):
    address = session.get(UserAddress, id)
    resp = raiseExceptions(
        (address, 404, "Address not found"),
        (address and address.user_id != user["id"], 403, "Access denied", True),
    )
    if resp:
        return resp

    return api_response(200, "Address found", AddressRead.model_validate(address))


@router.get("/list")
def list_addresses(
    user: requireSignin,
    query_params: ListQueryParams,
):
    query_params = vars(query_params)
    return listRecords(
        query_params=query_params,
        searchFields=[],
        Model=UserAddress,
        Schema=AddressRead,
        customFilters=[["user_id", user["id"]]],
    )


@router.delete("/delete/{id}")
def delete_address(
    id: int,
    user: requireSignin,
    session: GetSession,
):
    address = session.get(UserAddress, id)
    resp = raiseExceptions(
        (address, 404, "Address not found"),
        (address and address.user_id != user["id"], 403, "Access denied", True),
    )
    if resp:
        return resp

    was_default = address.default == 1
    session.delete(address)
    session.flush()

    if was_default:
        next_address = session.exec(
            select(UserAddress)
            .where(UserAddress.user_id == user["id"])
            .order_by(UserAddress.created_at.asc())
        ).first()
        if next_address:
            next_address.default = 1
            session.add(next_address)

    session.commit()

    return api_response(200, "Address deleted successfully")
