# Two UAAP apps, one Ruth

DAYFORM and STRIDE STUDIO use separate catalogs, databases and ports. Their
storefronts differ, while the [UAAP App SDK](../../libraries/app-sdk/README.md)
and product controller are shared. Both apps implement the same
[UAAP message delivery and context exchange contracts](../../protocol/README.md).
Product queries and simulated ordering use their ordinary domain APIs.

The [shared chat UI](agent-ui.md) is optional example code. Ruth connects through
the separate [UAAP Agent SDK](../../libraries/agent-sdk/README.md); the app SDK
can also run without any chat component.

Run from the repository root using `bin/ruth-shopping-demo serve`. See the
[walkthrough](../../docs/shopping-demo.md) for the real-runtime console and
Telegram setup. No product, payment, shipping or fit claim is real.
