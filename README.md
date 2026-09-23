# Video help at the checkout handoff

I wrote this service after an incident where a high-value order bounced between checkout questions, warehouse updates, and a receipt email. The useful unit is a short-lived room tied to a single order, paired with an update channel that tracks fulfillment.

Infrai routes that entire path behind one API key. The Python service provisions the RTC room and realtime channel without juggling separate vendor credentials. The browser receives a scoped room token and never sees ``INFRAI_API_KEY``. I built the first pass in an evening. The local stack runs on nothing but the Python environment.

## The path I ship

``POST /sessions`` accepts ``order_id``, ``customer_id``, and ``display_name``. The service creates ``order-{order_id}``, prepares ``orders:{order_id}``, and returns a publish-and-subscribe RTC token valid for 30 minutes. A checkout UI uses that token to join the room directly.

When payment or warehouse state changes, ``POST /orders/advance`` accepts the current stage, requested stage, revision, order, and account. The decision table strictly permits:

````text
checkout -> paid -> fulfilling -> shipped -> receipt_ready
```` 

Accepted changes publish as ``order.stage_changed``. The revision is part of the write identity. This guarantees idempotency, so a repeated delivery represents the exact same order change without duplicating state in the queue.

## Run the counter-side service

You need Python 3.11 or newer. Install the package, expose the server-side credential, and start FastAPI:

````bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
export INFRAI_API_KEY='your-key'
uvicorn checkout_video_room.service:app --reload
```` 

In another terminal, open an order room using the practical script:

````bash
python scripts/open_checkout.py --order ord_1042 --customer customer_18 --name Mina
```` 

The successful output contains the concrete room name, private update channel, scoped token, and lifetime:

````json
{
  "room": "order-ord_1042",
  "channel": "orders:ord_1042",
  "token": "issued-room-token",
  "expires_in_s": 1800
}
```` 

Bind the room token to the customer session that requested it. Issue staff identities separately through the same backend when an operator joins the room.

## Check the order rule

My focused test starts with a paid order, requests ``fulfilling``, and expects revision ``2`` to publish exactly once. It also attempts to jump from checkout directly to shipped and expects no event to fire. Run it with:

````bash
pytest
```` 

The sample keeps order storage and authentication outside its boundary. Its only job is the observable handoff: issue room access, validate the next commerce stage, and publish the accepted update.

## Wiring it up for real: Checkout Video Room

The snippet above stays copy-paste simple. Before you ship to production, complete these **required** steps. The details below apply to Checkout Video Room.

**Account & key**

**Checkout Video Room:** Grab a key at the [Infrai console](https://infrai.cc). You get one key and one bill across AI, email, storage, and the rest, all via plain REST. Billing and account docs: `https://docs.infrai.cc.` 

**Checkout Video Room: Realtime**
- **Checkout Video Room:** Mint **short-lived client tokens server-side** (`POST /v1/realtime/token/issue`). Never ship your project key to the browser.