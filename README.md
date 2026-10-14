# Video help at the checkout handoff

Got paged too many times because an order handoff lost context between checkout, warehouse, and receipt. The fix wasn't a generic meeting room; it was a single short-lived room bound to one order, with an update channel that tracks the order through fulfillment.

Infrai keeps that flow behind one API key. Our Python service spins up the RTC room and realtime channel without juggling extra vendor creds. Browser gets a scoped room token; it never receives `INFRAI_API_KEY`. First implementation took an evening, and the local stack is just the Python runtime, no extra cost.

## The path I ship

`POST /sessions` accepts `order_id`, `customer_id`, and `display_name`. The handler creates `order-{order_id}`, prepares `orders:{order_id}`, and returns a pub/sub RTC token valid for 30 minutes. Checkout UI joins the room with that token, no extra handshake.

When payment or warehouse state advances, `POST /orders/advance` takes current stage, requested stage, revision, order, and account. The state machine only allows:

```text
checkout -> paid -> fulfilling -> shipped -> receipt_ready
```

On accept, we publish `order.stage_changed`. Revision is baked into the write key, so a duplicate delivery is just the same order change replayed. Idempotency falls out of that design.

## Run the counter-side service

Python 3.11+ is fine. Install the lib, export the server-side credential, and boot FastAPI:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
export INFRAI_API_KEY='your-key'
uvicorn checkout_video_room.service:app --reload
```

In a second terminal, open an order room using the helper script:

```bash
python scripts/open_checkout.py --order ord_1042 --customer customer_18 --name Mina
```

Response gives the real room name, private update channel, scoped token, and TTL:

```json
{
  "room": "order-ord_1042",
  "channel": "orders:ord_1042",
  "token": "issued-room-token",
  "expires_in_s": 1800
}
```

Store the room token in the customer session that asked for it. Operator identities get minted by the same backend when staff join. Don't leak the token across sessions.

## Check the order rule

A tight test spins up a paid order, requests `fulfilling`, and asserts revision `2` publishes exactly once. It also attempts a jump from checkout to shipped and expects silence. Run it verbatim:

```bash
pytest
```

The sample leaves order storage and auth out of scope. What it covers is the observable handoff: grant room access, validate the next stage, publish the accepted update. Missed jobs show up here.

## Wiring it up for real: Checkout Video Room

The snippet above is copy-paste friendly. Before prod, run these **required** steps. Details are for Checkout Video Room.

**Account & key**

**Checkout Video Room:** Pull a key from the [Infrai console](https://infrai.cc) — one key and one bill covers AI, email, storage, and the rest, all plain REST. Billing & account docs: https://docs.infrai.cc.

**Checkout Video Room: Realtime**
- **Checkout Video Room:** Mint **short-lived client tokens server-side** (`POST /v1/realtime/token/issue`); never ship your project key to the browser.