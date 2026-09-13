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

## Demo video

[![Watch Ruth — One Agent, Anywhere on YouTube](https://img.youtube.com/vi/onO0yoVqc_s/hqdefault.jpg)](https://www.youtube.com/watch?v=onO0yoVqc_s)

**[Watch the two-minute animated demo on YouTube](https://www.youtube.com/watch?v=onO0yoVqc_s).**

Follow a Tokyo trip across **Airside**, **Staywell**, and **Daylight**, using the
[OneAgent travel sample apps](https://github.com/our-ark/oneagent/tree/main/examples/travel).
The video shows conversation and context continuity across apps, website
exchanges collected in Telegram, and an introduction to the One Agent, Anywhere
architecture and paper.

The video is an animated walkthrough with Ruth as the personal agent. The
runnable integration in this repository is the
[DAYFORM and STRIDE shopping demo](docs/shopping-demo.md).

## Current capabilities

The DAYFORM and STRIDE shopping demo supports:

- **Website conversations in Telegram.** With Telegram configured, every new
  website question and Ruth reply also appear in the same Telegram chat, labeled
  with the store and product. Website turns reuse Ruth's existing conversation
  context. Earlier website conversations are not backfilled.
- **Current app and page awareness.** Connected apps report page/product context
  and foreground presence without requiring another chat message. `/shop status`
  shows the observed app and product, or reports ambiguous or unknown presence.
- **Telegram updates when you switch apps.** Ruth announces the first stable app
  arrival and subsequent switches, such as DAYFORM → STRIDE STUDIO, including the
  viewed product when known. Brief focus changes are debounced; heartbeats and
  product changes within the same app do not trigger extra announcements.

App awareness runs during an active `/shop` task and covers only connected app
sessions. Stale presence expires to unknown; `/shop cancel` stops polling and
app-switch announcements. See the [walkthrough](docs/shopping-demo.md) for setup
and examples.

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
bin/ruth state migrate
bin/ruth state validate
```

The source checkout stays on `main`. The instance uses its own
`agent/ruth-local` worktree branch and ignored `.ruth/` state. Instance
metadata lives in `.agent/instance.yaml`. Credentials, memory, logs, runtime
dependencies, and personal identity are never inherited from Enoch or
committed to this repository.

`state migrate` initializes the private-state manifest for a new instance. For
an existing instance, `bin/ruth state migrate --dry-run` previews changes;
migration preserves backups of files it updates.

`bin/ruth` opens the administrative CLI. Conversation uses a configured chat
provider; creating an instance does not start a daemon or contact a user.

## Connect Telegram

From the instance directory, install the inherited reference providers in a
private virtual environment:

```bash
python3 -m venv .ruth/venv
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

The optional UAAP
[`context-presence/1` extension](protocol/README.md#optional-extension-context-presence1)
adds a separate activity feed for page context and focused-session presence.
Ruth processes it independently of message reasoning, so observations can update
while a model turn is running. The feed retains the latest context and presence
per session, rather than a complete browsing history. Apps can adopt the
extension without changing the core message flow. No public inbound Ruth
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

Ruth and both UAAP SDKs use the [Apache-2.0 license](LICENSE). Each SDK
distribution includes the license text.

## Development

See [CONTRIBUTING.md](CONTRIBUTING.md) for an isolated setup and the same Python,
JavaScript, and package-install checks used in CI. Tests use synthetic data and
mock providers; they do not require a Telegram token or a model subscription.
The [validation notes](docs/shopping-validation.md) distinguish automated checks
from historical live demonstrations.

This is a research prototype. The reference app server is intended for local,
single-account use, and all shopping orders are simulated. See the
[SDK deployment boundary](libraries/app-sdk/README.md) before adapting it to a
hosted service.
