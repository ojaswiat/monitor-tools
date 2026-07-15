#!/usr/bin/env python3
"""Detect and reconcile monitor/profile.json — the project's source of truth.

Reconcile is strictly ADDITIVE: new detected keys/fields are added (stamped with
the new profileVersion); keys already present are left as-is (hand edits win);
nothing is ever removed or renamed. This is what makes schema/template upgrades
backward compatible.

Usage:  python3 profile.py --project-root <repo>   [--print]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import monitor_lib as mlib

DEFAULT_LOG_FIELDS = [
    {"key": "timestamp", "required": True,  "since": 1},
    {"key": "level",     "required": True,  "since": 1,
     "enum": ["DEBUG", "INFO", "WARNING", "ERROR"]},
    {"key": "operation", "required": True,  "since": 1},
    {"key": "tool",      "required": True,  "since": 1},
    {"key": "summary",   "required": True,  "since": 1},
    {"key": "status",    "required": True,  "since": 1,
     "enum": ["success", "partial", "failure"]},
    {"key": "details",   "required": False, "since": 1},
    {"key": "files",     "required": False, "since": 1, "type": "array"},
    {"key": "task",      "required": False, "since": 1},
    # Optional, not required: logging must keep working outside a git repo and
    # on older entries that predate this field.
    {"key": "branch",    "required": False, "since": 2},
]

DEFAULT_KPIS = [
    {"key": "tests",  "label": "Tests",  "since": 1},
    {"key": "commit", "label": "Commit", "since": 1},
    {"key": "status", "label": "Status", "since": 1},
]

DEFAULT_SECTIONS = ["summary", "asked", "done", "evidence", "files",
                    "risks", "followups", "steps"]


def detect(root: Path) -> dict:
    """Best-effort project detection. Language + build/test commands."""
    det = {"project": {"name": root.name}, "commands": {}}
    if (root / ".git").exists():
        det["project"]["vcs"] = "git"
    checks = [
        ("Package.swift", "swift", None, "swift test"),
        ("package.json", "javascript", None, "npm test"),
        ("Cargo.toml", "rust", "cargo build", "cargo test"),
        ("go.mod", "go", "go build ./...", "go test ./..."),
        ("pyproject.toml", "python", None, "pytest"),
        ("requirements.txt", "python", None, "pytest"),
        ("pom.xml", "java", "mvn package", "mvn test"),
    ]
    for fname, lang, build, test in checks:
        if (root / fname).exists():
            det["project"]["language"] = lang
            if build:
                det["commands"]["build"] = build
            if test:
                det["commands"]["test"] = test
            break
    # Prefer a build.sh if present (common for hand-rolled builds).
    if (root / "build.sh").exists():
        det["commands"]["build"] = "./build.sh"
    if (root / "package.json").exists():
        det["commands"].setdefault("build", "npm run build")
    return det


def _merge_list(existing: list, defaults: list, added: list, kind: str,
                version: int) -> list:
    """Merge default field/kpi entries into existing by 'key', additively."""
    out = list(existing)
    have = {e.get("key") for e in existing}
    for item in defaults:
        if item.get("key") not in have:
            entry = dict(item)
            entry["since"] = version
            out.append(entry)
            added.append(f"{kind}:{item['key']}")
    return out


def reconcile(existing: dict, det: dict) -> tuple[dict, list]:
    added: list[str] = []
    first = not existing
    version = int(existing.get("profileVersion", 0)) + 1
    prof = dict(existing)
    prof["profileVersion"] = version

    # project + commands: fill only missing keys (hand edits win).
    proj = dict(existing.get("project", {}))
    for k, v in det.get("project", {}).items():
        if k not in proj:
            proj[k] = v
            added.append(f"project.{k}")
    prof["project"] = proj

    cmds = dict(existing.get("commands", {}))
    for k, v in det.get("commands", {}).items():
        if k not in cmds:
            cmds[k] = v
            added.append(f"commands.{k}")
    prof["commands"] = cmds

    prof["kpis"] = _merge_list(existing.get("kpis", []), DEFAULT_KPIS,
                               added, "kpi", version)
    prof["logFields"] = _merge_list(existing.get("logFields", []),
                                    DEFAULT_LOG_FIELDS, added, "logField", version)
    if "reportSections" not in existing:
        prof["reportSections"] = list(DEFAULT_SECTIONS)
        if not first:
            added.append("reportSections")
    prof.setdefault("notes", existing.get("notes", {}))
    return prof, added


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mlib.add_root_arg(ap)
    ap.add_argument("--print", action="store_true", help="Print result only")
    args = ap.parse_args()
    root = mlib.resolve_root(args)
    existing = mlib.load_profile(root)
    prof, added = reconcile(existing, detect(root))
    if not args.print:
        mlib.save_json(mlib.monitor_dir(root) / "profile.json", prof)
    print(f"profileVersion={prof['profileVersion']} "
          f"({'created' if not existing else 'reconciled'})")
    if added:
        print("added: " + ", ".join(added))
    else:
        print("added: (nothing new)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
