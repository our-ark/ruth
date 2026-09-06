# Ruth

**One Agent, Anywhere: Personal Agents Accompanying Users Across Applications.**

Ruth is an independently versioned personal agent descended from
[Enoch](https://github.com/our-ark/enoch), created with
[Genesis](https://github.com/our-ark/genesis). This repository contains her
software body; each local instance has its own private state.

The Enoch foundation is initialized and has passed its inherited creation
tests. Ruth's cross-application message and context protocol is planned work;
it is not implemented by this initial import.

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
```

Use Ruth's own Telegram bot and authorized chat. After configuring them,
`bin/ruth-daemon start` starts the instance. The provider supports interactive
setup so credentials need not be committed to code.

## Planned collaboration skill

Applications contribute local state and domain intelligence. Ruth contributes
the user's continuing context, preferences, and goals. The same conversation
continues across Telegram and participating applications.

The initial protocol focuses on message delivery and bidirectional context
exchange. Ruth opens outbound connections to a small set of applications for
an active task, using app-hosted SSE event streams or bounded polling. Apps
report activity and page context through those connections. Actions can use
the apps' existing APIs. See [the design boundary](docs/app-collaboration.md).

## Provenance

- Ancestor: Enoch, commit `b16f6acf3d7664b21161b1a743e48f76a66b90bd`.
- Body identity: [`src/ruth/body.yaml`](src/ruth/body.yaml), generation 4.
- Parent and birth revisions: [`.agent/lineage.yaml`](.agent/lineage.yaml).
- Creation details and validation: [bootstrap notes](docs/bootstrap.md).

The inherited body retains its Apache-2.0 license. This repository is private.
