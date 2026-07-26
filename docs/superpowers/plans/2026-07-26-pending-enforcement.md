# Pending-State Enforcement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the soft Y/N pending-state gate from `docs/superpowers/specs/2026-07-25-pending-enforcement-design.md` — a committed `monitor/.pending.json` tracked by two real Claude Code hooks, so an agent gets reminded to log/report at the start of its next turn instead of the policy being purely discretionary.

**Architecture:** A new stdlib-only `pending.py` engine script owns the `monitor/.pending.json` data model (`track`/`check` for manual use and testing, plus two hook-entrypoint subcommands that speak the real Claude Code hook I/O contract — JSON on stdin, JSON on stdout for `UserPromptSubmit`). `logger.py` and `render_report.py` call back into `pending.py` to clear state at the exact moments a log or report actually completes. `/monitor:init` installs the two hooks into the consumer project's `.claude/settings.json`; `/monitor:update` can add them to already-initialized projects.

**Tech Stack:** Python 3 stdlib only (matches the rest of the engine — no new dependencies).

## Global Constraints

- Engine scripts are stdlib-only Python 3, no third-party dependencies (project-wide rule, `CLAUDE.md`).
- Every engine script except `profile.py` calls `mlib.require_init(root)` and exits 2 if `monitor/profile.json` is missing — **except** the two hook-entrypoint subcommands in `pending.py` (`hook-post-tool-use`, `hook-user-prompt-submit`), which must fail silently (exit 0, no output) if monitor isn't initialized, since a hook erroring is user-visible noise, not a real failure.
- Log schema (`REQUIRED`/`LEVELS`/`STATUSES` in `logger.py`) is locked in code — this plan does not touch those constants.
- `monitor/.pending.json` is committed alongside the rest of `monitor/`, not gitignored (per the spec and the standing project rule that `monitor/` travels with every commit).
- This repo has no automated test suite (standing project decision) — verification steps in this plan run scripts directly against fixture data and check stdout/file contents, not pytest.
- **Real Claude Code hook I/O contract** (confirmed against current docs, not assumed): a hook's `command`+`args` receives a JSON object on **stdin** (includes `tool_input` for tool-scoped events, e.g. `tool_input.command` for a Bash call). A `PostToolUse` hook's own stdout is not specially interpreted, so it should stay silent on success. A `UserPromptSubmit` hook that wants to inject context must print a specific JSON envelope to stdout: `{"continue": true, "hookSpecificOutput": {"additionalContext": "<text>"}}`. The `matcher` field only matches the **tool name** (e.g. `"Bash"`) — it does NOT filter on the command string, so `pending.py`'s own hook entrypoint must read `tool_input.command` from stdin and self-filter for `git commit`/`git merge`/`git rebase`.
- After any change under `plugins/monitor/skills/monitor/`, bump `version` in `plugins/monitor/.claude-plugin/plugin.json` — done once, in the final task.

---

### Task 1: `pending.py` — data model, `track`, `check`

**Files:**
- Create: `plugins/monitor/skills/monitor/scripts/pending.py`

