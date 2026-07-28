# Thought-Leak Scanner v2 + Mechanical Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the thought-leak scanner with level-gated context capture and report-only agentic verification (Track A), and land six independently-specified mechanical fixes from a prior verification round (Track B).

**Architecture:** Track A adds a `--level` flag to `scripts/check_thought_leaks.py` that scales what context each hit carries (nothing / sentence / full file / git history), and rewrites `.claude/skills/test-thought-leaks/SKILL.md` so the invoking agent must verdict every hit and, on any confirmed leak, produce a report in one of three formats — the skill never edits a file. Track B is six small, unrelated bugfixes across the existing engine and test suite, each already fully specified — no new architecture, just correctness fixes.

**Tech Stack:** Python 3 stdlib only (`re`, `subprocess`, `argparse`, `pathlib`) — no new dependencies in either track. Track A's `--level max` shells out to `git log`, matching the existing `subprocess` pattern already used in `pending.py`.

## Global Constraints

- Repo: `/Users/ojaswi/Projects/monitor-tools`, branch `feat/followup-fixes`. Working tree already has an uncommitted 13-file diff from a prior fix wave plus an already-applied `EXCLUDED` revert in `check_thought_leaks.py` — do not touch or redo that revert.
- Stdlib-only Python 3 — no `pip install` in any engine or scanner script (per `CLAUDE.md`).
- `scripts/check_thought_leaks.py` is a repo-root dev tool, never copied into `plugins/monitor/` (per its own `SKILL.md` Notes section).
- Never record development history, version changelogs, or reasoning leakage in any shipped/user-facing doc (`SKILL.md`, `commands/*.md`, `README.md`, generated `CLAUDE.md`/`AGENTS.md`) — this rule applies to the plan's own doc edits (Task 5's `SKILL.md` rewrite, Task 8's `record.md`-adjacent... N/A here, just be mindful in Track A's own doc file).
- The `test-thought-leaks` skill must never edit any file — verdict and report only (per spec `docs/superpowers/specs/2026-07-28-thought-leak-scanner-v2-design.md`).
- `plugins/monitor/skills/monitor/` changed again in Track B → bump `plugins/monitor/.claude-plugin/plugin.json`'s `version` (currently `1.14.1`) to `1.14.2` (final task).
- No pytest coverage for Track A (matches the spec's Testing section — this script sits outside `tests/`).
- Do not commit anything — leave the full diff staged/unstaged for review at the end.

---

## Track A: Scanner v2

### Task 1: `--level` flag + level-gated `find_hits()` in `check_thought_leaks.py`

**Files:**
- Modify: `scripts/check_thought_leaks.py` (full rewrite of `find_hits()` and `main()`, current file is 90 lines, read in full above)

**Interfaces:**
- Produces: `find_hits(level: str) -> list[dict]`, where each dict has keys `path` (str, POSIX-relative), `line_no` (int), `matched_text` (str), and conditionally `sentence` (str, present when `level != "minimum"`), `full_file_text` (str, present when `level in ("high", "max")`), `git_history` (str, present when `level == "max"`).
- Produces: module-level `LEVELS = ("minimum", "standard", "high", "max")` tuple for `main()`'s `argparse` choices and for Task 2's `SKILL.md` to reference by name.
- Produces: `_extract_sentence(text: str, line_no: int, matched_text: str) -> str` — helper used by `find_hits()`.
- Produces: `_strip_markdown(s: str) -> str` — helper used by `find_hits()`.
- Produces: `_git_history_for_line(root: Path, path: Path) -> str` — helper used by `find_hits()` at `max`.
- Consumes: nothing new from other tasks (Track A Task 1 is the foundation both other Track A tasks build on).

- [ ] **Step 1: Add the sentence-extraction and markdown-stripping helpers**

These are pure functions, easy to hand-test at the REPL before wiring them into `find_hits()`. Add above `find_hits()`:

```python
def _strip_markdown(s: str) -> str:
    """Strip common markdown syntax for a clean plain-text read: bold/italic
    markers, and [text](url) links reduced to their visible text."""
    s = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", s)
    s = re.sub(r"(\*\*|__)(.*?)\1", r"\2", s)
    s = re.sub(r"(\*|_)(.*?)\1", r"\2", s)
    s = re.sub(r"`([^`]+)`", r"\1", s)
    return s


def _extract_sentence(text: str, line_no: int, matched_text: str) -> str:
    """Return the sentence containing `matched_text` on 1-indexed `line_no`
    within `text`. Splits the line's paragraph (blank-line-delimited block)
    into sentences on '.', '!', '?' followed by whitespace, and returns the
    first sentence whose lowercase form contains the lowercase matched text.
    Falls back to the raw line if no paragraph or sentence boundary is
    found (e.g. a one-line heading with no terminal punctuation)."""
    lines = text.splitlines()
    start = line_no - 1
    para_start = start
    while para_start > 0 and lines[para_start - 1].strip():
        para_start -= 1
    para_end = start
    while para_end < len(lines) - 1 and lines[para_end + 1].strip():
        para_end += 1
    paragraph = " ".join(l.strip() for l in lines[para_start:para_end + 1])
    sentences = re.split(r"(?<=[.!?])\s+", paragraph)
    needle = matched_text.lower()
    for sentence in sentences:
        if needle in sentence.lower():
            return _strip_markdown(sentence).strip()
    return _strip_markdown(lines[start].strip())


def _git_history_for_line(root: Path, path: Path) -> str:
    """`git log -p --follow` for `path`, relative to `root`. Read-only,
    no network. Returns "" if git is unavailable or the file has no
    history (e.g. untracked)."""
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "log", "-p", "--follow", "--", str(path)],
            capture_output=True, text=True, timeout=10)
    except Exception:  # noqa: BLE001 — git missing/unusable, no history to show
        return ""
    return out.stdout if out.returncode == 0 else ""
```

Add `import subprocess` to the top-level imports (currently only `re`, `sys`, `pathlib.Path`).

- [ ] **Step 2: Rewrite `find_hits()` to accept and honor `level`**

Replace the existing `find_hits()`:

```python
LEVELS = ("minimum", "standard", "high", "max")


def find_hits(level: str = "standard") -> list[dict]:
    hits: list[dict] = []
    seen: set[Path] = set()
    for pattern in TARGET_GLOBS:
        for path in sorted(REPO_ROOT.glob(pattern)):
            if path in seen or not path.is_file():
                continue
            rel = path.relative_to(REPO_ROOT).as_posix()
            if rel in EXCLUDED:
                continue
            seen.add(path)
            text = path.read_text(encoding="utf-8", errors="replace")
            file_hits = []
            for i, line in enumerate(text.splitlines(), 1):
                for regex in PATTERNS:
                    m = regex.search(line)
                    if m:
                        file_hits.append((i, m.group(0)))
            if not file_hits:
                continue
            full_file_text = text if level in ("high", "max") else None
            git_history = _git_history_for_line(REPO_ROOT, path) if level == "max" else None
            for line_no, matched_text in file_hits:
                hit = {"path": rel, "line_no": line_no, "matched_text": matched_text}
                if level != "minimum":
                    hit["sentence"] = _extract_sentence(text, line_no, matched_text)
                if full_file_text is not None:
                    hit["full_file_text"] = full_file_text
                if git_history is not None:
                    hit["git_history"] = git_history
                hits.append(hit)
    return hits
```

- [ ] **Step 3: Rewrite `main()` to accept `--level` and print level-scaled output**

```python
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--level", default="standard", choices=LEVELS,
                    help="How much context to capture per hit: minimum "
                         "(matched line only), standard (+ containing "
                         "sentence, markdown-stripped), high (+ full file "
                         "text), max (+ git log -p history for the file). "
                         "Default: standard.")
    args = ap.parse_args()
    hits = find_hits(args.level)
    if not hits:
        print("clean: no development-history/reasoning-leakage phrases found")
        return 0
    print(f"{len(hits)} candidate(s) found — review each for a real leak vs. a false positive:\n")
    for hit in hits:
        print(f"{hit['path']}:{hit['line_no']}: {hit['matched_text']!r}")
        if "sentence" in hit:
            print(f"  sentence: {hit['sentence']}")
    return 1
