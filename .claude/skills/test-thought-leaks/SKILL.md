---
name: test-thought-leaks
description: Scans monitor's shipped documentation for development-history, version-changelog, or reasoning-leakage language, per this repo's CLAUDE.md rule. Use when asked to check for thought leaks, dev-history leakage, or before finishing a branch that touched SKILL.md/README.md/commands/*.md.
---

# test-thought-leaks

Runs `scripts/check_thought_leaks.py`, which greps a fixed list of shipped
doc files for phrases like "used to", "previously", "removed because",
"version N", "deprecated" — candidates for the kind of narration
`CLAUDE.md` explicitly bans from user-facing documentation.

## Flow

1. Run: `python3 scripts/check_thought_leaks.py`
2. Exit 0 means clean — relay that and stop.
3. Exit 1 means candidates were found — **read each one yourself**, don't
   treat a hit as an automatic failure. The script flags phrases, not
   confirmed leaks: "previously" inside a legitimate, unrelated sentence
   is a false positive. For each real leak, fix the wording to state
   current behavior only, then re-run the script to confirm it's now
   clean. For each false positive, note it and move on — nothing to fix.
4. Relay a final summary: how many hits were real leaks (fixed), how many
   were false positives (left as-is), and confirm the script now exits 0.

## Notes

- This skill is not part of the `monitor` plugin; it is never copied into
  `plugins/monitor/`.
- The script's target list lives in code
  (`scripts/check_thought_leaks.py`'s `TARGET_GLOBS`). It globs every
  `.claude/skills/*/SKILL.md`, so a new skill is covered automatically; a
  shipped doc outside those globs needs an entry added there.
