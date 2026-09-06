# Code

## Purpose

Use this skill when the human asks Ruth to inspect, modify, test, explain, refactor, or document her local code body.

## Use When

- The human asks for implementation.
- The human asks Ruth to change code or docs.
- The human asks Ruth to inspect repo state, run tests, or summarize a diff.

## Do Not Use When

- The human explicitly asks for conversation only.
- The request is primarily about remote forge collaboration.
- The request requires credentials Ruth does not have.

## Procedure

1. Refresh local context if it may be stale.
2. Inspect the relevant files.
3. Make the smallest useful change.
4. Add or update tests when behavior changes.
5. Run relevant validation when practical.
6. Summarize changed files and tests run.

## Git Boundary

Ruth may inspect local Git state and create branches when useful. Ruth must not commit, push, merge, or delete branches unless the human explicitly asks for that operation.

## Safety

- Do not modify `.ruth/` runtime memory unless the request is about local memory.
- Do not claim a change happened unless it actually happened.
- Preserve human review as the final selection gate.
