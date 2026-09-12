# UAAP App SDK

Backend support for **UAAP — User–Agent–App Protocol**: expose message delivery
and context exchange to a user's persistent personal agent. The app SDK owns
the application side of the contract; the [agent SDK](../agent-sdk/README.md)
connects from the personal agent's side.

The core is independent of Ruth, models, and chat UI. Python 3.11+, standard
library only. The package is `our-ark-app-sdk`; import `our_ark_app_sdk`.

```bash
python3 -m pip install -e libraries/app-sdk
```

## Backend integration

`MessageStore` provides SQLite sessions, message-time context snapshots,
resumable event reads, correlated outputs, and duplicate-ID handling. It accepts
application-specific JSON context without requiring products or shopping fields.

```python
from pathlib import Path
from our_ark_app_sdk import MessageStore

store = MessageStore(Path("private/notes.sqlite"), "notes")
# Called by your backend after authenticating the user.
session = store.session(authenticated_user_id)
store.message(authenticated_user_id, {
    "id": "msg-001",
    "session_id": session["session_id"],
    "text": "Explain this paragraph.",
    "context": {"document_id": "doc-1", "selected_text": "A paragraph..."},
})
```

Map `store.events(after)` and `store.output(session_id, body)` to the
[UAAP HTTP endpoints](../../protocol/README.md) in your own backend. Authenticate
the agent connection and scope it to the connected account. Read
`store.transcript(authenticated_user_id, session_id)` to render the session's
messages and outputs in your chosen UI.

Use these extension points for application-specific policy:

- `snapshot_context(context)`: validate/enrich app facts before persisting a message.
- `message_metadata(body)`: record app-validated disclosure permissions with a message.
- `validate_shared_context(source, shared)`: validate returned fields and check
  the source message's permission. The base store rejects nonempty shared context
  until the application supplies this policy.

These callbacks do not grant the agent access to private memory; the agent also
enforces its user's disclosure policy. See the independent notes-app round trip
in [SDK tests](../../tests/test_uaap_sdk.py).

## Headless reference HTTP adapter

For local development, `AppServer` exposes the core agent-facing HTTP operations
without a frontend:

```python
from our_ark_app_sdk import AppServer

server = AppServer(
    ("127.0.0.1", 8013), store=store,
    agent_token=app_account_credential,
    public_origin="http://127.0.0.1:8013",
)
server.serve_forever()
```

With no `connect_token` or `static_dir`, browser routes and static UI are
disabled. The app backend can accept user messages through its own interface.
The reference HTTP adapter is for one preconnected account; a production app
must provide its own identity/tenant binding. The generic store's event feed
does not filter multiple accounts, so use a separate account-scoped store/feed
or implement authenticated account filtering before exposing it to agents.

## Optional context/presence extension

Enable `MessageStore(path, app_id, activity_enabled=True)` to advertise
`context-presence/1`. Call `store.activity(authenticated_user_id, body)` with
`event_id`, `session_id`, `type`, `sequence`, and either `context` or `state`.
A context update uses the same `snapshot_context` validation as message context.
Presence state is `active` or `inactive`; the server stamps reception and expiry.

`store.activity_events(after)` supplies the independent coalesced feed; map it to
`GET /collaboration/activity`. `store.capabilities()` supplies capability discovery.
These operations inherit the same account-scoping requirements as message feeds.
The additive SQLite table preserves existing messages, sessions and outputs.
Only the latest update per session/type is retained. Identical retries do not
renew leases, and lower sequences are ignored. See the
[protocol](../../protocol/README.md#optional-extension-context-presence1).

The optional browser `ActivityReporter` in `static/activity.js` reports focus,
visibility, heartbeat and context changes for one authenticated session. Its
`contextChanged()` hook should be called when relevant app state changes. It
sends no messages and invokes no models. `<agent-chat>` starts it after connecting
only when the app advertises support, and exposes the same `contextChanged()` hook.

## Shopping adapter and optional example UI

`CollaborationStore(path, app_id, catalog)` extends `MessageStore` with the
existing shopping snapshot/disclosure policy, mock products, and simulated
orders, and enables the activity extension. The two demo websites use it with `AppServer`, supplying a
`connect_token`, `static_dir`, and their own storefront files. Existing routes,
payloads, databases, and package imports remain compatible.

The bundled `<agent-chat>` component is optional. It uses app-owned `/ui/*`
routes and a browser cookie separate from the agent credential. Its current
Ruth labels and shopping controls are example UI, not UAAP protocol requirements.
See the [example UI guide](../../examples/shopping/agent-ui.md) for both stores'
styling and integration. A custom UI or an adapted third-party toolkit can
use the same backend semantics.

See the [SDK overview](../README.md), [protocol](../../protocol/README.md), and
[runnable shopping example](../../docs/shopping-demo.md).
