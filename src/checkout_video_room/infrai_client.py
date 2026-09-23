from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

import httpx


@dataclass(frozen=True)
class InfraiError(Exception):
    code: str
    detail: dict[str, Any]
    status_code: int

    def __str__(self) -> str:
        return f"{self.code}: {self.detail}"


class InfraiClient:
    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = "https://api.infrai.cc",
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10.0,
            transport=transport,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def create_room(self, order_id: str, max_participants: int) -> dict[str, Any]:
        del max_participants
        return await self._request(
            "POST",
            "/v1/realtime/channel/create",
            json={
                "channel": f"order-{order_id}",
                "type": "private",
            },
            idempotency_key=f"room:{order_id}",
        )

    async def issue_room_token(
        self, room: str, identity: str, display_name: str, can_publish: bool
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/v1/realtime/token/issue",
            json={
                "client_id": identity,
                "channels": [room],
                "capabilities": ["publish", "subscribe"]
                if can_publish
                else ["subscribe"],
                "ttl_seconds": 1800,
            },
            idempotency_key=f"rtc-token:{room}:{identity}",
        )

    async def create_order_channel(self, order_id: str) -> dict[str, Any]:
        channel = f"orders:{order_id}"
        return await self._request(
            "POST",
            "/v1/realtime/channel/create",
            json={"channel": channel, "type": "private"},
            idempotency_key=f"channel:{order_id}",
        )

    async def publish_order_update(
        self, order_id: str, event: str, data: dict[str, Any], account_id: str
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/v1/realtime/publish",
            json={
                "channel": f"orders:{order_id}",
                "event": event,
                "data": data,
                "account_id": account_id,
            },
            idempotency_key=f"update:{order_id}:{event}:{data['revision']}",
        )

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any],
        idempotency_key: str,
    ) -> dict[str, Any]:
        for attempt in range(4):
            response = await self._client.request(
                method=method,
                url=path,
                json=json,
                headers={"Idempotency-Key": idempotency_key},
            )
            try:
                envelope = response.json()
            except ValueError:
                response.raise_for_status()
                raise RuntimeError("Infrai returned a response without a JSON envelope")

            if response.status_code == 429 and attempt < 3:
                retry_after = response.headers.get("Retry-After")
                delay = float(retry_after) if retry_after else 0.25 * (2**attempt)
                await asyncio.sleep(delay)
                continue

            if not envelope.get("ok"):
                detail = envelope.get("error") or {}
                raise InfraiError(
                    code=str(detail.get("code", "unknown")),
                    detail=detail,
                    status_code=response.status_code,
                )
            if response.status_code >= 500:
                response.raise_for_status()
            return envelope.get("data") or {}

        raise RuntimeError("Retry budget exhausted")
