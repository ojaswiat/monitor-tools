---
name: test-thought-leaks
description: Scans monitor's shipped documentation for development-history, version-changelog, or reasoning-leakage language, per this repo's CLAUDE.md rule. Use when asked to check for thought leaks, dev-history leakage, or before finishing a branch that touched SKILL.md/README.md/commands/*.md.
---

# test-thought-leaks

Runs `scripts/check_thought_leaks.py`, which greps a fixed list of shipped
doc files for phrases like "used to", "previously", "removed because",
"version N", "deprecated" — candidates for the kind of narration
`CLAUDE.md` explicitly bans from user-facing documentation.

This skill never edits the files it scans — no auto-fix, no line removal,
no wording change to any flagged doc. Its only write is the report itself,
when the user picks Markdown or HTML format. It judges each candidate and,
if any are real leaks, produces a report — the fix itself is a separate,
deliberate step the user or a follow-up task takes.

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
