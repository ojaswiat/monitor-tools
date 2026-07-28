# Companion skill usage — monitor-tools

Probed at `/monitor:init`. See `SKILL.md`'s companion table for the full
role/fallback description of each.

| Skill | Status | How monitor uses it here |
|---|---|---|
| **superpowers** | PRESENT (`.claude/settings.json` `enabledPlugins`) | Gates `/monitor:report` on `verification-before-completion` — reports render **verified** instead of falling back to unverified. |
| **ui-ux-pro-max** | PRESENT (`.claude/settings.json` `enabledPlugins`) | Not consulted for monitor's own pages — the report/log/dashboard design is fixed (`mlib.PALETTE_CSS`), identical regardless of this skill. |
| **graphify** | PRESENT (`~/.claude/skills/graphify`, global) | Available for orientation (query/path/explain) instead of grep when investigating this repo. |
| **find-skills** | PRESENT (`~/.claude/skills/find-skills`, global) | Available to improve skill discovery; not needed at init since companions were already known from prior sessions. |
| **openwiki** | ABSENT | No doc sync after commits — noted as a manual follow-up if docs drift from code. Recommended install: marketplace `SoulKyu/openwiki-cc`, plugin `openwiki`. |
| **copywriting** | ABSENT | Report prose written plainly, no polish pass. Recommended install: `npx skills add coreyhaines31/marketingskills@copywriting` (project-scoped). |

Note: this is monitor's own source repo dogfooding itself — the
`monitor/` folder here is generated local state (see `.gitignore`), not
committed, same as any consumer project's data folder.
