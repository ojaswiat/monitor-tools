# test-e2e monitor:search Coverage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a step to `.claude/skills/test-e2e/SKILL.md`'s subagent template that exercises `/monitor:search`, the one shipped monitor command the dogfood drill never touches.

**Architecture:** Single Markdown skill-file edit — insert one new template step (search test) between the existing pending-hook step and the report step, renumber the report step, and extend the report/verification/synthesis steps' evidence lists with the search result.

**Tech Stack:** Markdown (Claude Code skill spec format). No code, no dependencies.

## Global Constraints

- This skill stays under `.claude/skills/test-e2e/` — never copied into `plugins/monitor/`.
- No test suite exists in this repo — every "test" step below is a manual read-through of the edited file for correctness.
- The subagent template's steps are currently numbered 0-8 (0 = worktree self-check, 1-5 = clone/install/companions/act-as-dev/5-rounds, 6 = tasks, 7 = pending-hook, 8 = report). This plan inserts a new step 8 (search) and renumbers the report step to 9.
- All work happens on branch `improve/test-e2e-search` (already checked out, forked from `dev`).

---

### Task 1: Add the search-test step to SKILL.md

**Files:**
- Modify: `.claude/skills/test-e2e/SKILL.md`

**Interfaces:**
- N/A — documentation file, no code interfaces.

- [ ] **Step 1: Insert the new step 8 (search test) between the existing step 7 (pending-hook) and step 8 (report)**

In the subagent prompt template's fenced code block, immediately after the existing step 7 block (which ends with "...since the pending entry is matched by the commit sha that was HEAD at log time.") and before the existing step 8 ("Report back in plain language..."), insert:

```markdown
   8. Somewhere in those same 5 rounds, exercise the project's log-search
      command: pick a word that actually appears in one of your own log
      entries (from a `--summary` or `--details` field you wrote earlier
      in this run — not a guess), then search for it via
      `monitor/scripts/search.py --project-root . --query "<that word>"`.
      Verify the output is non-empty and contains a real matching entry
      (not an error, not an empty "no matches" result) — if it comes back
      empty, you either picked a word that isn't actually in the log or
      something is broken; try a different real word from your own log
      before concluding it's broken. Paste the exact query and one
      matched result block verbatim into your final report.
```

- [ ] **Step 2: Renumber the existing step 8 (report) to step 9, and add the search-test evidence requirement to it**

Replace the existing step 8 block:
```
   8. Report back in plain language: what you changed, whether/how you
      used monitor (which commands, how many times), and anything that
      looked broken, confusing, inconsistent, or undocumented — including
      anything about the companion-install step if companion_level wasn't
      "none". Your worktree will likely be gone by the time this is read,
      so paste the real evidence inline rather than describing it: the
      final log-entry count and report count, the number of distinct task_ids
      in `monitor/tasks/tasks.mtr` (that file is append-only with one block per
      lifecycle event, so count distinct task_ids, not blocks or lines), one full
      task's self-reported metrics pasted verbatim, one full `--details`
      block copied verbatim from `operations.mtr` (not paraphrased) so it can be
      checked for real content vs. placeholder text, and the pending-hook test
      outcome from step 7 — pass or fail, with the warning message text pasted
      verbatim.
```
with:
```
   9. Report back in plain language: what you changed, whether/how you
      used monitor (which commands, how many times), and anything that
      looked broken, confusing, inconsistent, or undocumented — including
      anything about the companion-install step if companion_level wasn't
      "none". Your worktree will likely be gone by the time this is read,
      so paste the real evidence inline rather than describing it: the
      final log-entry count and report count, the number of distinct task_ids
      in `monitor/tasks/tasks.mtr` (that file is append-only with one block per
      lifecycle event, so count distinct task_ids, not blocks or lines), one full
      task's self-reported metrics pasted verbatim, one full `--details`
      block copied verbatim from `operations.mtr` (not paraphrased) so it can be
      checked for real content vs. placeholder text, the pending-hook test
      outcome from step 7 — pass or fail, with the warning message text pasted
      verbatim — and the search-test outcome from step 8: the exact query used
      and one matched result block pasted verbatim.
```

- [ ] **Step 3: Update flow step 4 (orchestrator verification) to mention the search test**

In skill flow step 4, the sentence currently reading:
```markdown
   as the expected case, not an error: fall back to checking the verbatim
   log-entry count, report count, distinct-task_id count, one task's metrics,
   and the pending-hook pass/fail each subagent was told to paste into its own
   report (template step 8) for internal consistency and real content, same
```
becomes:
```markdown
   as the expected case, not an error: fall back to checking the verbatim
   log-entry count, report count, distinct-task_id count, one task's metrics,
   the pending-hook pass/fail, and the search-test query/result each subagent
   was told to paste into its own report (template step 9) for internal
   consistency and real content, same
```
(Only the "template step 8" → "template step 9" reference and the inserted "the search-test query/result" clause change; the rest of the paragraph is untouched.)

- [ ] **Step 4: Update flow step 5 (report synthesis) to add the search-test column**

In skill flow step 5, the sentence currently reading:
```markdown
   commits/changes made, log entry count, report count, task count (distinct
   task_ids, matching how the subagents were told to count), and
   hook-test result (pass/fail, with the one-line reason on fail) — plus a
```
becomes:
```markdown
   commits/changes made, log entry count, report count, task count (distinct
   task_ids, matching how the subagents were told to count), hook-test result
   (pass/fail, with the one-line reason on fail), and search-test result
   (pass/fail, with the query used) — plus a
```

- [ ] **Step 5: Re-read the whole file for internal consistency (this task's only "test")**

Open `.claude/skills/test-e2e/SKILL.md` and confirm, reading top to bottom:
- The subagent template's steps are numbered 0-9 with no gaps or duplicates, step 9 is the final (report) step.
- Every remaining "step 8" reference in the orchestrator's own prose (flow steps 4-5, both distinct from the template's own numbering) now correctly points at "template step 9" for the report and "template step 8" for the search test — no leftover ambiguous or wrong reference.
- No other part of the file (Notes section, etc.) references the old step 8 in a way that's now wrong.

If any inconsistency is found, fix it directly in the file before moving on.

- [ ] **Step 6: Commit**

```bash
cd /Users/ojaswi/Projects/monitor-tools
git add .claude/skills/test-e2e/SKILL.md
git commit -m "feat(test-e2e): cover /monitor:search in the dogfood drill"
```

---

## Self-Review Notes

**Spec coverage:** the spec's one change (new search-test step + evidence-list additions in the report/verification/synthesis steps) maps entirely onto this single task.

**Placeholder scan:** every step gives exact replacement text, not a description.

**Numbering consistency:** the plan spells out the full before/after text for every renumbered reference (step 8→9 for the report, new step 8 for search) so there's no ambiguity between the two same-numbered-but-different things (old step 8 = report, new step 8 = search) — Step 2 above makes the renumbering explicit rather than implicit.
