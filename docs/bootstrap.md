# Ruth bootstrap

Created on 2026-09-06 with Genesis from the Git-tracked Enoch body.

- Enoch source: `b16f6acf3d7664b21161b1a743e48f76a66b90bd`.
- Genesis base: `ab7159935692141a9e0fb8fba474b3c58eafcc46`.
- Local Genesis fix: `b4afcface24f26df8681553b55cd61d907262ec1`.
- Ruth birth: `d14ec1ecf9c939bebca1f18d91d8155f883ba0ec`.

Genesis copies and identity-transforms the declared body paths, initializes a
new Git history, and records the immutable parent and birth revisions. It does
not copy the ancestor's private instance state or transplant its entire Git
history. Runtime library references remain pinned to their original Enoch
commits.

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

## Validation

- Genesis: 39 tests passed, including the new descendant-order regression.
- Ruth: Genesis accepted both inherited pre-birth validation gates, using
  Python 3.13 and `python -m unittest discover -s tests -t .`.
- The inherited suite contains 844 tests; the creation environment skips seven
  optional tests. No skip was added to work around the profile failure.

The application collaboration protocol remains planned work. These checks
validate the inherited agent foundation, not cross-application interoperability.
