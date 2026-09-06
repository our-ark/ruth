# Ruth shopping demo

Status: proposed demo design; this document does not implement the integration.

The user starts shopping with `/shop` in Telegram. Ruth searches two registered
applications, sends recommendations to Telegram, and continues the same
conversation inside either application. Each reply returns to the application
session that supplied its user message. The demo does not track visits, tab
focus, or a global current application.

## Architecture

Arrows below describe operations and data flow. Ruth initiates all calls to
application APIs; applications do not call a public Ruth endpoint.

<a href="diagrams/shopping-architecture.png"><img src="diagrams/shopping-architecture.png" alt="Ruth architecture: Telegram connects to one Ruth conversation; Ruth calls two apps with shared collaboration and shopping interfaces." width="600"></a>

[Full-size PNG](diagrams/shopping-architecture.png) ·
[Scalable SVG](diagrams/shopping-architecture.svg)

The overview separates Ruth's responsibilities from each app's interfaces.
The API table below gives the routes and payloads.

## Demo components

| Component | Responsibility |
| --- | --- |
| Telegram `/shop <request>` | Create a shopping task using the request, such as running shoes under $80. An incomplete request can be clarified in the continuing conversation. |
| Static registry | Describe the two supported apps and their configured account connections. No discovery service or central relay is required. |
| Shopping tools | Query candidates, inspect product details, and place a simulated order through the selected app's ordinary APIs. |
| Application message polling | Read both apps' user-message feeds while the shopping task is active. Empty polls do not invoke model reasoning. |
| Shared conversation | Retain preferences, recommendations, comparisons, and source-qualified product references across Telegram and both apps. |
| Reply routing | Post each answer to the original message's app and session. Telegram-originated turns receive Telegram replies. |
| App frontend and backend | Render the app's own chat UI, capture message-time page context, queue messages, and display Ruth's outputs. Each app may retain its own domain logic or AI. |

The implementation can begin with one demo user, one active shopping task, and
two preconnected app accounts. Those account bindings associate each app feed
with the same Ruth conversation; clicking a product link alone does not establish
that identity. Authentication setup is outside the recorded demo.

## Static registry

Keep the registry local to Ruth. Each entry contains:

- `app_id` and display name;
- `base_url` for the app-hosted interfaces;
- a reference to locally stored credentials for the connected app account;
- supported product/order operations, if the two apps need different adapters.

Use the same endpoint schemas in both demo apps. Their catalogs, storefronts,
and chat presentation can differ. A product reference always includes
`app_id` and `product_id`; product IDs alone need not be globally unique.

## Two collaboration endpoints, three shopping operations

Message delivery and context exchange are the paper's two semantic contracts.
For this demo, the contracts share two HTTP operations, following the paper's
compact example. Product and order operations are ordinary app APIs.

| Operation | Proposed route | Demo payload / result |
| --- | --- | --- |
| Receive user messages and app context | `GET /collaboration/events?after={cursor}` | A finite batch of queued user messages, each bound to its session and message-time context; next cursor. |
| Deliver Ruth replies and selected user context | `POST /collaboration/sessions/{id}/outputs` | Reply text, `in_reply_to`, stable output ID, and optional authorized context for the app. |
| `queryProduct` | `GET /products?q=...` | Candidate IDs, names, prices, availability, and canonical product links; optional budget, size, and category filters. |
| `getProduct` | `GET /products/{product_id}` | Details for a candidate or currently selected product, including variants and current price. |
| `orderProduct` | `POST /orders` | Product/variant, quantity, and an idempotency key; returns a simulated order ID and status. |

Example message event:

```json
{
  "event_id": "evt-a-017",
  "session_id": "session-a-01",
  "message": {
    "id": "msg-a-017",
    "text": "How does this compare with the pair from the other store?"
  },
  "context": {
    "revision": "ctx-a-042",
    "page_type": "product",
    "product_id": "shoe-17",
    "selected_variant": "size-9-blue"
  }
}
```