```

Add `import argparse` to the top-level imports (not currently imported — `main()` previously took no flags).

Note: `full_file_text` / `git_history` are captured in the returned hit dicts (available to a caller importing `find_hits()` directly, e.g. a future skill automation) but intentionally not dumped to stdout in `main()`'s human-facing report — printing an entire file or full git log per hit line would make the CLI output unreadable. The `standard`-level sentence line is the CLI's ceiling; `high`/`max` context is for a caller that reads the hit dicts directly.

- [ ] **Step 4: Update the module docstring's `Usage`/`Exit code` lines**

The current docstring (lines 1-12) says `Usage:  python3 scripts/check_thought_leaks.py` with no flag. Update to:

```python
Usage:  python3 scripts/check_thought_leaks.py [--level minimum|standard|high|max]
Exit code: 1 if anything matched (for scripting), 0 if clean.
```

- [ ] **Step 5: Manual verification — run all four levels against the real repo**

Run each of these and confirm every one exits 0 (the repo's own docs are clean per the last `check_thought_leaks.py` run in this session):

```bash
cd /Users/ojaswi/Projects/monitor-tools
python3 scripts/check_thought_leaks.py --level minimum; echo "exit: $?"
python3 scripts/check_thought_leaks.py --level standard; echo "exit: $?"
python3 scripts/check_thought_leaks.py --level high; echo "exit: $?"
python3 scripts/check_thought_leaks.py --level max; echo "exit: $?"
```

Expected: all four print `clean: ...` and exit 0. If `max` errors, check the `git log -p --follow` subprocess call — it must run with cwd resolving correctly relative to `REPO_ROOT`.

- [ ] **Step 6: Manual verification — inject a fake leak and confirm sentence extraction**

```bash
cd /Users/ojaswi/Projects/monitor-tools
cp README.md /tmp/README.md.bak
printf '\n\nThis feature used to work differently before it was reworked. It now works as described above.\n' >> README.md
python3 scripts/check_thought_leaks.py --level standard
```

Expected output includes a line `README.md:<N>: 'used to'` followed by `  sentence: This feature used to work differently before it was reworked.` — confirming the sentence boundary stopped at the first `.` and did not bleed into the next sentence.

Then restore the file and confirm clean again:

```bash
cp /tmp/README.md.bak README.md && rm /tmp/README.md.bak
python3 scripts/check_thought_leaks.py --level standard
```

Expected: `clean: ...`, exit 0.

- [ ] **Step 7: Commit is deferred**

Per Global Constraints, do not commit. Leave the change in the working tree. (No `git add`/`git commit` step here — this deviates from the standard plan template's per-task commit because the plan-level instruction is "leave for review.")

---

### Task 2: Rewrite `.claude/skills/test-thought-leaks/SKILL.md` — level prompt, mandatory verdicts, report-only

**Files:**
- Modify: `.claude/skills/test-thought-leaks/SKILL.md` (full rewrite, current file is 34 lines, read in full above)

**Interfaces:**
- Consumes: `--level {minimum,standard,high,max}` flag and per-hit `path:line_no: matched_text` / `sentence:` output format from Task 1's `main()`.
- Produces: nothing consumed by other tasks — this is a leaf doc.

- [ ] **Step 1: Write the new SKILL.md content**

```markdown
---
name: test-thought-leaks
description: Scans monitor's shipped documentation for development-history, version-changelog, or reasoning-leakage language, per this repo's CLAUDE.md rule. Use when asked to check for thought leaks, dev-history leakage, or before finishing a branch that touched SKILL.md/README.md/commands/*.md.
---

# test-thought-leaks

Runs `scripts/check_thought_leaks.py`, which greps a fixed list of shipped
doc files for phrases like "used to", "previously", "removed because",
"version N", "deprecated" — candidates for the kind of narration
`CLAUDE.md` explicitly bans from user-facing documentation.

This skill never edits any file. It judges each candidate and, if any are
real leaks, produces a report — the fix itself is a separate, deliberate
step the user or a follow-up task takes.

## Flow

1. Ask the user which level to run, presenting all four:
   - **minimum** — matched line only. Fastest, lowest token cost.
   - **standard** (Recommended) — matched line plus the full sentence it
     appears in, markdown-stripped for a clean read. Enough context for
     most judgment calls.
   - **high** — standard, plus the agent reads the full source file
     around each hit for whole-document context.
   - **max** — high, plus the agent checks `git log -p` history for the
     file to see whether the phrase traces to a real historical rewrite.
2. Run: `python3 scripts/check_thought_leaks.py --level <chosen>`
3. Exit 0 means clean — relay that and stop.
4. Exit 1 means candidates were found. For **every** hit printed, output:
   the sentence (or line, at `minimum`) → a verdict, `LEAK` or `OK` → one
   short reason. No hit is skipped or left unverdicted. At `high`/`max`,
   read the file (and git history, at `max`) yourself before verdicting —
   the script only prints the sentence at the CLI level.
5. If every hit verdicted `OK`, relay that (false positives only, nothing
   to report) and stop.
6. If any hit verdicted `LEAK`, ask the user which report format: **Chat**,
   **HTML**, or **Markdown**.
7. Generate the report — `LEAK` hits only, one entry per hit, four fields:
   **File**, **Line**, **Issue** (your one-line finding: what phrase, why
   flagged), **Description** (brief — why it reads as a leak),
   **Recommendation** (one line, concrete, human-executable — a fix a
   person could act on directly). Minimal and direct, no other sections,
   no fluff.
   - **Chat**: print the four-field list directly in the conversation.
   - **Markdown**: write the same list to a file, one heading/row per
     issue.
   - **HTML**: same content; consult the `ui-ux-pro-max` skill for
     minimal-report styling guidance first (a clean, scannable list, not
     a dashboard). Self-contained HTML, no external assets, no JS needed
     for a static list.

No template is hardcoded anywhere in this skill or the script — the
report is composed fresh from the verdicted hits each run.

## Notes

- This skill is not part of the `monitor` plugin; it is never copied into
  `plugins/monitor/`.
- The script's target list lives in code
  (`scripts/check_thought_leaks.py`'s `TARGET_GLOBS`). It globs every
  `.claude/skills/*/SKILL.md`, so a new skill is covered automatically; a
  shipped doc outside those globs needs an entry added there.
```

