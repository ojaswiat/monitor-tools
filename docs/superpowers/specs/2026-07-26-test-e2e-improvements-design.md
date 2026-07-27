# test-e2e skill improvements — design spec

## Summary

Update `.claude/skills/test-e2e/SKILL.md` to reflect two features that
landed in `monitor` since the skill was last touched — lifecycle-tracked
tasks and the pending-state hook gate — and to fix a stale-worktree bug
observed live this session (a dispatched subagent's worktree branched
before a feature had merged, silently testing an old engine until the
subagent noticed and self-corrected).

## Why

The skill's subagent template only exercises logs and reports. It has no
concept of the tasks feature or the pending-state hook gate, so a drill run
today would report "everything works" while never touching two of
monitor's three tracked entities and its only hook-backed enforcement
mechanism. Separately, this session's own drills hit worktrees cut from a
stale base ref — subagents caught it themselves each time, but the skill
never told them to check, so a future run without that lucky self-catch
would silently test a stale engine.

## Changes

### 1. Stale-worktree fix

Before dispatching (skill step 2), the orchestrator captures the current
plugin version:
```bash
grep '"version"' plugins/monitor/.claude-plugin/plugin.json
```
and passes it into each subagent's prompt as `{expected_version}`.

New Step 0 in the subagent template, before the existing clone step:
after `install-monitor.sh` copies the engine into the test project, check
`{project_dir}/monitor/scripts/../../../.claude-plugin/plugin.json`'s (i.e.
this repo's own, not the copied one — the copied engine has no
`.claude-plugin/`) version — simplest correct check: compare the repo
root's `plugins/monitor/.claude-plugin/plugin.json` version at the moment
the subagent starts against `{expected_version}` passed in. If they differ,
the branch moved since dispatch; run `git merge <base-branch>` (the branch
this drill is running on) inside the worktree before proceeding with
`install-monitor.sh`. If they match, proceed normally. Report which case
happened.

### 2. Tasks-feature coverage

New step in the subagent template, after the existing "5 rounds of small
changes" step: use the project's task-tracking commands (discovered via
`CLAUDE.md`/`AGENTS.md` the same way every other command is — never named
directly in this prompt) for at least one unit of work spanning part of the
5 rounds: start a task, update it at least once, close it with a terminal
status. Report back: the task count in `monitor/tasks/tasks.mtr`, and one
full task's metrics (whatever it self-reported) pasted verbatim.

### 3. Pending-hook coverage (standard, every run)

New required step in the subagent template: after making at least one real
commit without logging it first, simulate what the two installed hooks
would do — subagents cannot trigger Claude Code's real `PostToolUse`/
`UserPromptSubmit` hook dispatch (no live interactive session), so this is
done by piping the same JSON payload a real hook call receives directly
into `pending.py hook-post-tool-use` / `pending.py hook-user-prompt-submit`.
Verify: the unlogged commit appears in `monitor/.pending.json`, the
user-prompt-submit simulation produces a sensible warning message, and
running the project's actual log command afterward clears the matching
pending entry. Report pass/fail and paste the warning message text
verbatim.

### 4. Report synthesis update

The combined HTML report (skill step 5, `ui-ux-pro-max`-styled,
`temp/test-e2e-runs/<date>.html`) gains two new columns per project,
alongside the existing log-entry-count and report-count: **task count**
and **hook-test result** (pass/fail, with the one-line reason on fail).

## Non-goals

- No change to how repos are found (`WebSearch`, no hardcoded list) or to
  the 3-language/3-companion-level matrix (Python/none, Node/some,
  Go-or-docs/all) — those already work and aren't in scope.
- No change to the containment rules (no `find`/`ls`/`grep` rooted outside
  the project) or worktree cleanup notes at the end of the skill — untouched.
- The stale-worktree fix only guards against the specific failure mode
  observed (branch moved between dispatch and worktree creation); it does
  not attempt to solve worktree staleness in general or add retry logic
  beyond the one `git merge` step.

## Testing

No test suite in this repo. Validate by actually running `/test-e2e` once
after the change and confirming: each subagent's report includes a task
count and a hook-test verdict, the stale-version check either passes
cleanly or demonstrably self-corrects, and the synthesized report's new
columns render with real (non-placeholder) data.
