# UAAP Agent SDK

Connect a personal agent to application-hosted UAAP message delivery and context
exchange APIs. The SDK has no Ruth, model-provider, app SDK, or UI dependency.
It uses Python 3.11+ and the standard library.

```bash
python3 -m pip install -e libraries/agent-sdk
```

```python
from our_ark_agent_sdk import AppClient

app = AppClient(
    app_id="notes", name="My Notes",
    base_url="https://notes.example", token=app_account_credential,
)
batch = app.events(after=saved_cursor)
for event in batch["events"]:
    # The agent supplies its own model, continuing memory, and disclosure policy.
    # Persist the output before delivery; reuse it if delivery must be retried.
    output = load_or_create_durable_reply(app.app_id, event)
    app.output(event["session_id"], output)
    save_cursor(app.app_id, event["cursor"])
```

`load_or_create_durable_reply` and `save_cursor` above are integration functions
supplied by the agent. An output contains `id`, `in_reply_to`, `text`, and optional
authorized `shared_context`; see the [protocol](../../protocol/README.md).

## Responsibilities

- `AppClient`: one app origin and account credential; outbound JSON requests.
- `events(after)`: a finite polling batch with app-local cursor validation.
- `output(session_id, body)`: reply delivery to the originating app session.
- `UAAPError.retryable`: distinguishes transient HTTP/transport failures from
  permanent rejections. Redirects are not followed and credentials are hidden
  from the client's representation. HTTPS is required outside loopback.

The client does not automatically retry writes, persist cursors, own conversation
memory, discover apps, or run an agent. The agent chooses connection/task
lifetimes and keeps durable IDs and receipts so retries do not create new turns
or duplicate effects. Polling is the current transport; SSE and presence are
future extensions.

`request(path, body)` can also call ordinary app APIs. Shopping-specific product
methods, recommendation photos, ordering policy, Telegram, and `/shop` live in
[Ruth's integration](../../src/ruth/shopping), outside this SDK.

The other side of the contract is the [UAAP App SDK](../app-sdk/README.md).
Applications choose their own UI; no browser component is required by this client.
