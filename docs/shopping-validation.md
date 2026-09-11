# Prototype validation — 2026-09-10

This is an implementation check, not an empirical evaluation of the paper's
architecture hypothesis.

## Real-runtime manual walkthrough

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
authorization and effect tests provide regression coverage. Live Telegram
delivery and remote/phone access still require configured deployment testing.
