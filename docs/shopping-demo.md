# Run the One Agent, Anywhere prototype

This is the reference shopping implementation of
[UAAP — User–Agent–App Protocol](../protocol/README.md), with Ruth as the
persistent personal agent and DAYFORM/STRIDE as participating applications.
All source is in this repository. No external demo checkout is needed.

| Location | Responsibility |
| --- | --- |
| `protocol` | UAAP working draft and current HTTP mapping |
| `libraries/agent-sdk` | UAAP Agent SDK: runtime-independent outbound app connections and message/context delivery |
| `libraries/app-sdk` | UAAP App SDK: generic message/context store, headless HTTP adapter, and shopping specialization |
| `examples/shopping/dayform` | Warm DAYFORM storefront and mock catalog |
| `examples/shopping/stride` | Dark STRIDE STUDIO storefront and mock catalog |
| `examples/shopping/store.js` | Shared product-page controller (served by both apps) |
| `src/ruth/shopping` | Agent SDK integration, registry, shopping APIs, tool orchestration, durable replies and task lifecycle |
| `src/ruth/app/core.py` | `/shop`, existing runtime session, serialized Telegram/app turns, Telegram outbox |

The two stores have separate HTTP origins, catalogs, account credentials,
session histories and SQLite files. They import the same `/sdk/agent-chat.js`
and CSS. Both stores use `variant="sidebar"` to keep Ruth on the right on desktop,
with `app-name` labels identifying **Ruth on DAYFORM** and **Ruth on STRIDE**.
STRIDE uses `theme="dark"` to match its storefront; the shared avatar and continuing
conversation remain recognizable. On narrow screens the chat stacks below the products.
Neither store imports Ruth or calls a public agent endpoint.
The shared chat widget is an [optional example UI](../examples/shopping/agent-ui.md);
applications can use the app SDK's backend with their own frontend.

## Local walkthrough with the real model

Requires Python 3.11+ and a working Ruth runtime (the inherited default is the
authenticated Codex CLI). The SDK and demo servers use the Python standard
library; no Node build or additional web framework is needed.

From the Ruth checkout, start the stores:

```bash
bin/ruth-shopping-demo serve --root "$PWD/.ruth/shopping-demo"
```

In another terminal, use the **same root** for the console:

```bash
bin/ruth-shopping-demo console --root "$PWD/.ruth/shopping-demo"
```

This console runs Ruth's configured model; it has no canned response mode. It
substitutes local input/output for Telegram while using the same shopping
service. Console notifications print in the terminal. Its session is
`console:demo`, deliberately separate from a live Telegram instance.

1. `/shop work sneakers for my walk to the office, US 9, under $130 total. Compare Day One and Arc 02.`
2. Open both recommendation links. They connect your preconfigured demo account
   to the store chat. Plain store URLs let you browse but do not connect chat.
3. In DAYFORM: “Would this pair be comfortable for my walk?”
4. In STRIDE: “How does this compare with the first pair?”
5. Return to DAYFORM. Choose a size and say “Place a simulated order for this
   pair in US 9, quantity 1, up to $120 total,” or use **Ask Ruth to order**.
6. The source chat receives the result; the console receives the full website
   conversation turn (your message and Ruth’s reply). Ruth continues listening for follow-up questions in both stores.
   `/shop cancel` stops polling;
   `/shop status` reports whether it is active.

Day One costs $98 ($107.80 including mock tax); Arc 02 costs $112 ($123.20
including mock tax). A $120 total budget should exclude Arc 02. All catalog
claims and orders are fictional. There are no payment or address APIs.

For another run after completion, use `/shop <request>` again. This retains the
conversation and app cursors. Messages submitted while polling is stopped stay
queued until the next task. Store sessions are per browser tab and survive a
reload; opening a new tab creates a new delivery session, not a new agent.

## Telegram

Use an instance containing this revision, with its existing runtime, Telegram
provider, bot token and **locked conversation** configured as in the main
README. Start the stores from that checkout with:

```bash
bin/ruth-shopping-demo serve
```

Then start/restart that instance's normal `bin/ruth-daemon`. Send `/shop ...`
to its Telegram bot. The app turns reuse **that exact `telegram:<chat-id>`
runtime session**, including previous Telegram conversation. Every new website
turn is also mirrored to the locked Telegram conversation, labeled with the store
and product, followed by **You** and **Ruth** with their complete messages. The
mirror uses Ruth's existing durable notification service; retries reuse the same
notification key without repeating reasoning or website output. Telegram turns
are already present in that chat and are not mirrored again. The app worker polls while
Telegram's long poll is waiting; a shared lock serializes reasoning turns.

