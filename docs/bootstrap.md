# Ruth bootstrap

Created on 2026-09-06 with Genesis from the Git-tracked Enoch body.

- Enoch source: `b16f6acf3d7664b21161b1a743e48f76a66b90bd`.
- Genesis base: `ab7159935692141a9e0fb8fba474b3c58eafcc46`.
- Local Genesis fix: `b4afcface24f26df8681553b55cd61d907262ec1`.
- Ruth birth: `d14ec1ecf9c939bebca1f18d91d8155f883ba0ec`.

Genesis copies and identity-transforms the declared body paths, initializes a
new Git history, and records the immutable parent and birth revisions. It does
not copy the ancestor's private instance state or transplant its entire Git
history. Runtime library references remain pinned to immutable Enoch commits;
the post-birth Telegram correction below aligns its installed package with the
inherited body's expected configuration.

## Creation-tool correction

The original Genesis transformation preserved a hard-coded profile-list order.
Renaming `enoch` to `ruth` changes its alphabetical position relative to
`researcher`, causing one inherited test to fail. The local fix re-sorts that
expected display string after identity transformation, preserving the original
test's behavior check. It does not change runtime profile behavior.

The fix and a regression test covering descent in both alphabetical directions
are preserved in [`bootstrap/genesis-profile-order.patch`](bootstrap/genesis-profile-order.patch).
The patch uses zero context; apply it to the Genesis base with
`git apply --unidiff-zero genesis-profile-order.patch`.
They were developed in an isolated Genesis worktree; neither Genesis's main
branch nor Enoch's body was modified for Ruth's creation.

## Installed-provider correction

Enoch's tracked Telegram library included `TelegramConfig.bot_peers`, but the
inherited dependency manifests still pointed to an older library commit.
Genesis's local-source validation used the newer checked-out library, while
Doctor against the installed reference providers exposed the mismatch.

Ruth pins Telegram to `13c7b266f70c8c5c3b1ba3907130000e6e23966f`, the
ancestor commit that introduced those fields. Both `pyproject.toml` and
`genesis.toml` use this revision. This is a post-birth dependency correction;
the recorded Enoch parent and Ruth birth revisions are unchanged.

Doctor may use a separate managed Python environment for tests. That
environment also needs the reference providers used by the inherited
integration tests. Installing the body with `.[reference]` in both the runtime
and Doctor-selected test environment supplies them.

## Validation

- Genesis: 39 tests passed, including the new descendant-order regression.
- Ruth: Genesis accepted both inherited pre-birth validation gates, using
  Python 3.13 and `python -m unittest discover -s tests -t .`.
- The inherited suite contains 844 tests; the creation environment skips seven
  optional tests. No skip was added to work around the profile failure.
- Instance Doctor passed after the installed-provider correction: inherited
  tests, import checks, build backend, authenticated Codex runtime and GitHub
  forge, clean worktree, and private-state storage checks all passed. Runtime
  and test environments also passed `pip check`.

The application collaboration protocol remains planned work. These checks
validate the inherited agent foundation, not cross-application interoperability.
