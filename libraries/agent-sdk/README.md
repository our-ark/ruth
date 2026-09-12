# UAAP Agent SDK

Connect a personal agent to application-hosted UAAP message delivery and context
exchange APIs. The SDK has no Ruth, model-provider, app SDK, or UI dependency.
It uses Python 3.11+ and the standard library.

```bash
python3 -m pip install -e libraries/agent-sdk
```

```python
from our_ark_agent_sdk import AgentOutput, AppClient

app = AppClient(
    app_id="notes", name="My Notes",
    base_url="https://notes.example", token=app_account_credential,
)
batch = app.events(after=saved_cursor)
for event in batch["events"]:
    # App -> agent: local context captured with this user message.
    app_context = event["context"]
    user_message = event["message"]["text"]

    output = load_saved_reply(app.app_id, event["event_id"])
    if output is None:
        # The agent combines app_context with its own continuing conversation.
        reply_text = respond(user_message, app_context)
        # Agent -> app: select only user context authorized for this destination.
        user_context = authorized_context_for_app(app.app_id, event)
        output: AgentOutput = {
            "id": new_reply_id(),
            "in_reply_to": event["message"]["id"],
            "text": reply_text,
            "shared_context": user_context,
        }
        save_reply(app.app_id, event["event_id"], output)
    # A retry reuses the saved text, shared context, and IDs.
    app.output(event["session_id"], output)
    save_cursor(app.app_id, event["cursor"])
```

The reply-storage, reasoning, ID, authorization, and cursor functions above are
integration hooks supplied by the agent. They are not SDK functions. The complete
context round trip is exercised by the [headless notes-app test](../../tests/test_uaap_sdk.py).

## Context exchange

Core context exchange travels in the same envelopes as message delivery:

| Direction | SDK method and field | Example |
| --- | --- | --- |
| App -> personal agent | `events()` returns `AppEvent.context` | Selected paragraph, product details, or current page state captured with the message. |
| Personal agent -> app | `output()` sends `AgentOutput.shared_context` | A language preference or shopping budget authorized for this app. |

For a notes app that supports language disclosure, an authorized output could be:

```python
output: AgentOutput = {
    "id": "reply-001",
    "in_reply_to": "msg-001",
    "text": "Here is the explanation in English.",
    "shared_context": {"language": "en"},
}
app.output(source_session_id, output)
```

The SDK preserves domain fields and checks that incoming `context` and outgoing
`shared_context` are objects. These shape checks do not authorize disclosure.
The agent selects allowed user context; the app checks its own per-message
policy. An empty `{}` shares no structured user context. The SDK does not copy
incoming app context or the agent's full memory into `shared_context` automatically.

`AppEvent`, `EventBatch`, `UserMessage`, and `AgentOutput` are exported `TypedDict`
envelopes. They document the core fields while app adapters may add metadata,
such as the shopping demo's `share_preferences` permission.

## Independent context and presence

`capabilities()` discovers optional extensions (404 means a message-only app).
For `context-presence/1`, `activity(after=activity_cursor)` returns a validated
`ActivityBatch` of `ActivityEvent` updates and an app-server timestamp. Both types
are exported by the SDK. Keep this cursor separate from the message cursor.

```python
if "context-presence/1" in app.capabilities()["extensions"]:
    batch = app.activity(after=saved_activity_cursor)
    for event in batch["events"]:
        update_observed_state(app.app_id, event, batch["server_time"])
    persist_observed_state_and_cursor(batch["cursor"])
```

The update/persistence functions are agent-supplied hooks. This feed coalesces
superseded state; it is not a complete activity history. Treat presence as a
lease, account for app clock differences using `expires_at - server_time`, and
keep simultaneous active sessions ambiguous. Activity is separate from message
snapshots and never grants permission to act. See the
[extension contract](../../protocol/README.md#optional-extension-context-presence1).

## Responsibilities

- `AppClient`: one app origin and account credential; outbound JSON requests.
- `events(after)`: receive user messages with app context; validate app-local cursors and context shape.
- `output(session_id, body)`: deliver replies with optional authorized user context to the originating app session.
- `UAAPError.retryable`: distinguishes transient HTTP/transport failures from
  permanent rejections. Redirects are not followed and credentials are hidden
  from the client's representation. HTTPS is required outside loopback.

The client does not automatically retry writes, persist cursors, own conversation
memory, discover apps, or run an agent. The agent chooses connection/task
lifetimes and keeps durable IDs and receipts so retries do not create new turns
or duplicate effects. Polling is the current transport; SSE remains future work.

`request(path, body)` can also call ordinary app APIs. Shopping-specific product
methods, recommendation photos, ordering policy, Telegram, and `/shop` live in
[Ruth's integration](../../src/ruth/shopping), outside this SDK.

The other side of the contract is the [UAAP App SDK](../app-sdk/README.md).
Applications choose their own UI; no browser component is required by this client.
