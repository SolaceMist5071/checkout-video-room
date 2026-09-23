import asyncio

import pytest

from checkout_video_room.checkout_session import (
    CheckoutSessionService,
    InvalidOrderTransition,
    OrderStage,
)


class RecordingInfrai:
    def __init__(self) -> None:
        self.published: list[tuple[object, object, object, object]] = []

    async def publish_order_update(self, *args: object) -> dict[str, object]:
        self.published.append(args)
        return {"accepted": True}


def test_paid_order_can_enter_fulfillment() -> None:
    async def scenario() -> None:
        infrai = RecordingInfrai()
        service = CheckoutSessionService(infrai)

        result = await service.advance_order(
            "ord_1042", "shop_7", OrderStage.PAID, OrderStage.FULFILLING, 2
        )

        assert result == {"stage": "fulfilling", "revision": 2}
        assert infrai.published == [
            (
                "ord_1042",
                "order.stage_changed",
                {"stage": "fulfilling", "revision": 2},
                "shop_7",
            )
        ]

    asyncio.run(scenario())


def test_checkout_cannot_skip_to_shipping() -> None:
    async def scenario() -> None:
        infrai = RecordingInfrai()
        service = CheckoutSessionService(infrai)

        with pytest.raises(InvalidOrderTransition):
            await service.advance_order(
                "ord_1042", "shop_7", OrderStage.CHECKOUT, OrderStage.SHIPPED, 1
            )

        assert infrai.published == []

    asyncio.run(scenario())
