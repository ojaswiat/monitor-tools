# Pending-state enforcement — design

## Problem

`monitor`'s logging/reporting policy today is discretion-based: `CLAUDE.md`
tells the agent to log after every commit and report after merges/rebases,
but nothing enforces it. This session's dogfood drills already produced one
concrete failure — the same wording worked in one drill and silently didn't
in an earlier manual drill. A policy an agent can rationalize skipping under
pressure isn't a gate.

## Goal

A soft-but-real enforcement mechanism: after a commit/merge/rebase with
unlogged/unreported state, the agent is reminded at the start of its next
turn and must explicitly ask the user Y/N before continuing — not a hard
tool-call block, but not silently skippable either.

## Non-goals

- True hard gating (denying tool calls outright) — considered and rejected
  in favor of the softer Y/N flow (user's explicit choice).
- Preserving individual commit shas through a `git rebase` — rebase rewrites
  history, so pending log entries tied to now-rewritten shas are folded into
  the report range instead (see "Rebase handling" below).
- Any change to git hooks (`.git/hooks/`) — this lives entirely in Claude
  Code's own hook system, which already has agent context and doesn't need
  a separate LLM call or a per-clone hook install step.

## Components

### `monitor/scripts/pending.py` (new engine script)

Stdlib-only, same convention as the other engine scripts (`--project-root`
override, `mlib.require_init()` gate). Two subcommands:

- `pending.py track` — invoked after a `git commit`/`git merge`/`git rebase`
  Bash call. Reads the command that ran and the current `git rev-parse HEAD`,
  updates `monitor/.pending.json`:
  - `git commit` → append `{sha, message, committed_at}` to `pending_logs`.
  - `git merge` / `git rebase` completing → set `pending_report` to
    `{event, since_sha, detected_at}`, where `since_sha` is the previous
    `last_report_sha`.
- `pending.py check` — reads `monitor/.pending.json`. If `pending_logs` is
  non-empty or `pending_report` is set, prints the warning text (see below)
  to stdout. Otherwise prints nothing.

### `monitor/.pending.json` (new state file, committed)

Lives inside the existing `monitor/` folder and is committed alongside it,
consistent with the standing rule that `monitor/` travels with every commit
— this file is per-branch state and needs to survive push/pull/clone the
same way logs and reports do, not disappear as local-only cruft.

```json
{
  "branch": "adding-dependency-skills",
  "pending_logs": [
    {"sha": "bd3ecb7", "message": "fix: correct test-e2e skill...", "committed_at": "2026-07-25T10:03:00"}
  ],
  "pending_report": {
    "event": "merge",
    "since_sha": "58e342a",
    "detected_at": "2026-07-25T11:00:00"
  },
  "last_report_sha": "58e342a"
}
```

`branch` is informational (written by `track`, read by `check` for the
warning text) — actual isolation between branches/worktrees comes for free
from each checkout having its own working-tree copy of the file, not from
this field.

### Two Claude Code hooks, written into the consumer project's `.claude/settings.json`

Installed by a new step in `/monitor:init` (same pattern already used for
companion-skill installs: merge in, don't clobber existing keys), project-
scoped so every clone of the repo gets them:

- **`PostToolUse`** on `Bash`, matcher on command containing `git commit`,
  `git merge`, or `git rebase` → runs `python3 monitor/scripts/pending.py
  track`. Purely mechanical (parses the command string + current HEAD sha),
  no LLM judgment — this is what makes it reliable even though the hook
  itself has no "brain."
- **`UserPromptSubmit`** → runs `python3 monitor/scripts/pending.py check`.
  Its stdout becomes injected context on the agent's next turn — the same
  mechanism already visibly firing all session for other project hooks
  (e.g. session mode reminders). This is what makes the gate "soft": it
  surfaces at the next turn boundary, not mid-tool-call.

### Warning text and Y/N flow

When `check` finds pending state, the agent sees context equivalent to:

```
[Warn!] Monitor: Pending logs and report. Do you want Monitor to record now [Y/N]
```

The agent surfaces this to the user verbatim (or near-verbatim) as its own
message and waits for an answer:

- **Y** → read `monitor/.pending.json`. For each `pending_logs` entry, run
  `/monitor:log` (commit message is a starting point; `DECISION`/`WHY`/etc.
  fields are still the agent's judgment, same as today). For a set
  `pending_report`, run `git log <since_sha>..HEAD` to determine the real
  commit range — using live git history rather than trusting stored shas is
  what makes this safe across a rebase — then generate one report covering
  it. The user's original prompt continues normally afterward.
- **N** → print "Skipping monitor. What next?" (or equivalent), leave
  `monitor/.pending.json` untouched (it stays pending and will re-warn on
  the next turn), continue with whatever the user asks for.

### Clearing pending state

- `logger.py` removes the matching sha from `pending_logs` after a
  successful `/monitor:log` call for that commit.
- `render_report.py` clears `pending_report` and sets `last_report_sha` to
  the current `HEAD` after a successful `/monitor:report`.

## Rebase handling

Rebase rewrites commit shas, so a `pending_logs` entry recorded before a
rebase may point at a sha that no longer exists afterward. Rule: don't try
to track individual shas through a rewrite. On the `track` call that fires
after a rebase completes, any `pending_logs` entries whose sha no longer
resolves (`git cat-file -e <sha>` fails) are dropped from `pending_logs` and
folded into `pending_report`'s range instead — the eventual report is built
from `git log since_sha..HEAD` at report time, which reflects reality
regardless of what got rewritten in between.

## Install / rollout

- New `/monitor:init` step: after the existing companion-skill probe/install
  step, merge the two hook entries into the project's `.claude/settings.json`
  (additive merge, same non-clobbering approach as companion installs).
- `/monitor:update` should also be able to add these hooks to
  already-initialized projects that predate this feature (reconciliation is
  additive, same guarantee as `profile.py`).
- No `.gitignore` changes — `monitor/.pending.json` is committed, not
  ignored.

## Testing

No automated test suite in this repo (confirmed standing decision — engine
isn't growing further in complexity that would need one). Verification is a
live dry run, same bar as the `test-e2e` skill: make a commit, confirm
`.pending.json` gets a `pending_logs` entry, confirm the next turn's context
carries the warning, answer Y, confirm the log gets written and the entry
clears. Repeat for a merge and a rebase to confirm `pending_report`
behavior and the rebase-fold rule.
