# UAAP — User–Agent–App Protocol

**UAAP enables collaboration among users, their persistent personal agents,
and applications through message delivery and context exchange.**

Status: working draft, with a local polling-based shopping reference
implementation in this repository. This document names the collaboration
contracts and describes their current HTTP mapping. It does not introduce a
new transport or claim a finalized interoperability standard.

**One Agent, Anywhere** is the architectural vision. **UAAP** defines the
collaboration contracts. **Ruth** is the reference personal agent; DAYFORM and
STRIDE are participating applications.

## Three participants

| Participant | Responsibility |
| --- | --- |
| User | Directs the collaboration, chooses applications, and authorizes disclosure and actions. |
| Personal agent | Maintains the user's continuing conversation, preferences, and goals across applications. |
| Application | Supplies local state and domain intelligence, renders its own interface, and retains authority over its services. |

The user interacts with both their agent and the application. The UAAP network
interface connects the application and the personal agent: the app hosts the
endpoints, and the agent initiates outbound calls. The agent needs no public
inbound endpoint. Applications may retain their own models or agents.

## Two collaboration contracts

### Message delivery

An application delivers a user's message with a stable message identifier and
its source session. The personal agent incorporates it into the continuing
conversation and returns an answer correlated with that message.

An app session identifies a delivery destination. Switching apps or opening a
new delivery session does not require a new personal-agent conversation. The
reference implementation routes a reply to the originating app/session, even
if the user has switched elsewhere while the answer is being generated.

### Context exchange

The application attaches a snapshot of the local context relevant to the
message, such as the current page, selected product, and selected size. The
snapshot reflects the state when the message was sent; later UI changes do not
change the meaning of a queued request.

The agent can return selected, authorized user context for the application to
use in its own presentation or domain logic. Access to the agent's continuing
context does not imply that every application receives its full conversation
or private memory. App-provided context remains untrusted input and does not
grant permission to take actions or disclose unrelated information.

## Current HTTP mapping

The [UAAP App SDK](../libraries/app-sdk/README.md) implements both contracts
through two agent-facing operations. Each app has its own origin, account
credential, cursor, and sessions. Requests use an app-specific bearer token;
JSON request bodies use `Content-Type: application/json`.

| Operation | HTTP request | Result |
| --- | --- | --- |
| Receive messages with app context | `GET /collaboration/events?after=<cursor>` | An `events` array and the last returned `cursor`; up to 20 events in app-local cursor order. An empty batch retains the input cursor. |
| Deliver a reply with optional user context | `POST /collaboration/sessions/<session_id>/outputs` | The stored output, correlated to a message in that session. |

An incoming event contains:

| Field | Meaning in the current adapter |
| --- | --- |
| `event_id` | Stable event identifier, equal to `message.id` in this implementation. |
| `session_id` | App-local delivery session. |
| `message` | User message with `id` and `text`. |
| `context` | Message-time snapshot: `revision`, `page_type`, `product_id`, `selected_size`, and app-enriched `product` facts. |
| `share_preferences` | Whether this message authorizes the demo's structured preference disclosure. |
| `created_at` | App-assigned Unix timestamp in seconds. |
| `cursor` | App-local integer cursor for resumable reads. |

App and account identity come from the configured authenticated connection.
Product references must therefore retain their source app as well as the
product ID. Cursors from different apps do not establish a global event order.

For a message `msg-001` in session `session-001`, an output can be posted to
`/collaboration/sessions/session-001/outputs`:

```json
{
  "id": "reply-001",
  "in_reply_to": "msg-001",
  "text": "This pair fits the budget we discussed in Telegram.",
  "shared_context": {}
}
```

The current shopping adapter accepts `budget_cents`, `size`, and `purpose`
in `shared_context` only when the source message has `share_preferences: true`.
These shopping-specific fields and the preference checkbox are reference
application choices, not universal UAAP context fields. Natural-language
replies can include a cross-app comparison requested by the user; the structured
field check is not a general redaction guarantee for reply text.

### Delivery and retries

Event reads are non-destructive. The browser retains the message ID and snapshot
when retrying a send. Reusing a message or output ID with different content is
rejected with HTTP 409. Posting an output to a session that does not own the
referenced message is rejected with HTTP 400; unauthorized structured preference
disclosure is rejected with HTTP 403.

Ruth persists received-event receipts, outputs, and app cursors. An output retry
uses its original ID. These mechanisms support recovery and deduplication;
they do not guarantee that model reasoning executes exactly once after a crash.

## Application UI and domain APIs

The two [UAAP SDKs](../libraries/README.md) implement the agent and application
sides of these contracts. The agent SDK needs no frontend. The app SDK's
`MessageStore` accepts domain-specific JSON context, while `AppServer` can run
headlessly with only agent-facing HTTP endpoints. The `CollaborationStore`
shopping specialization supplies the product and preference fields listed above.

The shared `<agent-chat>` component is one UI implementation. Both demo stores
use it with their own styling and app label. Its same-origin `/ui/*` routes
connect the browser to the application's backend with a separate cookie
credential; the agent bearer token is never exposed to the browser.

UAAP does not require this component or a uniform chat layout. The supplied component currently
uses Ruth's name and shopping-specific copy. Another integration can use its
own UI while preserving the message and context semantics.

`queryProduct`, `getProduct`, and `orderProduct` are ordinary domain operations,
mapped to `/products` and `/orders` by the shopping example. They complement
UAAP; they are not additional core collaboration contracts. Orders in this
repository are simulated and use their own idempotency keys.

## Connection lifecycle and implementation scope

The current demo uses one preconnected user and a small static app registry.
`/shop <request>` starts a new task and polls both apps, retaining the same
conversation and purchase history. Ruth answers messages in their source
sessions. Polling continues after an order until `/shop cancel`; the agent's
conversation persists after polling stops.

This implementation uses message-time snapshots. SSE, presence queues, dynamic
user tracking, app discovery, and multi-user onboarding are future work. No
central UAAP relay is required for this polling example. The broader
[architecture notes](../docs/app-collaboration.md) discuss possible extensions.

The SDK remains installed as `our-ark-app-sdk` and imported as
`our_ark_app_sdk`. Its existing `/health` identifier is `our-ark-app/0.1`;
introducing the UAAP name does not change those identifiers, endpoint paths,
or payloads. There is no protocol-version negotiation in this prototype.

## Implementation and walkthrough

- [SDK overview](../libraries/README.md): agent-side and application-side responsibilities, with replaceable UI.
- [UAAP Agent SDK](../libraries/agent-sdk/README.md): independent outbound app client, event reads, and reply delivery.
- [UAAP App SDK](../libraries/app-sdk/README.md): UI-independent message/context storage and reference HTTP adapter; includes a shopping specialization.
- [Ruth integration](../src/ruth/shopping): uses the agent SDK while retaining task lifecycle and shared conversation orchestration.
- [Optional demo UI](../examples/shopping/agent-ui.md): the existing shopping chat component, independent of the protocol requirements.
- [Participating applications](../examples/shopping/README.md): DAYFORM and STRIDE.
- [Runnable demo and verification](../docs/shopping-demo.md): console/Telegram setup and existing integration checks.
