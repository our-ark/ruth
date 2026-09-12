# Ruth

**One Agent, Anywhere: Personal Agents Accompanying Users Across Applications.**

Ruth is an independently versioned personal agent descended from
[Enoch](https://github.com/our-ark/enoch), created with
[Genesis](https://github.com/our-ark/genesis). This repository contains her
software body; each local instance has its own private state.

Ruth is the reference personal agent for **UAAP — User–Agent–App Protocol**.
UAAP enables collaboration among users, their persistent personal agents, and
applications through **message delivery and context exchange**. The personal
agent maintains continuity; applications retain domain authority; the user
governs their collaboration.

The local shopping prototype connects two mock stores through the shared
UAAP App SDK. `/shop` brings them into Ruth's existing conversation and model
runtime. Start with the [UAAP protocol](protocol/README.md),
[two SDKs](libraries/README.md), or
[runnable walkthrough](docs/shopping-demo.md).

## UAAP in this repository

**One Agent, Anywhere** is the vision; **UAAP** defines the collaboration
contracts; **Ruth** demonstrates them as a persistent personal agent.

| Location | Role |
| --- | --- |
| [`protocol/`](protocol/README.md) | UAAP working draft: roles, message/context semantics, and the current HTTP mapping |
| [`libraries/agent-sdk/`](libraries/agent-sdk/README.md) | UAAP Agent SDK: outbound app connections, event reads, and reply delivery |
| [`libraries/app-sdk/`](libraries/app-sdk/README.md) | UAAP App SDK: backend message/context storage and app-hosted APIs |
| [`src/ruth/shopping/`](src/ruth/shopping) | Ruth's UAAP integration, task lifecycle, and shopping orchestration |
| [`examples/shopping/`](examples/shopping/README.md) | DAYFORM and STRIDE: two participating apps with different storefronts |

Both SDKs are independent of Ruth's model and runtime. Applications choose
their own UI; the shared shopping chat component is an
[optional example](examples/shopping/agent-ui.md). The app SDK provides a
generic message/context store and the existing shopping adapter. Product
search and ordering use ordinary app APIs.

## Mission

Accompany her human across applications as one persistent personal agent, maintaining a continuing conversation and memory while exchanging authorized context and messages with each application and using its existing action APIs when requested.

## Local instance

Requires Git and Python 3.11 or newer. The launcher installs pinned core
dependencies into ignored private state on first use.

```bash
bin/ruth status
bin/ruth init --instance local --worktree ../ruth-local
cd ../ruth-local
bin/ruth status
bin/ruth state validate
```

The source checkout stays on `main`. The instance uses its own
`agent/ruth-local` worktree branch and ignored `.ruth/` state. Instance
metadata lives in `.agent/instance.yaml`. Credentials, memory, logs, runtime
dependencies, and personal identity are never inherited from Enoch or
committed to this repository.

`bin/ruth` opens the administrative CLI. Conversation uses a configured chat
provider; creating an instance does not start a daemon or contact a user.

## Connect Telegram

From the instance directory, install the inherited reference providers in a
private virtual environment:

```bash
python3.13 -m venv .ruth/venv
.ruth/venv/bin/python -m pip install -e '.[reference]'
export RUTH_PYTHON="$PWD/.ruth/venv/bin/python"
bin/ruth config provider chat telegram
bin/ruth setup
bin/ruth setup chat <your-chat-id>
```

Use Ruth's own Telegram bot and authorized chat. After configuring them,
`bin/ruth-daemon start` starts the instance. The provider supports interactive
setup so credentials need not be committed to code.

## Application collaboration with UAAP

Applications contribute local state and domain intelligence. Ruth contributes
the user's continuing context, preferences, and goals. The same conversation
continues across Telegram and participating applications.

The prototype focuses on message delivery and bidirectional context exchange.
Ruth polls two registered apps during an active shopping task. Each message
carries its page/product snapshot, and each answer goes back to its source
session. Ordinary product APIs support search, details and simulated orders.
Connected apps can also report page context and focused-session presence through
the optional UAAP `context-presence/1` extension. `/shop status` shows Ruth's
current observation; stable app changes also produce brief Telegram updates.
Stale presence expires to unknown. No public inbound Ruth
endpoint is required.

All code is in this repository: `libraries/agent-sdk`, `libraries/app-sdk`,
`examples/shopping`, and `src/ruth/shopping`. Try the local
stores and real-model console in two terminals:

```bash
bin/ruth-shopping-demo serve --root "$PWD/.ruth/shopping-demo"
bin/ruth-shopping-demo console --root "$PWD/.ruth/shopping-demo"
```

Then enter `/shop work sneakers, US 9, under $130 total` in the console. The
[walkthrough](docs/shopping-demo.md) also explains how to use the same flow
through the instance's configured Telegram bot. See the broader
[design boundary](docs/app-collaboration.md) for future extensions.

## Provenance

- Ancestor: Enoch, commit `b16f6acf3d7664b21161b1a743e48f76a66b90bd`.
- Body identity: [`src/ruth/body.yaml`](src/ruth/body.yaml), generation 4.
- Parent and birth revisions: [`.agent/lineage.yaml`](.agent/lineage.yaml).
- Creation details and validation: [bootstrap notes](docs/bootstrap.md).

The inherited body retains its Apache-2.0 license. This repository is private.
