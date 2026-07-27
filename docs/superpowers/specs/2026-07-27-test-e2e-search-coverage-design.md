# test-e2e search coverage — design spec

## Summary

`.claude/skills/test-e2e/SKILL.md`'s subagent template exercises logging,
reporting, tasks, and the pending-hook gate, but never `/monitor:search` —
the one remaining command in monitor's own commands table (`search.py`,
already shipped on `dev`) that the dogfood drill never touches. Add a
step that exercises it, mirroring how tasks/hooks coverage was added.

## Why

`/monitor:search` is a real developer-facing command (search the operations
log by keyword/branch/status/level), identical tier to `/monitor:log` or
`/monitor:report`. Every other command has drill coverage; this one has
none, so a regression in `search.py` would never surface from a drill run.

## Change

New step in the subagent prompt template, after the existing pending-hook
step and before the final report step: run `/monitor:search` (via
`search.py --project-root . --query "<text>"`) for a keyword known to
appear in at least one of the subagent's own log entries (e.g. a word from
one of its `--summary`/`--details` fields), verify the output actually
contains a matching entry (not empty, not an error), and paste the query
plus one matched result block verbatim into the final report.

The report-step evidence list and the orchestrator's step-4 verification
and step-5 report-synthesis columns each get one addition: search-test
result (pass/fail, with the query used).

## Non-goals

- No change to `search.py` itself — it already works; this is purely drill
  coverage.
- No change to the 3-repo/3-companion-level matrix, containment rules, or
  worktree cleanup notes.

## Testing

No test suite in this repo. Validate by running `/test-e2e` once after the
change and confirming each subagent's report includes a real search query
and a real matched result, not a placeholder.
