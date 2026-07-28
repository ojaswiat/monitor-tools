---
name: test-installation
description: Verifies the monitor plugin actually resolves as invokable Skills through the real marketplace-plugin install path, not just correct-looking config. Use when asked to test plugin installation, verify monitor registers correctly, debug "Unknown skill: monitor:*" errors, or after editing marketplace.json/plugin.json/settings.json plugin entries.
---

# test-installation

Config that *looks* right (`.claude-plugin/marketplace.json`,
`extraKnownMarketplaces`/`enabledPlugins` in `settings.json`) is not proof
the plugin resolves. Hand-editing those JSON blocks directly was tried in
this repo and silently failed — `monitor:*` skills never appeared, with no
error until an actual `Skill()` call returned `Unknown skill`. The only
real registration path is the interactive commands below; they write
additional state hand-edits skip.

## Known gotchas (why config alone lies)

- **`extraKnownMarketplaces`/`enabledPlugins` hand-edits are not sufficient.**
  Only `/plugin marketplace add` + `/plugin install` reliably register a
  plugin's skills. If `settings.json` already has plugin entries but
  `monitor:*` skills don't resolve, redo the install via the real commands
  rather than trusting the existing JSON.
- **A `github` source with no branch pin resolves to the repo's default
  branch**, not whichever branch you're actually on. If the default branch
  (commonly `main`) is behind your working branch, the cached plugin is
  stale — check the version in `~/.claude/plugins/cache/<marketplace>/<plugin>/`
  against `plugins/monitor/.claude-plugin/plugin.json` on the branch you
  expect to be serving.
- **Registration is a session-start snapshot.** Editing settings.json or
  running `/plugin marketplace update` mid-session does not hot-reload the
  skill list — run `/reload-plugins` (or restart) before testing.
- **A stale manual-copy fallback masks a broken plugin install.** If
  `.claude/skills/monitor/` and `.claude/commands/monitor/` exist from
  `install-monitor.sh`, `/monitor:*` commands keep working even if the
  plugin path is fully broken — you're testing the fallback, not the
  plugin. Remove both before testing the plugin path for real.

## Verification steps

1. Confirm the marketplace source resolves to the branch you expect:
   `cat .claude-plugin/marketplace.json` and check the plugin source path/branch.
2. Register for real (interactive slash commands — cannot be scripted around):
   ```
   /plugin marketplace add <owner>/<repo>      # or an absolute local path
   /plugin install monitor@<marketplace-name>
   /reload-plugins
   ```
3. Remove any manual-copy fallback so there's nothing to mask a failure:
   ```
   rm -rf .claude/skills/monitor .claude/commands/monitor
   ```
4. Confirm `$CLAUDE_PLUGIN_ROOT` and the fallback dirs are both absent, then
   invoke a real skill call — e.g. `Skill(skill: "monitor:search")` or any
   `/monitor:*` command. `Unknown skill: monitor:*` means registration
   failed; a normal skill prompt loading means it passed.
5. Run the invoked command to completion (e.g. a real search or log) to
   confirm the engine scripts underneath also resolve correctly, not just
   the skill prompt.

## Quick reference

| Symptom | Cause | Fix |
|---|---|---|
| `Unknown skill: monitor:*` after settings.json edit | Hand-edit isn't a real install | Run `/plugin marketplace add` + `/plugin install` |
| Skills list unchanged after editing settings.json | Registration is snapshot at session start | `/reload-plugins` or restart |
| Plugin version in cache is older than expected | `github` source pinned to stale default branch | Merge/fast-forward the default branch, or pin a branch in the source |
| `/monitor:*` commands work but you're not sure if it's the plugin or a stale manual copy | Fallback dirs present | `rm -rf .claude/skills/monitor .claude/commands/monitor`, retest |
