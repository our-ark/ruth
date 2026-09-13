# Prototype validation

This is an implementation check, not an empirical evaluation of the paper's
architecture hypothesis.

## Release and regression checks — 2026-09-13

On macOS with Python 3.12, a fresh virtual environment built the current Ruth
and both SDKs plus pinned upstream packages using `scripts/prepare_tests.py`.
`pip check` passed. `scripts/test.py` then completed:

- **890 agent/UAAP tests:** 889 passed, one inherited check skipped because it
  inspects the upstream Telegram vision library's source-only lineage metadata.
- **Four release tests, all passed:** dependency-manifest parity; an installed
  Ruth task using independent provider/profile/extension packages; SDK license,
  metadata, and static-asset packaging; and an isolated installed-SDK HTTP round
  trip for messages, bidirectional context, replay, and presence without Ruth.
- **Two Node harnesses, both passed:** activity focus, visibility, heartbeat,
  context retry, reload, and cleanup; repeat-order controls, pending requests,
  reminders, and product/size isolation.

The agent tests include independent activity processing, expiring and ambiguous
presence, debounced app-switch announcements, and mirroring website questions
and replies into Telegram. Chat transports and reasoning are mocked; these
results do not claim a new live Telegram or model evaluation.

The release tests now run separately from the inheritable agent body. They use
the independently packaged upstream libraries instead of assuming Enoch's
library source directories exist inside Ruth. The same commands are configured
in [CI](../.github/workflows/tests.yml) for Linux and macOS; see
[CONTRIBUTING.md](../CONTRIBUTING.md) to reproduce them.

## Real-runtime manual walkthrough — 2026-09-10

Executed with Ruth's configured Codex runtime, two local HTTP app servers,
real browser chat components, and isolated demo state. Console input/output
substituted for Telegram; no messages were sent to a live Telegram account.

| Step | Observed result |
| --- | --- |
| `/shop` for work sneakers, US 9, comfort first, $120 total | Ruth queried both mock catalogs and recommended Day One ($107.80 with mock tax). It correctly identified Arc 02's $123.20 total as over budget. |
| Request the second store link | Ruth supplied Arc 02's STRIDE STUDIO link in the continuing session. |
| DAYFORM: “Would this pair be comfortable for the walk I told you about?” | Ruth identified Day One from the app snapshot and used the earlier commute/comfort preference and budget. |
| Opt into sharing shopping preferences | DAYFORM displayed budget $120, US 9, and “walk to the office” from Ruth's structured return context. |
| STRIDE: “How does this pair compare with the first one?” | Ruth compared Arc 02 against Day One, retaining comfort and budget preferences. It calculated the difference in totals as $15.40. |
| Return to DAYFORM and request a simulated order | The website confirmed Day One, US 9, $107.80; Ruth delivered the receipt to that website session and emitted the console notification. App polling stopped. |

This demonstrates execution of the message/context contracts and model-based
continuation for one walkthrough. It does not establish general task success,
token savings, latency improvements, security against adversarial applications,
or effectiveness across arbitrary runtimes and independently developed apps.

## Automated checks

`tests/test_ruth_shopping.py` uses actual HTTP servers and SQLite databases with
a deterministic reasoning fixture. It tests shared runtime session identity,
message-time product snapshots, cross-app references, source-session routing,
preference-disclosure scope, output replay, unknown order outcomes, Telegram
notification retry, bounded unavailable-runtime attempts, and task cancellation
without conversation deletion. The command-dispatch check enters through
`RuthApplication.handle_event` with a Telegram-compatible test provider.

The inherited Telegram, runtime, application, command registry, daemon,
authorization and effect tests provide regression coverage. Remote/phone access
still requires configured deployment testing.

## Telegram recommendation photos

The grouped-photo update passes 18 shopping/transport tests and 255 existing
application, Telegram, notification and effect-fencing tests. These include one
multipart album upload, numbered captions with all links intact, Unicode caption
limits, source-app image restrictions, and replay protection. The command-dispatch
test verifies that a successful album replaces the separate text recommendation,
that a failed album falls back to text once, and that app replies stay in the app.
The automated Telegram transport is mocked; it does not establish live delivery.

These photo-update results predate website-to-Telegram mirroring. The current
implementation also mirrors new website questions and Ruth replies to Telegram;
the September 13 regression checks above cover this newer behavior.

A live check consolidated the latest saved recommendation (Day One, Arc 01 and
Day One Lite) through the same album delivery path. A single sendMediaGroup upload
returned three message IDs sharing one media_group_id, and the album receipt was
recorded as delivered. This checks Telegram grouping and delivery for the demo
catalogs, not remote access to the local stores or every Telegram client's layout.
