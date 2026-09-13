# Contributing to Ruth

Ruth is a research prototype for one personal agent collaborating with its user
across applications. Changes should preserve the continuing conversation,
message-time context snapshots, source-session reply routing, and explicit
context disclosure. Product search and simulated ordering remain app APIs.

## Set up and test

Use a source checkout with Git, Python 3.11 or newer, and Node.js 22 or newer.
Run these commands from the repository root on macOS or Linux:

```bash
python3 -m venv .venv
.venv/bin/python scripts/prepare_tests.py
.venv/bin/python scripts/test.py
```

Preparation needs network access. It builds the current Ruth and both local
SDKs, plus the upstream dependency revisions pinned in `genesis.toml`, into
`.ruth/test-wheels/`. It installs them only in this virtual environment and
checks their dependency metadata. It does not require access to another private
repository or fetch an older Ruth SDK revision. Rerun preparation after changes
to SDK code, dependencies, or package metadata so distribution tests see fresh
artifacts.

The test command disables pip index access and runs:

- The agent and UAAP Python suite, including actual loopback HTTP/SQLite tests
  with deterministic reasoning and mocked chat transports.
- Distribution checks in `release_tests/`: an installed Ruth task with separate
  provider/profile/extension packages; SDK license and static-asset packaging;
  and message/context/presence exchange using only the installed SDK wheels.
- Node tests for browser activity reporting and shopping order state.

CI runs these commands on Linux with Python 3.11, 3.13, and 3.14, and macOS with
Python 3.13. The suite creates disposable state and repositories. It needs no
live model, Telegram, or GitHub account and does not start an instance daemon.
The release suite is outside the Genesis-inheritable `tests/` directory because
it requires the complete source checkout and distribution build tools.

For a focused change, use the prepared environment to run a module:

```bash
OUR_ARK_RUNTIME_DEPENDENCY_PATHS="$PWD/.venv/lib/python3.13/site-packages" \
  .venv/bin/python -m unittest tests.test_uaap_sdk
```

Adjust `python3.13` to your virtual environment's Python version. Use the
canonical `tests.*` module name so the private-state isolation fixture loads.
`scripts/test.py` resolves this environment path automatically for the full run.

## Propose a change

Open an issue or pull request explaining the behavior and relevant validation.
Use synthetic examples in fixtures, logs, and screenshots. Keep bot tokens,
private conversations, instance state, and local databases outside Git.
Document changes to the two UAAP contracts in `protocol/`; keep UI-specific
behavior optional. Preserve upstream provenance and license notices.

The current app server is a local, single-account reference implementation.
Production authentication, account isolation, and deployment are separate work;
passing the prototype tests does not establish those properties. Report live
walkthroughs separately from mocked tests or proposed architecture features.
