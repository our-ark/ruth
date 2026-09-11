# Optional shopping chat UI

DAYFORM and STRIDE use the same `<agent-chat>` component for the demo. This is
one replaceable application UI; UAAP's message and context APIs do not require
the component, a uniform layout, or a frontend framework.

The assets remain in `libraries/app-sdk/src/our_ark_app_sdk/static` to preserve
existing `/sdk/*` URLs. `AppServer` serves them only when `static_dir` is enabled.

```html
<link rel="stylesheet" href="/sdk/agent-chat.css">
<script type="module" src="/sdk/agent-chat.js"></script>
<agent-chat variant="sidebar" app-name="DAYFORM"></agent-chat>
```

After the element loads, set `chat.contextProvider` to return
`{revision, product_id, selected_size}`. The component freezes that context on
send and retries with a stable message ID. It renders the current session's
outputs, while Ruth maintains the continuing conversation across applications.

Both stores use a sidebar. STRIDE sets `app-name="STRIDE"` and `theme="dark"`.
The component also supports `variant="dock"` and overrides of `--agent-*` CSS
properties. Its labels, shopping preference checkbox, and order controls are
specific to this demonstration.

`agent-context` events expose authorized structured return context to the page.
Application code decides how to use it. A different UI can implement the same
send/snapshot/output flow against its own backend. A toolkit such as CopilotKit
would need an adapter between its frontend protocol and that backend; no such
adapter is implemented here.

See the [UAAP App SDK](../../libraries/app-sdk/README.md) for the backend and
[shopping walkthrough](../../docs/shopping-demo.md) for the full demonstration.
