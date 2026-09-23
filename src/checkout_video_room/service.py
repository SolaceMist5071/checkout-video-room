from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .checkout_session import (
    CheckoutSessionService,
    InvalidOrderTransition,
    OrderStage,
)
from .infrai_client import InfraiClient, InfraiError


class OpenSessionRequest(BaseModel):
    order_id: str = Field(min_length=1)
    customer_id: str = Field(min_length=1)
    display_name: str = Field(min_length=1, max_length=80)


class OpenSessionResponse(BaseModel):
    room: str
    channel: str
    token: str
    expires_in_s: int


class OrderUpdateRequest(BaseModel):
    order_id: str = Field(min_length=1)
    account_id: str = Field(min_length=1)
    current_stage: OrderStage
    requested_stage: OrderStage
    revision: int = Field(ge=1)


class OrderUpdateResponse(BaseModel):
    stage: str
    revision: int


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    api_key = os.environ.get("INFRAI_API_KEY")
    if not api_key:
        raise RuntimeError("Set INFRAI_API_KEY before starting the service")
    client = InfraiClient(api_key)
    app.state.sessions = CheckoutSessionService(client)
    yield
    await client.close()


app = FastAPI(title="Checkout video room", lifespan=lifespan)


def sessions(request: Request) -> CheckoutSessionService:
    return request.app.state.sessions


@app.exception_handler(InfraiError)
async def infrai_error_handler(request: Request, exc: InfraiError):
    del request
    status = exc.status_code if 400 <= exc.status_code < 500 else 502
    return JSONResponse(
        status_code=status, content={"detail": {"code": exc.code, "error": exc.detail}}
    )


@app.post("/sessions", response_model=OpenSessionResponse, status_code=201)
async def open_session(
    body: OpenSessionRequest,
    service: CheckoutSessionService = Depends(sessions),
) -> OpenSessionResponse:
    opened = await service.open_session(
        body.order_id, body.customer_id, body.display_name
    )
    return OpenSessionResponse(**opened.__dict__)


@app.post("/orders/advance", response_model=OrderUpdateResponse)
async def advance_order(
    body: OrderUpdateRequest,
    service: CheckoutSessionService = Depends(sessions),
) -> OrderUpdateResponse:
    try:
        update = await service.advance_order(
            body.order_id,
            body.account_id,
            body.current_stage,
            body.requested_stage,
            body.revision,
        )
    except InvalidOrderTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return OrderUpdateResponse.model_validate(update)
