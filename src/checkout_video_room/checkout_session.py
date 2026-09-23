from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .infrai_client import InfraiClient


class OrderStage(StrEnum):
    CHECKOUT = "checkout"
    PAID = "paid"
    FULFILLING = "fulfilling"
    SHIPPED = "shipped"
    RECEIPT_READY = "receipt_ready"


ALLOWED_NEXT_STAGE = {
    OrderStage.CHECKOUT: OrderStage.PAID,
    OrderStage.PAID: OrderStage.FULFILLING,
    OrderStage.FULFILLING: OrderStage.SHIPPED,
    OrderStage.SHIPPED: OrderStage.RECEIPT_READY,
}


class InvalidOrderTransition(ValueError):
    pass


def require_next_stage(current: OrderStage, requested: OrderStage) -> None:
    if ALLOWED_NEXT_STAGE.get(current) != requested:
        raise InvalidOrderTransition(f"Cannot move order from {current} to {requested}")


@dataclass(frozen=True)
class OpenedSession:
    room: str
    channel: str
    token: str
    expires_in_s: int


class CheckoutSessionService:
    def __init__(self, infrai: "InfraiClient | Any") -> None:
        self._infrai = infrai

    async def open_session(
        self, order_id: str, customer_id: str, display_name: str
    ) -> OpenedSession:
        room_data = await self._infrai.create_room(order_id, max_participants=3)
        await self._infrai.create_order_channel(order_id)
        room = str(room_data.get("name", f"order-{order_id}"))
        token_data = await self._infrai.issue_room_token(
            room, customer_id, display_name, can_publish=True
        )
        return OpenedSession(
            room=room,
            channel=f"orders:{order_id}",
            token=str(token_data["token"]),
            expires_in_s=1800,
        )

    async def advance_order(
        self,
        order_id: str,
        account_id: str,
        current: OrderStage,
        requested: OrderStage,
        revision: int,
    ) -> dict[str, object]:
        require_next_stage(current, requested)
        update = {"stage": requested.value, "revision": revision}
        await self._infrai.publish_order_update(
            order_id, "order.stage_changed", update, account_id
        )
        return update
