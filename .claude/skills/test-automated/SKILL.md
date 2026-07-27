---
name: test-automated
description: Runs the full automated check set for monitor — unit tests, integration tests, and the thought-leak scan — in one pass. Use when asked to run all automated tests, do a full check before finishing a branch, or verify nothing regressed after an engine change. Does not run test-e2e (the live dogfood drill stays manual/on-demand).
---

# test-automated

Runs, in order, reporting each result separately (never merged into one
opaque pass/fail):

1. **Unit tests** — `pip install -r requirements-dev.txt -q` (skip if
   pytest already importable), then
   `PYTHONPATH=plugins/monitor/skills/monitor/scripts pytest tests/unit/ -v`.
2. **Integration tests** —
   `PYTHONPATH=plugins/monitor/skills/monitor/scripts pytest tests/integration/ -v`.
3. **Thought-leak scan** — `python3 scripts/check_thought_leaks.py`; per
   `test-thought-leaks`'s own rule, a nonzero exit means candidates to
   review by hand, not an automatic failure — read each hit and judge it
   yourself before reporting this step's outcome.

## Flow

Run all three in sequence (stop and report immediately if either pytest
run fails — don't run the next step on top of a known-broken suite; the
thought-leak scan has no such gate since its own hits require judgment,
not a hard stop). Relay one summary at the end: unit (pass/fail count),
integration (pass/fail count), thought-leaks (clean / N reviewed, M fixed).

## Notes

- This skill is not part of the `monitor` plugin; it is never copied into
  `plugins/monitor/`.
- Does **not** invoke `test-e2e` — that stays manual/on-demand, run
  separately whenever a live dogfood drill against real cloned repos is
  wanted.