**Interfaces:**
- Consumes: `monitor_lib.add_root_arg`, `monitor_lib.resolve_root`, `monitor_lib.monitor_dir`, `monitor_lib.load_json`, `monitor_lib.save_json`, `monitor_lib.git_branch`, `monitor_lib.git_last_commit` (all existing, `monitor_lib.py`).
- Produces (used by Task 2 and Task 3): `pending_path(root: Path) -> Path`; `load_pending(root: Path) -> dict`; `save_pending(root: Path, data: dict) -> None`; `track(root: Path, event: str, sha: str | None, message: str) -> None` (`event` is `"commit"`, `"merge"`, or `"rebase"`); `check_text(root: Path) -> str` (returns the warning text, or `""` if nothing pending — Task 3's hook entrypoint wraps this in the JSON envelope); `clear_log(root: Path, sha: str) -> None`; `clear_report(root: Path) -> None`. `WARNING` module-level constant (the exact warning + Y/N instruction text).

- [ ] **Step 1: Write `pending.py`**

```python
#!/usr/bin/env python3
"""Track and check monitor's pending log/report state (monitor/.pending.json).

Stdlib-only. `track` and `check` are the plain, directly-testable CLI
commands; `hook-post-tool-use` and `hook-user-prompt-submit` (added in a
later task) are the actual Claude Code hook entrypoints that speak the real
hook I/O contract. See "Pending-state enforcement" in SKILL.md.

Usage:
  python3 pending.py --project-root <repo> track --event commit --sha <sha> --message "<msg>"
  python3 pending.py --project-root <repo> track --event merge
  python3 pending.py --project-root <repo> check
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import monitor_lib as mlib

_DEFAULT = {"branch": "", "pending_logs": [], "pending_report": None,
            "last_report_sha": ""}


def pending_path(root: Path) -> Path:
    return mlib.monitor_dir(root) / ".pending.json"


def load_pending(root: Path) -> dict:
    data = mlib.load_json(pending_path(root), dict(_DEFAULT))
    for key, default in _DEFAULT.items():
        data.setdefault(key, default)
    return data


def save_pending(root: Path, data: dict) -> None:
    mlib.save_json(pending_path(root), data)


def _sha_exists(root: Path, sha: str) -> bool:
    try:
        out = subprocess.run(["git", "-C", str(root), "cat-file", "-e", sha],
                              capture_output=True, timeout=5)
    except Exception:  # noqa: BLE001 — git missing/unusable means "doesn't exist"
        return False
    return out.returncode == 0


def track(root: Path, event: str, sha: str | None, message: str) -> None:
    data = load_pending(root)
    data["branch"] = mlib.git_branch(root)
    head = sha or mlib.git_last_commit(root)
    now = datetime.now().isoformat(timespec="seconds")
    if event == "commit":
        if head and not any(e["sha"] == head for e in data["pending_logs"]):
            data["pending_logs"].append(
                {"sha": head, "message": message, "committed_at": now})
    else:  # "merge" or "rebase"
        # Rebase rewrites shas — drop any pending_logs entry whose sha no
        # longer resolves; its content is folded into the report range via
        # since_sha instead of tracked individually. A no-op filter on a
        # plain merge (no rewrite happened).
        data["pending_logs"] = [e for e in data["pending_logs"]
                                 if _sha_exists(root, e["sha"])]
        data["pending_report"] = {
            "event": event, "since_sha": data.get("last_report_sha") or "",
            "detected_at": now,
        }
    save_pending(root, data)


WARNING = (
    "[Warn!] Monitor: Pending logs and report. Do you want Monitor to record now [Y/N]\n\n"
    "If Y: read monitor/.pending.json. For each pending_logs entry, run "
    "/monitor:log for it (its stored message is a starting point — "
    "DECISION/WHY/etc are still your judgment). For a set pending_report, "
    "run `git log <since_sha>..HEAD` (since_sha is in monitor/.pending.json) "
    "to get the real commit range, then author one /monitor:report covering "
    "it. Continue with the user's original request afterward.\n"
    "If N: say \"Skipping monitor. What next?\" and leave "
    "monitor/.pending.json untouched — it stays pending and will remind "
    "again next turn."
)


def check_text(root: Path) -> str:
    data = load_pending(root)
    if data.get("pending_logs") or data.get("pending_report"):
        return WARNING
    return ""


def clear_log(root: Path, sha: str) -> None:
    data = load_pending(root)
    data["pending_logs"] = [e for e in data["pending_logs"] if e["sha"] != sha]
    save_pending(root, data)


def clear_report(root: Path) -> None:
    data = load_pending(root)
    data["pending_report"] = None
    data["last_report_sha"] = mlib.git_last_commit(root)
    save_pending(root, data)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mlib.add_root_arg(ap)
    sub = ap.add_subparsers(dest="cmd", required=True)

    t = sub.add_parser("track")
    t.add_argument("--event", required=True, choices=("commit", "merge", "rebase"))
    t.add_argument("--sha", default=None)
    t.add_argument("--message", default="")

    sub.add_parser("check")

    args = ap.parse_args()
    root = mlib.resolve_root(args)
    mlib.require_init(root)

    if args.cmd == "track":
        track(root, args.event, args.sha, args.message)
    elif args.cmd == "check":
        text = check_text(root)
        if text:
            print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Verify `track`/`check` by hand against a real git repo**

`_sha_exists` needs real git, so this fixture uses an actual repo:

```bash
cd /tmp && rm -rf pending-fixture && mkdir pending-fixture && cd pending-fixture
git init -q && git commit -q --allow-empty -m "seed"
mkdir -p monitor/scripts
cp /Users/ojaswi/Projects/monitor-tools/plugins/monitor/skills/monitor/scripts/*.py monitor/scripts/
echo '{"project": {"name": "fixture"}}' > monitor/profile.json

SEED_SHA=$(git rev-parse --short HEAD)
python3 monitor/scripts/pending.py --project-root . check
echo "--- (nothing printed above is correct — nothing pending yet) ---"

python3 monitor/scripts/pending.py --project-root . track --event commit --sha "$SEED_SHA" --message "seed"
cat monitor/.pending.json
echo "--- pending_logs should have 1 entry with sha=$SEED_SHA ---"

python3 monitor/scripts/pending.py --project-root . check
echo "--- warning text above should have printed (pending_logs non-empty) ---"

python3 monitor/scripts/pending.py --project-root . track --event merge
cat monitor/.pending.json
echo "--- pending_report should now be set with event=merge, since_sha='' ---"
```

Expected: first `check` prints nothing; `.pending.json` after `track --event commit` shows one `pending_logs` entry with `sha` matching `$SEED_SHA`; `check` after that prints the full `WARNING` text; `.pending.json` after `track --event merge` shows `pending_report.event == "merge"`.

- [ ] **Step 3: Clean up the fixture**

```bash
cd / && rm -rf /tmp/pending-fixture
```

- [ ] **Step 4: Commit**

```bash
git add plugins/monitor/skills/monitor/scripts/pending.py
git commit -m "feat: add pending.py — track/check for monitor/.pending.json"
```

---

### Task 2: Wire `logger.py` and `render_report.py` to clear pending state

**Files:**
- Modify: `plugins/monitor/skills/monitor/scripts/logger.py`
- Modify: `plugins/monitor/skills/monitor/scripts/render_report.py`

**Interfaces:**
- Consumes: `pending.clear_log(root, sha)` and `pending.clear_report(root)` from Task 1.
- Produces: nothing new consumed by later tasks.

- [ ] **Step 1: Clear the matching `pending_logs` entry after a successful log**

In `plugins/monitor/skills/monitor/scripts/logger.py`, `log_operation()` already auto-captures `last_commit_hash` and, after writing the entry, refreshes the Logs page and Dashboard (two `try`/`except` blocks calling `render_logs.render(root)` and `render_report.refresh_dashboard(root)`). Add a third block right after those two, using the same entry's `last_commit_hash`:

```python
    try:
        import pending
        if entry.get("last_commit_hash"):
            pending.clear_log(root, entry["last_commit_hash"])
    except Exception as err:  # noqa: BLE001 — best-effort pending-state update
        print(f"warning: could not update pending state: {err}", file=sys.stderr)
```

This goes inside `log_operation()`, after the existing `render_report.refresh_dashboard(root)` try/except block (which itself follows the `render_logs.render(root)` try/except block) — same function, same indentation level, same defensive try/except pattern already used twice there.

- [ ] **Step 2: Clear `pending_report` exactly when a report is locked in**

In `plugins/monitor/skills/monitor/scripts/render_report.py`, `main()`'s `--lock-report` branch is the precise "a report was just authored" signal — `report.md`/`record.md` always run it as the very next command after writing a new report file, and *only* then. (Deliberately not hooking this into `render_all()`/`render_template()` — those also run during plain `/monitor:init`/`/monitor:update`, which would incorrectly clear a genuinely pending report that the user hasn't answered Y/N on yet.)

Find this block:

```python
    if args.lock_report:
        rel = args.lock_report.split("reports/", 1)[-1]
        changed = lock_report_style(root, rel)
        print(f"{'corrected' if changed else 'already canonical'}: {args.lock_report}")
        return 0
```

Change it to:

```python
    if args.lock_report:
        rel = args.lock_report.split("reports/", 1)[-1]
        changed = lock_report_style(root, rel)
        print(f"{'corrected' if changed else 'already canonical'}: {args.lock_report}")
        try:
            import pending
            pending.clear_report(root)
        except Exception as err:  # noqa: BLE001 — best-effort pending-state update
            print(f"warning: could not update pending state: {err}", file=sys.stderr)
        return 0
```

- [ ] **Step 3: Verify both clears by hand**

```bash
cd /tmp && rm -rf clear-fixture && mkdir clear-fixture && cd clear-fixture
git init -q && git commit -q --allow-empty -m "seed"
mkdir -p monitor/scripts monitor/reports monitor/logs
cp /Users/ojaswi/Projects/monitor-tools/plugins/monitor/skills/monitor/scripts/*.py monitor/scripts/
echo '{"project": {"name": "fixture"}}' > monitor/profile.json
python3 monitor/scripts/render_report.py --project-root .   # seed template.html etc

SHA=$(git rev-parse --short HEAD)
python3 monitor/scripts/pending.py --project-root . track --event commit --sha "$SHA" --message "seed"
grep -c "$SHA" monitor/.pending.json
echo "--- should be 1 (sha present in pending_logs) ---"

python3 monitor/scripts/logger.py --project-root . --operation test-op --tool Bash --summary "test" --status success --branch main
cat monitor/.pending.json
echo "--- pending_logs should now be empty (logger.py auto-captured the same HEAD sha and cleared it) ---"

python3 monitor/scripts/pending.py --project-root . track --event merge
python3 -c "import json; d=json.load(open('monitor/.pending.json')); assert d['pending_report'] is not None; print('pending_report is set: OK')"

echo '<h1>Test</h1><span class="mono">main</span><h2>Summary</h2><p>x</p>' > monitor/reports/2026-01-01-test.html
python3 monitor/scripts/render_report.py --project-root . --lock-report reports/2026-01-01-test.html
python3 -c "import json; d=json.load(open('monitor/.pending.json')); assert d['pending_report'] is None, d; print('pending_report cleared: OK')"
```

Expected: both `print("...OK")` lines execute without an `AssertionError`.

- [ ] **Step 4: Clean up the fixture**

```bash
cd / && rm -rf /tmp/clear-fixture
```

- [ ] **Step 5: Commit**

```bash
git add plugins/monitor/skills/monitor/scripts/logger.py plugins/monitor/skills/monitor/scripts/render_report.py
git commit -m "feat: clear pending state on successful log / --lock-report"
```

---

### Task 3: Hook entrypoints in `pending.py`

**Files:**
- Modify: `plugins/monitor/skills/monitor/scripts/pending.py`

**Interfaces:**
- Consumes: `track()`, `check_text()` from Task 1.
- Produces: two new CLI subcommands, `hook-post-tool-use` and `hook-user-prompt-submit`, invoked by the settings.json hook entries Task 4 installs.

- [ ] **Step 1: Add the hook entrypoints**

In `plugins/monitor/skills/monitor/scripts/pending.py`, add two new functions right after `main()`'s current subparser setup area (before `def main()`), and wire them into `main()`:

```python
import json


_COMMIT_MARKERS = ("git commit",)
_REPORT_MARKERS = ("git merge", "git rebase")


def _monitor_initialized(root: Path) -> bool:
    return (mlib.monitor_dir(root) / "profile.json").exists()


def hook_post_tool_use(root: Path) -> None:
    """PostToolUse hook entrypoint. Silent no-op unless the Bash command that
    just ran was a git commit/merge/rebase — matcher only filters on tool
    name ("Bash"), so this reads tool_input.command itself to self-filter."""
    if not _monitor_initialized(root):
        return
    try:
        payload = json.load(sys.stdin)
    except Exception:  # noqa: BLE001 — malformed/empty stdin, nothing to do
        return
    command = (payload.get("tool_input") or {}).get("command", "") or ""
    if any(m in command for m in _COMMIT_MARKERS):
        track(root, "commit", None, command.strip()[:200])
    elif any(m in command for m in _REPORT_MARKERS):
        event = "rebase" if "git rebase" in command else "merge"
        track(root, event, None, command.strip()[:200])


def hook_user_prompt_submit(root: Path) -> None:
    """UserPromptSubmit hook entrypoint. Prints the JSON envelope Claude Code
    requires to inject additionalContext; prints nothing if not initialized
    or nothing is pending."""
    if not _monitor_initialized(root):
        return
    text = check_text(root)
    if text:
        print(json.dumps({
            "continue": True,
            "hookSpecificOutput": {"additionalContext": text},
        }))
```

Then update `main()` to route to them, bypassing `mlib.require_init()` for these two (per the Global Constraints — a hook must fail silently, not exit 2 with a stderr message):

```python
    sub.add_parser("check")
    sub.add_parser("hook-post-tool-use")
    sub.add_parser("hook-user-prompt-submit")

    args = ap.parse_args()
    root = mlib.resolve_root(args)

    if args.cmd == "hook-post-tool-use":
        hook_post_tool_use(root)
        return 0
    if args.cmd == "hook-user-prompt-submit":
        hook_user_prompt_submit(root)
        return 0

    mlib.require_init(root)
    if args.cmd == "track":
        track(root, args.event, args.sha, args.message)
    elif args.cmd == "check":
        text = check_text(root)
        if text:
            print(text)
    return 0
```

(This replaces the tail of the previous `main()` from Task 1 — the `sub.add_parser("check")` line already exists; add the two new `sub.add_parser(...)` lines directly after it, and replace the body from `args = ap.parse_args()` onward as shown.)

- [ ] **Step 2: Verify both hook entrypoints by hand**

```bash
cd /tmp && rm -rf hook-fixture && mkdir hook-fixture && cd hook-fixture
git init -q && git commit -q --allow-empty -m "seed"
mkdir -p monitor/scripts
cp /Users/ojaswi/Projects/monitor-tools/plugins/monitor/skills/monitor/scripts/*.py monitor/scripts/
echo '{"project": {"name": "fixture"}}' > monitor/profile.json

echo '{"tool_input": {"command": "git commit -m \"test\""}}' | python3 monitor/scripts/pending.py --project-root . hook-post-tool-use
cat monitor/.pending.json
echo "--- pending_logs should have 1 entry ---"

echo '{}' | python3 monitor/scripts/pending.py --project-root . hook-user-prompt-submit
echo "--- above should be one line of JSON: {\"continue\": true, \"hookSpecificOutput\": {\"additionalContext\": \"[Warn!]...\"}} ---"

echo '{"tool_input": {"command": "ls -la"}}' | python3 monitor/scripts/pending.py --project-root . hook-post-tool-use
cat monitor/.pending.json
echo "--- pending_logs should STILL have only 1 entry (a plain ls did not add another) ---"
```

Expected: after the `git commit` line, `.pending.json` has one `pending_logs` entry; `hook-user-prompt-submit` prints exactly one line of valid JSON with `hookSpecificOutput.additionalContext` containing the `[Warn!]` text; the `ls -la` line changes nothing.

- [ ] **Step 3: Clean up the fixture**

```bash
cd / && rm -rf /tmp/hook-fixture
```

- [ ] **Step 4: Commit**

```bash
git add plugins/monitor/skills/monitor/scripts/pending.py
git commit -m "feat: add pending.py hook entrypoints (post-tool-use, user-prompt-submit)"
```

---

### Task 4: Install the hooks + document the feature + version bump

**Files:**
- Modify: `plugins/monitor/commands/init.md`
- Modify: `plugins/monitor/commands/update.md`
- Modify: `plugins/monitor/skills/monitor/SKILL.md`
- Modify: `plugins/monitor/.claude-plugin/plugin.json`

**Interfaces:**
- Consumes: `pending.py hook-post-tool-use` / `hook-user-prompt-submit` from Task 3 as the commands the installed hooks invoke.
- Produces: nothing (final task).

- [ ] **Step 1: Add the hook-install step to `init.md`**

In `plugins/monitor/commands/init.md`, after step 6 (`Ensure .gitignore contains monitor/scripts/__pycache__/.`) and before step 7 (the `CLAUDE.md`/`AGENTS.md` block), insert a new step (renumber step 7 onward by one):

```markdown
7. **Install the pending-state hooks.** Merge these two entries into the
   project's `.claude/settings.json` under a top-level `"hooks"` key
   (merge in — don't clobber any existing `hooks` entries for other tools):
   ```json
   {
     "hooks": {
       "PostToolUse": [
         {
           "matcher": "Bash",
           "hooks": [
             {"type": "command", "command": "python3",
              "args": ["${CLAUDE_PROJECT_DIR}/monitor/scripts/pending.py",
                        "hook-post-tool-use", "--project-root",
                        "${CLAUDE_PROJECT_DIR}"]}
           ]
         }
       ],
       "UserPromptSubmit": [
         {
           "matcher": "*",
           "hooks": [
             {"type": "command", "command": "python3",
              "args": ["${CLAUDE_PROJECT_DIR}/monitor/scripts/pending.py",
                        "hook-user-prompt-submit", "--project-root",
                        "${CLAUDE_PROJECT_DIR}"]}
           ]
         }
       ]
     }
   }
   ```
   These are silent unless something is actually pending — see "Pending-state
   enforcement" in `SKILL.md`.
```

- [ ] **Step 2: Add the same reconciliation step to `update.md`**

In `plugins/monitor/commands/update.md`, after the existing step 5 (refresh `monitor/usage.md`) and before step 6 (memory refresh), insert:

```markdown
6. **Ensure the pending-state hooks are installed.** If the project's
   `.claude/settings.json` doesn't yet have the `PostToolUse`/
   `UserPromptSubmit` entries pointing at `pending.py` (same JSON shown in
   `/monitor:init` step 7), add them now — additive merge, same as init.
   Already-initialized projects that predate this feature pick it up here.
```

(Renumber the existing steps 6-7 to 7-8.)

- [ ] **Step 3: Document the feature in `SKILL.md`**

In `plugins/monitor/skills/monitor/SKILL.md`, add a new section — find the "Companion skills" section (search for `## Companion skills`) and insert a new section directly before it:

```markdown
## Pending-state enforcement

Two Claude Code hooks (installed by `/monitor:init`/`/monitor:update` into
the project's `.claude/settings.json`) back a soft, real reminder instead of
pure discretion: a `PostToolUse` hook fires `pending.py hook-post-tool-use`
after every `git commit`/`merge`/`rebase`, recording it in
`monitor/.pending.json`. A `UserPromptSubmit` hook fires `pending.py
hook-user-prompt-submit` on your next turn — if anything is pending, its
`[Warn!]` text becomes injected context, and you must surface it to the
user and get a Y/N before continuing:

- **Y** → work through `monitor/.pending.json`'s `pending_logs` (one
  `/monitor:log` per entry) and `pending_report` (one `/monitor:report`
  covering `git log <since_sha>..HEAD`), then continue the user's original
  request.
- **N** → say so, leave `.pending.json` untouched (it stays pending and
  reminds again next turn), and do whatever the user asks instead.

`monitor/.pending.json` is committed like the rest of `monitor/` — it's
per-branch state, not local scratch. `logger.py` and `render_report.py`
(on `--lock-report`) clear the matching entries automatically on success;
nothing else should ever hand-edit this file.
```

- [ ] **Step 4: Bump the version and update the description**

In `plugins/monitor/.claude-plugin/plugin.json`, change:

```json
  "version": "1.10.1",
```

to:

```json
  "version": "1.11.0",
```

(Minor bump, not patch — this adds a new user-facing mechanism, not just a bugfix.)

- [ ] **Step 5: Verify the JSON is still valid**

```bash
python3 -c "import json; json.load(open('plugins/monitor/.claude-plugin/plugin.json'))" && echo OK
```

- [ ] **Step 6: Commit**

```bash
git add plugins/monitor/commands/init.md plugins/monitor/commands/update.md plugins/monitor/skills/monitor/SKILL.md plugins/monitor/.claude-plugin/plugin.json
git commit -m "feat: install pending-state hooks via init/update, document the feature"
```

---

## Self-Review Notes

- **Spec coverage:** `pending.py` data model + `track`/`check` (Task 1), pending-state clearing on log/report (Task 2), the real hook I/O contract — a refinement over the spec's vaguer "stdout becomes injected context," now precise after confirming the actual Claude Code hooks schema (Task 3), hook installation via init/update + documentation (Task 4). The spec's "Rebase handling" section is covered by `track()`'s sha-existence filter in Task 1. Every spec section maps to a task.
- **Placeholder scan:** no TBD/TODO — every step has literal file content or an exact command.
- **Type consistency:** `clear_log(root, sha)` and `clear_report(root)` signatures in Task 1 match exactly how Task 2 calls them. `check_text()` (returns a string) is what both `main()`'s plain `check` subcommand and `hook_user_prompt_submit()` call, keeping one source of truth for the warning text.
- **Deviation from spec, noted:** the spec's "Clearing pending state" section says `render_report.py` clears `pending_report` "after a successful `/monitor:report`" without pinning an exact call site. Task 2 pins it to the `--lock-report` branch specifically (not `render_all()`), because `render_all()` also runs during plain `/monitor:init`/`/monitor:update`, which would incorrectly clear a genuinely pending report the user hasn't answered Y/N on yet.
- **Scope:** deliberately does not attempt to use the hooks-doc's `"if"` matcher-filter field — confirmed unreliable/undocumented for this purpose, so `pending.py`'s own hook entrypoint self-filters on `tool_input.command` instead, which works regardless of `"if"`'s actual behavior.