- [ ] **Step 2: Verify the doc itself is clean under its own scanner**

```bash
cd /Users/ojaswi/Projects/monitor-tools
python3 scripts/check_thought_leaks.py --level standard
```

Expected: `clean: ...`, exit 0. (`.claude/skills/test-thought-leaks/SKILL.md` is in `EXCLUDED` already, so this file self-matching wouldn't fail the run regardless — but the new prose above avoids the banned phrases entirely on its own merits, so this is a sanity check, not a dependency on the exclusion.)

- [ ] **Step 3: Commit is deferred**

Per Global Constraints, do not commit.

---

## Track B: Mechanical Fixes

### Task 3: Drop the redundant `aria-label` on the Dashboard search input

**Files:**
- Modify: `plugins/monitor/skills/monitor/scripts/render_report.py:392-396`

**Interfaces:**
- Consumes: nothing from Track A or other Track B tasks.
- Produces: nothing consumed elsewhere.

- [ ] **Step 1: Remove the `aria-label` attribute, keep the `<label>`**

Current (lines 392-396):

```python
  <div class="dsearch">
    <label class="sr-only" for="monitor-search">Search titles across logs, reports, and tasks</label>
    <input type="text" id="monitor-search" placeholder="Search titles across logs, reports, tasks..."
           autocomplete="off" aria-label="Search titles across logs, reports, and tasks"
           aria-describedby="monitor-search-status">
    <ul id="monitor-search-results"></ul>
    <p class="status" id="monitor-search-status" role="status" aria-live="polite"></p>
```

Change to:

```python
  <div class="dsearch">
    <label class="sr-only" for="monitor-search">Search titles across logs, reports, and tasks</label>
    <input type="text" id="monitor-search" placeholder="Search titles across logs, reports, tasks..."
           autocomplete="off" aria-describedby="monitor-search-status">
    <ul id="monitor-search-results"></ul>
    <p class="status" id="monitor-search-status" role="status" aria-live="polite"></p>
```

- [ ] **Step 2: Confirm the markup change is exactly as intended**

```bash
cd /Users/ojaswi/Projects/monitor-tools
grep -n 'id="monitor-search"' plugins/monitor/skills/monitor/scripts/render_report.py
```

Expected: one `<label for="monitor-search">` line and one `<input id="monitor-search" ...>` line, with no `aria-label` on the input. This is a static text check — full render verification (does `render_report.py` still produce a valid Dashboard) happens in Task 9's full test-suite run, which exercises `render_report.py` end to end via the existing integration tests.

---

### Task 4: Free `item["text"]` after use in `search_reports()`

**Files:**
- Modify: `plugins/monitor/skills/monitor/scripts/search.py:87-111`

**Interfaces:**
- Consumes: `render_report.scan_reports(root, with_text=True)` (unchanged signature from the prior fix wave).
- Produces: nothing consumed elsewhere.

- [ ] **Step 1: Add `del item["text"]` once the match check is done**

Current (lines 94-101):

```python
    for item in render_report.scan_reports(root, with_text=True):
        raw = item["text"]
        # Drop <style>/<script> *contents* before flattening to text —
        # _plain() only strips tags, so an embedded stylesheet would
        # otherwise put every CSS token in the search haystack.
        raw = render_report.STYLE_RE.sub("", raw)
        raw = render_report.SCRIPT_RE.sub("", raw)
        text = render_report._plain(raw)
```

Change to:

```python
    for item in render_report.scan_reports(root, with_text=True):
        raw = item.pop("text")
        # Drop <style>/<script> *contents* before flattening to text —
        # _plain() only strips tags, so an embedded stylesheet would
        # otherwise put every CSS token in the search haystack.
        raw = render_report.STYLE_RE.sub("", raw)
        raw = render_report.SCRIPT_RE.sub("", raw)
        text = render_report._plain(raw)
```

`item.pop("text")` both reads and frees the key in one call — after this line `item` (and the `matches.append({...})` a few lines down, which only copies `file`/`title`/`date`/`excerpt` anyway) no longer holds the report body, so it can be garbage collected once the loop moves to the next report instead of accumulating across the whole scan.

- [ ] **Step 2: Run the existing search test to confirm no regression**

```bash
cd /Users/ojaswi/Projects/monitor-tools
PYTHONPATH=plugins/monitor/skills/monitor/scripts python3 -m pytest tests/unit/test_search.py -v
```

Expected: all existing tests pass (the report-search tests already exercise `search_reports()`'s matching logic; `item.pop` vs `item["text"]` doesn't change any returned value, only when the string is freed).

---

### Task 5: Warn on stderr when a log-only filter is used with a non-`logs` scope

**Files:**
- Modify: `plugins/monitor/skills/monitor/scripts/search.py:166-216` (`main()`)
- Test: `tests/unit/test_search.py` (add one new test)

**Interfaces:**
- Consumes: `args.scope`, `args.branch`, `args.status`, `args.level` from the existing `argparse` setup (lines 166-186, unchanged).
- Produces: nothing new consumed elsewhere — this is stderr output only, `search()`'s return value and behavior are unchanged.

- [ ] **Step 1: Write the failing test**

Add to `tests/unit/test_search.py` (check the existing file's imports/fixtures first — it already uses the `project_root` fixture and calls `search.main()` or `search.search()`; match that pattern). Add:

```python
def test_main_warns_when_log_filter_used_with_non_logs_scope(project_root, capsys):
    import search
    argv = ["--project-root", str(project_root), "--query", "x",
            "--scope", "reports", "--branch", "main"]
    search.main.__globals__["sys"].argv = ["search.py"] + argv
    search.main()
    captured = capsys.readouterr()
    assert "branch" in captured.err.lower()
    assert "reports" in captured.err.lower()


def test_main_no_warning_for_logs_scope_with_filters(project_root, capsys):
    import search
    argv = ["--project-root", str(project_root), "--query", "x",
            "--scope", "logs", "--branch", "main"]
    search.main.__globals__["sys"].argv = ["search.py"] + argv
    search.main()
    captured = capsys.readouterr()
    assert captured.err == ""
```

Note: check how other tests in `tests/unit/test_search.py` already invoke `main()` (likely via `monkeypatch.setattr(sys, "argv", [...])` with pytest's `monkeypatch` fixture rather than reaching into `__globals__`) — if the file has an established pattern for calling `main()` with args, use that pattern instead of the `__globals__` hack above; the hack is a fallback only if no such pattern exists. Read the existing test file before writing this step for real.

- [ ] **Step 2: Run it to verify it fails**

```bash
cd /Users/ojaswi/Projects/monitor-tools
PYTHONPATH=plugins/monitor/skills/monitor/scripts python3 -m pytest tests/unit/test_search.py -k "warn" -v
```

Expected: FAIL (no warning is currently printed).

- [ ] **Step 3: Add the warning in `main()`**

Current `main()` (lines 186-190):

```python
    args = ap.parse_args()
    root = mlib.resolve_root(args)
    mlib.require_init(root)
    matches = search(root, args.query, scope=args.scope, branch=args.branch,
                     status=args.status, level=args.level, limit=args.limit)
```

Change to:

```python
    args = ap.parse_args()
    root = mlib.resolve_root(args)
    mlib.require_init(root)
    if args.scope != "logs" and (args.branch or args.status or args.level):
        print(f"warning: --branch/--status/--level only filter log matches; "
              f"they have no effect under --scope {args.scope}", file=sys.stderr)
    matches = search(root, args.query, scope=args.scope, branch=args.branch,
                     status=args.status, level=args.level, limit=args.limit)
```

Note: `--scope all` also triggers this warning under the same condition, since `all` includes reports/tasks alongside logs and the filters still only apply to the logs portion — the warning text ("only filter log matches") already covers that case correctly without change.

- [ ] **Step 4: Run the test again to verify it passes**

```bash
cd /Users/ojaswi/Projects/monitor-tools
PYTHONPATH=plugins/monitor/skills/monitor/scripts python3 -m pytest tests/unit/test_search.py -v
```

Expected: all tests pass, including the two new ones.

---

### Task 6: Add `"profile"` to the `conftest.py` module-purge tuple

**Files:**
- Modify: `tests/conftest.py:48-49`

**Interfaces:**
- Consumes: nothing.
- Produces: nothing consumed elsewhere — this only affects test-teardown hygiene.

- [ ] **Step 1: Add `"profile"` to the tuple**

Current (lines 48-49):

```python
    for mod in ("tasks", "pending", "clean", "logger", "search",
               "render_tasks", "render_logs", "render_report", "monitor_lib"):
```

Change to:

```python
    for mod in ("tasks", "pending", "clean", "logger", "search", "profile",
               "render_tasks", "render_logs", "render_report", "monitor_lib"):
```

- [ ] **Step 2: Run the full unit suite to confirm no cross-test bleed was masking a bug**

```bash
cd /Users/ojaswi/Projects/monitor-tools
PYTHONPATH=plugins/monitor/skills/monitor/scripts python3 -m pytest tests/unit/ -v
```

Expected: all tests still pass. (This is a hygiene fix, not a behavior change — `profile.py` takes its root as an argument and caches no module-level state, per the existing comment directly above this tuple, so purging it now shouldn't change any test outcome; the run just confirms that holds.)

---

### Task 7: Shorten the duplicated mixed-case task message in `pending.py`

**Files:**
- Modify: `plugins/monitor/skills/monitor/scripts/pending.py:230-234`
- Test: `tests/unit/test_pending.py` (update the existing mixed-case assertion if it checks the old wording)

**Interfaces:**
- Consumes: `tasks` (list of dicts, from `open_tasks()`, unchanged) inside `check_text()`.
- Produces: `check_text()`'s mixed-case return string — the shape (list joined with `"\n"`) is unchanged, only the task-count sentence's wording shortens.

- [ ] **Step 1: Check the existing test for the mixed-case message's exact wording**

```bash
cd /Users/ojaswi/Projects/monitor-tools
grep -n "Separately\|not part of the" tests/unit/test_pending.py
```

If a test asserts the full old sentence ("...answering Y records the log/report and leaves these open."), note its location — Step 4 updates it.

- [ ] **Step 2: Shorten the message**

Current (lines 230-234):

```python
    if tasks:
        noun = "task" if len(tasks) == 1 else "tasks"
        lines.append(f"\nSeparately, {len(tasks)} open {noun} — not part of the "
                     f"Y/N above; answering Y records the log/report and leaves "
                     f"these open.")
        lines.append(_task_block(tasks))
```

Change to:

```python
    if tasks:
        noun = "task" if len(tasks) == 1 else "tasks"
        lines.append(f"\nSeparately, {len(tasks)} open {noun} — not part of "
                     f"the Y/N above.")
        lines.append(_task_block(tasks))
```

`_task_block()` (lines 200-205, unchanged by this task) already says "close with /monitor:task-close when done, or leave open and continue — this is informational, not blocking" immediately after — the removed clause was restating that.

- [ ] **Step 3: Run the pending test suite**

```bash
cd /Users/ojaswi/Projects/monitor-tools
PYTHONPATH=plugins/monitor/skills/monitor/scripts python3 -m pytest tests/unit/test_pending.py -v
```

- [ ] **Step 4: Fix any test asserting the old exact wording**

If Step 1 found a test asserting the removed clause, update it to check for the new shorter sentence (`"not part of the Y/N above."` with no trailing "answering Y..." text) instead of deleting the assertion — the test should still confirm the task-count sentence is present and still confirm it stays separate from the Y/N header, just with updated wording. Re-run Step 3's command to confirm green.

---

### Task 8: Reword the stale "instead of twice" comment in `search.py`

**Files:**
- Modify: `plugins/monitor/skills/monitor/scripts/search.py:92-93`

**Interfaces:**
- Consumes: nothing (comment-only change).
- Produces: nothing consumed elsewhere.

- [ ] **Step 1: Reword the comment**

Current (lines 92-93, immediately above the loop Task 4 also touches — apply this after Task 4's edit, the line numbers shift by one field name (`item["text"]` → `item.pop("text")`) but this comment's own line numbers are unaffected since it sits above the `for` line):

```python
    # with_text=True hands back the HTML scan_reports() already read, so each
    # report file is opened exactly once per search instead of twice.
```

Change to:

```python
    # with_text=True hands back the HTML scan_reports() already read, so
    # each report file is opened exactly once per search.
```

- [ ] **Step 2: Confirm no test depends on comment text**

Comments aren't asserted on in tests; no verification command needed beyond re-running the file's own tests once (already covered by Task 4/5's test runs on this same file).

---

## Final Task 9: Full verification, version bump, no commit

**Files:**
- Modify: `plugins/monitor/.claude-plugin/plugin.json:3` (version bump only)

**Interfaces:**
- Consumes: the complete state of the repo after Tasks 1-8.
- Produces: nothing — this is the plan's terminal verification gate.

- [ ] **Step 1: Run the full pytest suite**

```bash
cd /Users/ojaswi/Projects/monitor-tools
PYTHONPATH=plugins/monitor/skills/monitor/scripts python3 -m pytest tests/ -v
```

Expected: every test passes (Track A adds no pytest coverage per its spec; Track B's changes to `conftest.py`, `search.py`, `pending.py` are covered by Tasks 4-7's own test runs, but re-run the whole suite here since `conftest.py` changed and every test uses that fixture).

- [ ] **Step 2: Run the thought-leak scanner against the repo's own docs**

```bash
cd /Users/ojaswi/Projects/monitor-tools
python3 scripts/check_thought_leaks.py --level standard
```

Expected: `clean: ...`, exit 0 — this both confirms Track A's rewritten script still works end-to-end and confirms none of Track A/B's own doc/comment edits (SKILL.md rewrite, search.py comment) introduced a flagged phrase.

- [ ] **Step 3: Bump `plugin.json`'s version**

`plugins/monitor/skills/monitor/` files changed again in Track B (Task 3's `render_report.py`, Task 4/5/8's `search.py`, Task 7's `pending.py`), so per `CLAUDE.md`'s rule, bump the version. Current value is `"1.14.1"` (line 3 of `plugins/monitor/.claude-plugin/plugin.json`) — change to `"1.14.2"`.

- [ ] **Step 4: Final status check — confirm nothing was committed**

```bash
cd /Users/ojaswi/Projects/monitor-tools
git status --short
git diff --stat
```

Expected: a working-tree diff spanning both tracks' files plus `plugin.json`, nothing staged/committed. Leave it exactly as-is for review — no `git add`, no `git commit`.
