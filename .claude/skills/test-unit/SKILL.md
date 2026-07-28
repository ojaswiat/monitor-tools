---
name: test-unit
description: Runs the monitor engine's unit test suite (tests/unit/) — fast, isolated pytest tests with no subprocess/install-flow dependencies. Use when asked to run unit tests, check the engine's core logic, or verify a change to a single script didn't break its contracts.
---

# test-unit

Runs `tests/unit/` — one function/behavior at a time, each against a fresh
`tmp_path` scratch project (via `tests/conftest.py`'s `project_root`
fixture), never this repo's own real `monitor/` directory.

## Flow

1. Ensure pytest is available: `python3 -m pip install -r requirements-dev.txt -q`
   (skip if already importable — check with `python3 -c "import pytest"`
   first, only install on failure).
2. Run: `PYTHONPATH=plugins/monitor/skills/monitor/scripts pytest tests/unit/ -v`
3. Relay the pass/fail summary and, on any failure, the failing test names
   and assertion output verbatim — don't paraphrase a traceback.

## Notes

- This skill is not part of the `monitor` plugin; it is never copied into
  `plugins/monitor/`.
- Distinct from `test-integration` (multi-script flows) and `test-e2e`
  (live dogfood drill against real cloned repos, manual/on-demand only).
