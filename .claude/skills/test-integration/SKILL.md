---
name: test-integration
description: Runs the monitor engine's integration test suite (tests/integration/) — multi-script flows (task lifecycle, pending-hook dispatch) against a fresh scratch project. Use when asked to run integration tests or verify a cross-script flow still works end to end.
---

# test-integration

Runs `tests/integration/` — exercises multiple engine scripts together
(e.g. the full task start→update→close flow checked against rendered
HTML, or a real `git commit` driving the actual hook entrypoints via
stdin JSON) against a fresh `tmp_path` scratch project.

## Flow

1. Ensure pytest is available: `python3 -m pip install -r requirements-dev.txt -q`
   (skip if already importable — check with `python3 -c "import pytest"`
   first, only install on failure).
2. Run: `PYTHONPATH=plugins/monitor/skills/monitor/scripts pytest tests/integration/ -v`
3. Relay the pass/fail summary and, on any failure, the failing test names
   and assertion output verbatim — don't paraphrase a traceback.

## Notes

- This skill is not part of the `monitor` plugin; it is never copied into
  `plugins/monitor/`.
- Distinct from `test-unit` (single-function checks) and `test-e2e` (live
  dogfood drill against real cloned repos, manual/on-demand only).