Ruth identifies the app and connected user from the configured, authenticated
feed. The session and product IDs remain app-scoped. App context is evidence
about the page, not permission to access or disclose unrelated private memory.

The context snapshot travels with the message. No continuous page or presence
reporting is needed. In the opposite direction, Ruth can return selected context,
such as the user's shopping budget, for app-owned filtering or presentation.
The complete private conversation is not copied into each application's store.

## End-to-end flow

The sequence is split into three images so each step can be read without a
wide or nested diagram viewport.

### 1. Start shopping

The user sends `/shop running shoes under $80` in Telegram. Ruth loads both
registered app connections, starts polling, queries their catalogs, and sends
recommendations with product links.

<a href="diagrams/shopping-kickoff.png"><img src="diagrams/shopping-kickoff.png" alt="Shopping kickoff: Telegram request, registry setup, two-app product queries, and recommendations." width="600"></a>

[Full-size PNG](diagrams/shopping-kickoff.png) ·
[Scalable SVG](diagrams/shopping-kickoff.svg)

### 2. Continue in App A or App B

The user opens App A and asks, "Is this suitable?" Later, in App B, they ask,
"Better than the first?" Both apps use the flow below. Ruth combines the new
message's page context with the continuing conversation, including the earlier
App A comparison. Each reply returns to the message's source session.

<a href="diagrams/shopping-conversation.png"><img src="diagrams/shopping-conversation.png" alt="App conversation: the UI queues a message and context; Ruth polls the app, reasons with shared memory, and posts its reply back." width="600"></a>

[Full-size PNG](diagrams/shopping-conversation.png) ·
[Scalable SVG](diagrams/shopping-conversation.svg)

### 3. Order and notify

The user asks the selected app's chat to order a specific pair and size. Ruth
receives that request through the polling flow above, retrieves current product
details, and places the authorized simulated order. Results go to the source
app session and Telegram before polling stops.

<a href="diagrams/shopping-order.png"><img src="diagrams/shopping-order.png" alt="Order completion: retrieve product details, place a simulated order, deliver results to the app and Telegram, and stop polling." width="600"></a>

[Full-size PNG](diagrams/shopping-order.png) ·
[Scalable SVG](diagrams/shopping-order.svg)

All diagrams have checked-in PNG previews and standalone SVG versions. Their
editable drawing source is [render_shopping_demo.py](diagrams/render_shopping_demo.py).

## Routing and lifecycle rules

1. Start polling both registered app accounts before sending recommendations.
   A one-second interval per app is a proposed demo default, not a measured
   latency guarantee.
2. Polling consumes messages, not presence. An explicit message supplies its
   own reply address: `(app_id, session_id, message_id)`.
3. If the user switches tabs while an answer is pending, that answer still goes
   to its source session. A subsequent message in the other app continues the
   conversation there. No global `current_app` is needed.
4. Serialize reasoning turns for the single demo user. Deduplicate inbound
   event IDs and outbound output IDs, preserving cursors across retries. Order
   calls use an idempotency key to avoid duplicate simulated purchases.
5. Recommendations use products and links returned by app APIs. Resolve an
   order to the requested product and variant; clarify missing details or
   material changes before proceeding. Product APIs remain authoritative for
   price, inventory, and order status.
6. After order completion and final output delivery, or explicit cancellation,
   stop app polling. Telegram remains available. Later app messages wait until
   app polling is resumed, for example by another `/shop` command. The demo ends
   with the order notification.

## What the demo shows

- One Ruth conversation continues through Telegram, App A, and App B.
- Current product context grounds phrases such as "this pair"; retained
  conversation context grounds "the first pair" across apps.
- Different app and chat UIs use the same collaboration contracts.
- Ruth obtains product facts and performs a requested simulated purchase using
  ordinary app APIs, then reports the result on Telegram.

Automatic tracking of app visits, proactive relocation of pending replies,
dynamic app discovery, real payment processing, and concurrent shopping tasks
are outside this initial demo. The broader architecture remains described in
[Application collaboration](app-collaboration.md).