Telegram recommendations appear as one photo album with one shared caption,
using [Telegram sendMediaGroup](https://core.telegram.org/bots/api#sendmediagroup).
The caption numbers products in photo order, with each store/product name, price,
total including mock tax, and the full clickable product URL, including its
connection fragment. URLs appear as visible text rather than hidden text links.
A short opening
recommendation is included within Telegram's caption limit. The full reply stays
in Ruth's conversation; successful albums do not generate a separate text message.

Order confirmations use one product photo with the order number, product, size,
confirmed total and simulated-payment notice in its caption. This applies both
to orders placed through a web app and through Telegram. Web orders also include
the full mirrored conversation turn so the user’s original request is retained. The ordered product's
app supplies the image; all receipt details come from the confirmed order, even
if the catalog changes later. A durable order-photo receipt prevents repeated
uploads on replay. Missing images, oversized captions or uncertain photo delivery
fall back to the full text confirmation; an uncertain send can produce a photo
plus fallback text, but never triggers another purchase.
One recommended product uses `sendPhoto` with the same caption format.

Ruth reads each catalog `image` from its registered app and uploads the bytes, so
local demo images do not need a public image host. PNG/JPEG images are limited to 8 MB;
cross-origin images and redirects are not followed, and image requests carry no
account credentials. The shared provider's text-only interface remains unchanged.

An unavailable image, URLs exceeding the caption limit, or failed/ambiguous album upload falls back to the full text
recommendation with links. A per-turn album receipt prevents duplicate attempts
on event replay or restart. An ambiguous upload is not retried automatically, so
an uncertain outcome can yield an album plus fallback text, but no repeated album.
Ask Ruth to show the recommendations again to make a new attempt.

If serving the websites from the source checkout for another instance, pass
`--root /absolute/path/to/the/instance` to `serve`. The instance's own code must
also include this revision. Do not run the console against a live Telegram
instance: a demo registry is bound to one conversation.

The default URLs are `http://127.0.0.1:8011` and `http://127.0.0.1:8012`.
**Open them on the same computer as the servers.** They will not open from a
phone's Telegram browser. Remote HTTPS deployment/account onboarding is outside
this local demo. `--dayform-port` and `--stride-port` select other ports when
creating a new demo root; reuse the configured ports thereafter.

## Current app and page activity

Both websites enable UAAP's optional `context-presence/1` extension. After you
connect a store, switching product/size sends `context.updated`; focus, visibility
and a 15-second heartbeat send `presence.updated`. A 45-second lease expires to
unknown if the tab closes, the browser goes offline, or reporting stops. Updates
are limited to connected app sessions. Ruth sends a short Telegram announcement
when one app remains uniquely active for two seconds: first arrival, then
transitions such as `DAYFORM → STRIDE STUDIO`, with the viewed product when known.
Heartbeats, product changes within the same app, conflicting app presence and
expired presence do not create additional announcements. Multiple active sessions
in the same app can identify the app without guessing the viewed product. Brief focus changes are debounced.
Announcements include the observation time; durable text/keys survive send failures
and restarts. Telegram provider guarantees still apply to uncertain delivery.

During an active `/shop` task, a separate worker refreshes Ruth's observed state
without waiting for an ongoing model turn. `/shop status` reports the current
observed app/product, multiple active sessions, or unknown. Her next shopping
turn includes the observed state separately from the original message snapshot.
Ruth continues replying to the message's source session after a page switch.
`/shop cancel` stops message/activity polling and app-switch announcements.

Activity uses its own cursor and `.ruth/shopping/activity.json`. Each app database
keeps only the latest context/presence event per session. No complete browsing
history is retained by this feed. Restart preserves activity state and expiry;
stale observations never acquire a new lease just because Ruth reads them again.
Reload the websites after updating the SDK. If a website server was restarted,
reconnect through a Ruth recommendation link to renew the browser cookie.

## UAAP and data ownership

The [UAAP working draft](../protocol/README.md) defines the collaboration
semantics. The current agent-facing adapter exposes two HTTP operations:

- `GET /collaboration/events?after=<cursor>` returns up to 20 user messages,
  each with `event_id`, `session_id`, `message`, `context`, `created_at`, and a
  per-app integer cursor. It is a non-destructive read.
- `POST /collaboration/sessions/<id>/outputs` accepts `id`, `in_reply_to`,
  `text`, and optional `shared_context`. The SDK rejects replies to a different
  session and conflicting reuse of an output ID.

Ordinary app APIs implement `queryProduct` (`GET /products`), `getProduct`
(`GET /products/<id>`), and `orderProduct` (`POST /orders`). Prices use integer
USD cents. Query filters are `q`, `size`, and `max_price_cents`. Orders require
product ID, size, quantity 1, maximum total and an idempotency key.

The browser uses separate same-origin `/ui/*` routes. On send, the component
freezes page revision, product ID and selected size. The app enriches the
snapshot with its product facts. A later product selection cannot change a
queued message. Ruth replies to its source session even if the user has moved.

Checking **Share my shopping preferences with this store** authorizes only the
current message's structured return context: shopping budget, shoe size and
purpose. Both Ruth and the SDK enforce this metadata boundary. The store
displays those preferences. Replies themselves may naturally discuss the
cross-store comparison requested by the user. Other stores' transcripts and
Ruth's full private memory are not synchronized into the app database.

Ruth provides tool decisions as bounded JSON through the existing model runtime;
the host validates tool arguments and invokes APIs. The model does not need
network or shell access for shopping. Model-based interpretation of natural
language order authorization is appropriate only for this simulated demo; it
is not a production purchase authorization mechanism.

## State and retries

All generated state is ignored under the chosen root's `.ruth/` directory:

- `shopping/registry.json`: local app origins and separate agent/browser
  credentials. It is created with owner-only file permissions.
- `shopping/state.json`: active task, app cursors, durable inbound/output/order
  receipts and one continuing collaboration journal across tasks.
- `demo-apps/dayform.sqlite`, `demo-apps/stride.sqlite`: app-owned reference
  stores, colocated for this local demo.

Each app has separate random credentials. Agent endpoints require a bearer
token. Browser links carry a demo account capability in the fragment, exchanged
for an HttpOnly same-origin cookie and removed from the address bar. The SDK
checks Host/Origin, scopes sessions to the connected account and renders reply
text without HTML. Restarting the servers requires reconnecting using a Ruth
link. These preconnected demo bindings are not OAuth, multi-user tenancy or a
production login design; keep this reference server on loopback.

Output is stored before delivery. An output retry keeps the original ID and
does not invoke reasoning again. Before submitting an order Ruth persists its
exact payload/key. A lost order response retries that payload; the app returns
the existing receipt. Failed Telegram notification is retried before the event
is acknowledged. An order completes a purchase, not the shopping conversation:
the bounded app registry remains connected until `/shop cancel`. Every new
`/shop <request>` event starts a new task while preserving the same conversation
and purchase history. Ruth receives the task identity and earlier orders separately
from the current message's order receipt. A previous purchase may be mentioned,
but does not prevent a new, explicit purchase of the same product and size.
The shared UI disables ordering while a reply is pending, then offers
**Order another pair** with a reminder of the previous purchase. Each distinct
purchase request gets its own order key; replay of that request reuses its key.
The existing Telegram provider's delivery guarantees still apply; a
provider cannot guarantee exactly-once delivery after every ambiguous failure.

There is one active shopping task and one user per registry. No SSE, central
broker, dynamic discovery, real checkout, user study or
model-quality benchmark is implemented. A crash during reasoning can repeat a
model turn; output/order idempotency protects the corresponding demo effects.

## Verification

```bash
python3.13 -m unittest tests.test_ruth_shopping -v
python3.13 -m unittest tests.test_uaap_sdk -v
node tests/test_uaap_activity_ui.cjs
python3.13 -m unittest tests.test_ruth_activity_notifications -q
python3.13 -m unittest tests.test_ruth_shopping_photos -q
node tests/test_shopping_order_ui.cjs
python3.13 -m unittest tests.test_ruth_telegram tests.test_ruth_brain tests.test_ruth_application tests.test_ruth_command_registry -q
```

Use the instance's installed Python/dependencies, or Ruth's normal pinned
dependency activation. Tests require local socket access. They use isolated
temporary state and a deterministic reasoning fixture; they do not contact a
real Telegram account or measure model quality. The integration tests cover
three surfaces, shared session identity, message-time context, session routing,
disclosure scope, cancellation/resume, restart, duplicate output delivery,
ambiguous order outcomes and notification recovery.

The product images and visual direction reuse the earlier Bob concept video;
see [asset provenance](../examples/shopping/asset-provenance.md). That video
remains a scripted concept, separate from this executable prototype.
