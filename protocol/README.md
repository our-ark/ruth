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

The current agent SDK exposes the two directions as `AppEvent.context` from
`AppClient.events()` and `AgentOutput.shared_context` sent by `AppClient.output()`.
See its [context exchange example](../libraries/agent-sdk/README.md#context-exchange).
These core envelopes remain message-bound snapshots and disclosures. The optional
`context-presence/1` extension below adds independent app context and presence.

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

## Optional extension: `context-presence/1`

An app may publish context and presence independently of user messages. Agents
first read authenticated `GET /collaboration/capabilities`:

```json
{"extensions": ["context-presence/1"], "presence_ttl_seconds": 45}
```

An absent extension or a 404 from this endpoint means message-only operation.
Authentication/transport failures do not mean the extension is unsupported.
Existing `/collaboration/events` and output semantics remain unchanged. Apps
opt into activity reporting for their connected user; this does not authorize
tracking unrelated apps or returning any additional user memory to the app.

`GET /collaboration/activity?after=<cursor>` returns `events`, `cursor`, and
`server_time` (Unix seconds on the app server). The activity cursor is independent
of the message cursor. The reference store coalesces updates to the latest event
per `(session_id, type)`, returning at most 100 in ascending cursor order. Gaps
are expected: this is a resumable latest-state feed, not an audit log of every
page visit. Superseded heartbeats need not be processed. Persist updates and the
cursor together; retries must not renew the same presence observation.

Each activity event includes:

| Field | Meaning |
| --- | --- |
| `event_id` | Stable ID for a submitted update. |
| `app_id`, `session_id` | Origin and app-local session; interpret together. |
| `type` | `context.updated` or `presence.updated`. |
| `sequence` | Positive safe integer, strictly increasing per session and type. |
| `cursor` | App-assigned position in the separate activity feed. |
| `received_at` | App-server reception time, in Unix seconds. |
| `context` | Required object for `context.updated`; validated/enriched by the app. |
| `state`, `expires_at` | Required for `presence.updated`; state is `active` or `inactive`, with an app-server expiry time. |

For example, a context update can identify a newly selected product, while a
presence update reports that this session currently has a visible, focused page.
Presence is an observation, not proof of a user's attention or global location.
Multiple sessions/devices may report active simultaneously. An agent must retain
that ambiguity, and use **unknown** after expiry instead of inventing a location.
The demo sends an active heartbeat every 15 seconds and grants a 45-second lease.
Extension leases must be positive and at most 120 seconds. Use
`expires_at - server_time` (conservatively allowing for request delay) to compute
remaining lifetime across machines with different clocks. A stale read never
makes an expired observation fresh. Context changes alone do not renew presence.

The app backend authenticates and scopes session writes. It rejects conflicting
reuse of the current sequence, ignores lower sequences, and returns the stored
result for identical retries without changing reception or expiry time. The demo
browser stores its sequence across reloads. A new session starts its own sequence.
The reference adapter supplies authenticated, same-origin `POST /ui/activity` and
`GET /ui/capabilities` for its optional browser UI; these UI paths are not required
for custom app integrations. Generic `MessageStore` disables the extension by
default; the two shopping apps explicitly enable it.

Activity updates do not contain user messages, require replies, enter a chat
transcript as user messages, or authorize purchases. An agent may send user-enabled
activity announcements through its own channel; these are separate from app replies
and do not change the extension contract. They cannot be used as `in_reply_to` targets.
The agent may include observed activity as separately labeled context on its
next reasoning turn. It must retain the original message snapshot and route its
reply to that message's source session, regardless of subsequent activity.
An app's activity feed and messages must share the same connected-account scope.
The reference single-account adapter is not a multi-tenant authorization system.

## Connection lifecycle and implementation scope

The current demo uses one preconnected user and a small static app registry.
`/shop <request>` starts a new task and polls both apps, retaining the same
conversation and purchase history. Ruth answers messages in their source
sessions. Polling continues after an order until `/shop cancel`; the agent's
conversation persists after polling stops.

This implementation combines message-time snapshots with optional context/presence
updates from connected apps. SSE, app discovery, and multi-user onboarding remain
future work. No
central UAAP relay is required for this polling example. The broader
[architecture notes](../docs/app-collaboration.md) discuss possible extensions.

The SDK remains installed as `our-ark-app-sdk` and imported as
`our_ark_app_sdk`. Its existing `/health` identifier is `our-ark-app/0.1`;
introducing the UAAP name does not change those identifiers, endpoint paths,
or core payloads. Optional extensions are advertised through capabilities; there
is no general protocol-version negotiation in this prototype.

## Implementation and walkthrough

- [SDK overview](../libraries/README.md): agent-side and application-side responsibilities, with replaceable UI.
- [UAAP Agent SDK](../libraries/agent-sdk/README.md): independent outbound app client, event reads, and reply delivery.
- [UAAP App SDK](../libraries/app-sdk/README.md): UI-independent message/context storage and reference HTTP adapter; includes a shopping specialization.
- [Ruth integration](../src/ruth/shopping): uses the agent SDK while retaining task lifecycle and shared conversation orchestration.
- [Optional demo UI](../examples/shopping/agent-ui.md): the existing shopping chat component, independent of the protocol requirements.
- [Participating applications](../examples/shopping/README.md): DAYFORM and STRIDE.
- [Runnable demo and verification](../docs/shopping-demo.md): console/Telegram setup and existing integration checks.
