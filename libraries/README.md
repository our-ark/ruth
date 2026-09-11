# UAAP SDKs

UAAP has two complementary SDKs, both maintained in the Ruth repository:

| SDK | Used by | Responsibility |
| --- | --- | --- |
| [Agent SDK](agent-sdk/README.md) | A personal agent | Connect to app-hosted interfaces, receive messages and app context, and deliver replies with authorized user context. |
| [App SDK](app-sdk/README.md) | An application backend | Store message-time context, expose message delivery/context exchange APIs, correlate replies, and enforce the app's disclosure policy. |

Both SDKs use Python 3.11+ and the standard library. Neither requires Ruth's
runtime, a particular model, or a frontend framework. Ruth's shopping client
uses the agent SDK; DAYFORM and STRIDE use the app SDK.

```text
Personal agent                         Application
  continuing conversation                domain logic and local state
  Agent SDK  -- outbound UAAP calls -->  App SDK
                                          application-owned UI
```

The application UI is replaceable. It may be custom-built or use a toolkit
such as CopilotKit. CopilotKit uses AG-UI for its frontend/backend connection;
connecting that UI to a UAAP app requires an adapter. This repository does not
currently include a CopilotKit/AG-UI bridge. See the
[CopilotKit documentation](https://docs.copilotkit.ai/agentic-protocols/ag-ui).

The existing `<agent-chat>` widget is an optional shopping demonstration,
documented under [example UI](../examples/shopping/agent-ui.md). Its assets remain
bundled with the app SDK for existing demo URLs; the message/context APIs work
without serving or using them. Uniform UI is not a UAAP requirement.

Start with the [protocol](../protocol/README.md), then choose the SDK for your
side of the integration. Domain actions such as product search and ordering
remain ordinary app APIs alongside UAAP.
