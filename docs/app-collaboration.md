# Application collaboration

This is the intended scope of Ruth's next capability, not an implemented
integration.

Applications today integrate their own AI assistants. We explore a different
future: users bring the same persistent personal agent with them across
applications. Each application contributes local state and domain intelligence;
the personal agent contributes the user's continuing context, preferences,
and goals.

## Two contracts

1. **Message delivery:** carry user messages from the current application to
   Ruth and deliver her replies through the appropriate connected surface.
2. **Context exchange:** provide local page, product, activity, and task state
   to Ruth; provide authorized user context or collaboration outputs to the app.

One continuing conversation can span applications and tasks. An application
session binds access and delivery; it does not create a separate conversation.
Cross-app context available to Ruth is not automatically disclosed to every app.
Applications can retain their own models and agents.

## Connection lifecycle

A user initiates a task through an already connected channel such as Telegram.
Ruth selects a small set of relevant, compatible applications and establishes
authorized outbound event connections before recommending their links. SSE
streams are preferred; finite cursor-based polling is a fallback.

App frontends report visits, page changes, and foreground/background activity to
their own backends. Events include session/device identity, local sequence,
observation time, and freshness information. Ruth can estimate the current
surface from fresh events; conflicting or stale activity remains uncertain.

All selected applications stay connected while the user switches and returns.
Finishing or cancelling the task closes these connections after required final
results are delivered. Conversation and memory persist. Unselected apps and
later visits after monitoring has stopped are outside automatic tracking.

The application exposes the protocol interface. Ruth does not need a public
inbound endpoint, and this bounded design does not require an OurArk relay.
Actions such as product queries and ordering can use existing authorized app
APIs; they are not a third new protocol.

## Intended demonstration

Telegram -> shopping app A -> shopping app B -> app A -> Telegram.

The shopping apps have different page and chat UIs. Ruth retains the budget,
preferences, product comparisons, and ongoing conversation throughout. An
optional simulated order ends with a Telegram notification.

Implementation should reuse the inherited provider and extension boundaries
and one governed task lifecycle. App-provided content remains untrusted input;
receiving context does not grant authority over private memory or tools.
