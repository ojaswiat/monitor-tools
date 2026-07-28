# test-thought-leaks v2: context-aware, agent-verified, report-only

## Problem

`scripts/check_thought_leaks.py` currently greps a fixed list of shipped
doc files line-by-line against 8 red-flag regexes and prints
`file:line: matched text`. Two gaps:

1. A bare matched line often isn't enough to judge whether it's a real
   dev-history/reasoning leak or a coincidental, legitimate use of the
   same word — the invoking agent has to re-open the file itself for
   context on every hit.
2. `.claude/skills/test-thought-leaks/SKILL.md` tells the agent to "read
   each one yourself" and "fix the wording," which is informal (no
   required output per hit) and, more importantly, lets the skill edit
   shipped docs on its own judgment with no human in the loop.

## Scope

This spec covers only the scanner redesign (script + skill). A separate,
already-fully-specified batch of 6 mechanical fixes (issues 3-8 from a
prior verification round, touching `render_report.py`, `search.py`,
`conftest.py`, `pending.py`) rides alongside as its own implementation
track — no design needed there, straight to a fix wave.

## Design

### 1. Level-gated context capture (`check_thought_leaks.py`)

New `--level {minimum,standard,high,max}` flag, default `standard`.
`find_hits()` returns one record per hit with fields that scale by level:

| Level | Extra fields the script adds |
|---|---|
| `minimum` | none — `path, line_no, matched_text` (today's behavior, unchanged) |
| `standard` | `+ sentence` — split the hit's paragraph on `. ! ?` boundaries, take the sentence containing the match, strip markdown syntax (`**`, `_`, `[text](url)` -> `text`) for a clean read |
| `high` | `+ full_file_text` — the complete text of the file containing the hit |
| `max` | `+ git_history` — output of `git log -p --follow -- <file>`, filtered to hunks that touch the matched line's neighborhood, via subprocess (read-only git call, no network) |

`main()`'s printed report scales with the level: `minimum` prints today's
one-liner; `standard` and above also print the extracted sentence, so the
agent has enough to judge the common case without opening the file.

Sentence splitting and markdown stripping are regex-based (stdlib `re`
only, no new dependencies — matches this repo's stdlib-only rule).

### 2. Agentic verification, report-only (`.claude/skills/test-thought-leaks/SKILL.md`)

Flow:

1. Ask the user to pick a level. Present all four with a one-line
   tradeoff each; mark `standard` "(Recommended)".
2. Run `python3 scripts/check_thought_leaks.py --level <chosen>`.
3. Exit 0 -> relay "clean," stop.
4. Exit 1 -> for **every** hit, the agent outputs: the sentence (or
   line, at `minimum`) -> a verdict, `LEAK` or `OK` -> one-line reason.
   Every hit gets a verdict; none are silently skipped.
5. **The skill never edits any file.** It judges and reports only — no
   auto-fix, no line removal, no wording changes. This is a hard rule,
   not a default that can be overridden mid-flow.
6. If any hit was verdicted `LEAK`, ask the user which report format:
   **Chat**, **HTML**, or **Markdown**.
7. Generate the report, `LEAK` hits only, one entry per hit, four fields
   each:
   - **File** — path
   - **Line** — line number
   - **Issue** — the agent's one-line finding (what phrase, why flagged)
   - **Description** — brief summary of why it reads as a leak
   - **Recommendation** — one-line, concrete, human-executable fix (a
     sentence a person could paste in, not a vague pointer)

   No other sections. Minimal, direct, no fluff. No hardcoded template
   lives in the skill file — the skill gives these instructions and the
   agent composes the report fresh each run:
   - **Chat**: print the four-field list directly in the conversation.
   - **Markdown**: write the same four-field list to a file (agent picks
     a sensible path, e.g. under the scratch/output location the session
     is already using), one heading or row per issue.
   - **HTML**: same content; before writing, consult the `ui-ux-pro-max`
     skill for minimal-report styling guidance (clean, scannable list —
     not a dashboard). Self-contained HTML, no external assets, no JS
     needed for a static list.

If exit 0 at any level, or exit 1 but every hit verdicts `OK`, no report
step runs — nothing to report.

### 3. What doesn't change

- The script still never calls an LLM/external API (stdlib-only,
  `git log` is the only subprocess call, only at `--level max`).
- Exit code contract unchanged: 1 means "candidates found, needs
  judgment," never an automatic hard failure.
- `minimum` level is byte-for-byte today's behavior — a fast baseline
  path stays available.
- `TARGET_GLOBS`/`EXCLUDED`/`PATTERNS` — untouched by this spec (the
  `EXCLUDED` fix for `update.md` was already applied separately).

## Testing

No pytest coverage — this script sits outside `tests/`, consistent with
its current untested status. Manual verification instead:
1. Run all four levels against the current repo; confirm each exits 0.
2. Temporarily inject a fake leak phrase (e.g. "this used to work
   differently") into a scratch copy of a target doc; confirm `standard`
   extracts the correct containing sentence and the skill flow verdicts
   it `LEAK` with a report generated in all three formats.
3. Confirm `minimum` output is unchanged from the pre-spec script.

## Non-goals

- No automatic fixing of flagged docs by the skill, ever.
- No new pip dependency — sentence splitting and markdown stripping stay
  regex-based.
- No change to which files are scanned (`TARGET_GLOBS`) or which are
  exempt (`EXCLUDED`) as part of this spec.
