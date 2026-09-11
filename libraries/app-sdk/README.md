# UAAP App SDK (prototype)

Reference application SDK for **UAAP — User–Agent–App Protocol**: app-hosted
message delivery and context exchange for a user's persistent personal agent.
See the [UAAP working draft](../../protocol/README.md) for the roles, semantics,
and current HTTP mapping.

The SDK lives in the Ruth monorepo but imports no Ruth modules. Python 3.11+,
standard library only; the browser component uses native ES modules. Its package
name remains `our-ark-app-sdk`, with Python imports from `our_ark_app_sdk`.

```bash
python3 -m pip install -e libraries/app-sdk
```

The provided `AppServer` is a loopback reference adapter with SQLite storage,
one preconnected account, mock product APIs and simulated orders. Context
validation and disclosure fields currently describe shopping; another domain
needs its own context handling. A production app would bind the contracts to
its own authentication and domain backend.

```python
from pathlib import Path
from our_ark_app_sdk import AppServer, CollaborationStore

store = CollaborationStore(Path("private/app.sqlite"), "my-store", catalog)
server = AppServer(
    ("127.0.0.1", 8011), store=store,
    agent_token=agent_account_credential, connect_token=browser_account_capability,
    static_dir=Path("public"), public_origin="http://127.0.0.1:8011",
)
server.serve_forever()
```

Both demo websites load the exact same component:

```html
<link rel="stylesheet" href="/sdk/agent-chat.css">
<script type="module" src="/sdk/agent-chat.js"></script>
<agent-chat variant="sidebar" app-name="DAYFORM"></agent-chat>
```

After the custom element loads, set `chat.contextProvider` to a function
returning `{revision, product_id, selected_size}`. The component snapshots that
value on send, retries with a stable message ID, and renders only its session's
outputs. Both stores use a sidebar: STRIDE sets `app-name="STRIDE"` and
`theme="dark"`. The component also supports `variant="dock"` and overrides of
the `--agent-*` CSS properties. Its current labels refer to Ruth and shopping;
UAAP permits other agent identities and app-owned interfaces. `agent-context`
events carry authorized structured context returned by the agent; application
code decides how to use it.

The agent receives messages via `GET /collaboration/events` and delivers answers
via `POST /collaboration/sessions/<id>/outputs`. All agent calls are outbound to
the app. Browser `/ui/*` routes use a separate cookie credential; the agent
bearer token is never sent to the frontend.

Product search and ordering are ordinary domain APIs alongside UAAP's two
collaboration contracts. See the [protocol](../../protocol/README.md) and
[runnable example](../../docs/shopping-demo.md).
