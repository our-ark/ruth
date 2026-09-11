# Ruth

**One Agent, Anywhere: Personal Agents Accompanying Users Across Applications.**

Ruth is an independently versioned personal agent descended from
[Enoch](https://github.com/our-ark/enoch), created with
[Genesis](https://github.com/our-ark/genesis). This repository contains her
software body; each local instance has its own private state.

Ruth includes a local cross-application shopping prototype: two mock stores
share an app API and chat UI SDK, while `/shop` connects them to Ruth's existing
conversation and model runtime. See the [runnable walkthrough](docs/shopping-demo.md).

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

## Application collaboration

Applications contribute local state and domain intelligence. Ruth contributes
the user's continuing context, preferences, and goals. The same conversation
continues across Telegram and participating applications.

The prototype focuses on message delivery and bidirectional context exchange.
Ruth polls two registered apps during an active shopping task. Each message
carries its page/product snapshot, and each answer goes back to its source
session. Ordinary product APIs support search, details and simulated orders.
No dynamic user tracking or public inbound Ruth endpoint is required.

All code is in this repository: `libraries/app-sdk`, `examples/shopping`, and
`src/ruth/shopping`. The SDK is independent of Ruth's runtime. Try the local
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
