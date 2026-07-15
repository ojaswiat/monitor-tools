#!/usr/bin/env python3
"""Shared library for the `monitor` engine.

Provides project-root resolution, profile/schema/manifest IO, the shared
self-contained page CSS, and the Dashboard chrome (masthead + Reports/Logs
tab-nav) used by every generated page. All engine scripts import this.

Path model: when copied into a project as `monitor/scripts/<x>.py`, a script's
project root is `Path(__file__).resolve().parents[2]` and its monitor dir is
`.../monitor`. All scripts also accept `--project-root` to override.
"""

from __future__ import annotations

import argparse
import html
import json
import subprocess
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------- paths

def add_root_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--project-root", default=None,
        help="Repo root containing the monitor/ folder (default: inferred).")


def resolve_root(args) -> Path:
    """Return the project root that contains monitor/."""
    if getattr(args, "project_root", None):
        return Path(args.project_root).resolve()
    # monitor/scripts/<this>.py -> parents[2] is the repo root.
    p = Path(__file__).resolve()
    if p.parent.name == "scripts" and p.parent.parent.name == "monitor":
        return p.parents[2]
    return Path.cwd()


def monitor_dir(root: Path) -> Path:
    return root / "monitor"


# ---------------------------------------------------------------- IO

def load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def save_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2) + "\n", encoding="utf-8")


def load_profile(root: Path) -> dict:
    return load_json(monitor_dir(root) / "profile.json", {})


def require_init(root: Path) -> None:
    """Fail fast if monitor is not initialised (no profile.json). Only
    profile.py (which creates it) is exempt. Belt-and-suspenders behind the
    command-level init gate."""
    if not (monitor_dir(root) / "profile.json").exists():
        import sys
        print("monitor is not initialised for this project (no monitor/"
              "profile.json). Run /monitor:init first.", file=sys.stderr)
        sys.exit(2)


# ---------------------------------------------------------------- html

def esc(s) -> str:
    return html.escape(str(s), quote=True)


def now_stamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


# ---------------------------------------------------------------- vcs

def git_branch(root: Path) -> str:
    """Current git branch name, or "" when unavailable.

    Returns "" (never raises) outside a repo, without git, or on a detached
    HEAD that has no symbolic name — callers render a neutral placeholder so a
    non-git project still gets a working Dashboard.
    """
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, timeout=5)
    except Exception:  # noqa: BLE001 — git missing/unusable is not an error here
        return ""
    name = out.stdout.strip()
    if out.returncode != 0 or not name:
        return ""
    if name == "HEAD":  # detached — report the short sha instead
        sha = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5)
        head = sha.stdout.strip()
        return f"detached@{head}" if sha.returncode == 0 and head else ""
    return name


# The single source of truth for the report/log palette. Sharp corners, dual
# theme (light: near-black on off-white; dark: yellow on near-black), tabular
# numerals. Kept verbatim in generated pages so each file is self-contained.
PALETTE_CSS = """
  :root {
    --bg: #faf9f7; --surface: #ffffff; --text: #101418; --muted: #5a6472;
    --accent: #16181a; --accent-ink: #ffffff; --border: #d6d3cd; --hairline: #eae7e1;
    --code-bg: #f3f1ec; --pass: #15803d; --warn: #b45309; --fail: #b91c1c;
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --bg: #0b0d10; --surface: #0f1216; --text: #e9e7e2; --muted: #9aa3ad;
      --accent: #f5c518; --accent-ink: #111111; --border: #2c333b; --hairline: #1d2229;
      --code-bg: #14181e; --pass: #4ade80; --warn: #fbbf24; --fail: #f87171;
    }
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  html { scroll-behavior: smooth; }
  @media (prefers-reduced-motion: reduce) { html { scroll-behavior: auto; } * { transition: none !important; } }
  body { background: var(--bg); color: var(--text); font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; font-size: 16px; line-height: 1.6; }
  code, pre, .mono { font-family: "SF Mono", ui-monospace, Menlo, Consolas, monospace; }
  .wrap { max-width: 1080px; margin: 0 auto; padding: 0 24px 80px; }
  a { color: var(--accent); text-decoration: none; font-weight: 500; }
  a:hover { text-decoration: underline; }
  a:focus-visible, summary:focus-visible, label:focus-within { outline: 2px solid var(--accent); outline-offset: 2px; }
  .masthead { display: flex; justify-content: space-between; align-items: center; gap: 16px; padding: 14px 0; border-bottom: 1px solid var(--border); font-size: 0.72rem; letter-spacing: 0.14em; text-transform: uppercase; color: var(--muted); }
  .masthead .brand { color: var(--accent); font-weight: 700; }
  .masthead .mh-right { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; justify-content: flex-end; }
  .sr-only { position: absolute; width: 1px; height: 1px; padding: 0; overflow: hidden; clip-path: inset(50%); white-space: nowrap; border: 0; }
  .branchchip { display: inline-flex; align-items: center; gap: 5px; max-width: 34ch; border: 1px solid var(--border); background: var(--surface); padding: 2px 8px; font-family: "SF Mono", ui-monospace, Menlo, Consolas, monospace; font-size: 0.72rem; font-weight: 500; letter-spacing: 0; text-transform: none; color: var(--text); vertical-align: middle; }
  .branchchip svg { width: 11px; height: 11px; flex: 0 0 auto; color: var(--accent); }
  .branchchip .bname { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .branchchip.none { color: var(--muted); font-style: italic; }
  .back { display: inline-flex; align-items: center; gap: 6px; font-size: 0.72rem; font-weight: 700; letter-spacing: 0.14em; text-transform: uppercase; }
  .back svg { width: 13px; height: 13px; }
  header.report { padding: 40px 0 20px; border-bottom: 3px solid var(--accent); }
  header.report h1 { font-size: clamp(1.7rem, 4.5vw, 2.6rem); font-weight: 800; letter-spacing: -0.03em; line-height: 1.15; max-width: 26ch; }
  header.report .subtitle { margin-top: 10px; color: var(--muted); font-size: 0.95rem; }
  .tabnav { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 20px; }
  .tabnav a { border: 1px solid var(--border); padding: 8px 18px; font-size: 0.72rem; font-weight: 700; letter-spacing: 0.12em; text-transform: uppercase; color: var(--muted); background: var(--surface); }
  .tabnav a.active { color: var(--accent-ink); background: var(--accent); border-color: var(--accent); }
  .tabnav a:hover { text-decoration: none; color: var(--text); }
  .tabnav a.active:hover { color: var(--accent-ink); }
  .meta-chips { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 18px; }
  .chip { border: 1px solid var(--border); padding: 4px 10px; font-size: 0.74rem; color: var(--muted); }
  .chip b { color: var(--accent); font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; margin-right: 6px; font-size: 0.68rem; }
  .kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 12px; margin: 24px 0 8px; }
  .kpi { border: 1px solid var(--border); padding: 14px 16px; background: var(--surface); }
  .kpi.pass { border-left: 3px solid var(--pass); } .kpi.warn { border-left: 3px solid var(--warn); } .kpi.fail { border-left: 3px solid var(--fail); }
  .kpi .label { font-size: 0.66rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.1em; color: var(--accent); }
  .kpi.pass .label { color: var(--pass); } .kpi.warn .label { color: var(--warn); } .kpi.fail .label { color: var(--fail); }
  .kpi .value { margin-top: 4px; font-size: 1.45rem; font-weight: 750; letter-spacing: -0.01em; font-variant-numeric: tabular-nums; word-break: break-word; }
  .kpi .value.small { font-size: 1.0rem; }
  .table-scroll { overflow-x: auto; margin-top: 24px; }
  table { width: 100%; border-collapse: collapse; font-size: 0.92rem; }
  th { text-align: left; padding: 10px 14px; font-size: 0.66rem; font-weight: 800; text-transform: uppercase; letter-spacing: 0.1em; color: var(--accent); border-bottom: 2px solid var(--accent); }
  td { text-align: left; padding: 12px 14px; border-bottom: 1px solid var(--hairline); vertical-align: top; }
  tbody tr:hover { background: var(--code-bg); }
  .timestamp { color: var(--muted); font-size: 0.8rem; font-family: "SF Mono", ui-monospace, Menlo, Consolas, monospace; white-space: nowrap; }
  .description { color: var(--muted); font-size: 0.88rem; }
  .day-divider td { padding: 6px 14px; font-size: 0.66rem; font-weight: 800; text-transform: uppercase; letter-spacing: 0.12em; color: var(--accent); background: var(--code-bg); border-bottom: 1px solid var(--border); }
  .tag { display: inline-block; border: 1px solid currentColor; padding: 1px 8px; font-size: 0.66rem; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; font-family: "SF Mono", ui-monospace, Menlo, monospace; white-space: nowrap; }
  .tag.pass { color: var(--pass); } .tag.warn { color: var(--warn); } .tag.fail { color: var(--fail); } .tag.info { color: var(--accent); }
  .filter { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin: 22px 0 8px; border: none; }
  .filter .flabel { font-size: 0.66rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.1em; color: var(--muted); margin-right: 4px; }
  .filter input { position: absolute; opacity: 0; pointer-events: none; }
  .filter label { border: 1px solid var(--border); padding: 5px 12px; font-size: 0.72rem; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase; color: var(--muted); cursor: pointer; background: var(--surface); }
  .filter label:hover { color: var(--text); }
  #f-all:checked ~ label[for="f-all"], #f-success:checked ~ label[for="f-success"], #f-partial:checked ~ label[for="f-partial"], #f-fail:checked ~ label[for="f-fail"] { color: var(--accent-ink); background: var(--accent); border-color: var(--accent); }
  body:has(#f-success:checked) .logcard:not(.success), body:has(#f-partial:checked) .logcard:not(.partial), body:has(#f-fail:checked) .logcard:not(.fail) { display: none; }
  .log { margin-top: 12px; display: flex; flex-direction: column; gap: 10px; }
  .logcard { background: var(--surface); border: 1px solid var(--border); border-left: 3px solid var(--muted); padding: 14px 16px; }
  .logcard.success { border-left-color: var(--pass); } .logcard.partial { border-left-color: var(--warn); } .logcard.fail { border-left-color: var(--fail); }
  .logcard .row { display: flex; flex-wrap: wrap; align-items: baseline; gap: 8px 12px; }
  .logcard time { font-family: "SF Mono", ui-monospace, Menlo, Consolas, monospace; font-size: 0.78rem; color: var(--muted); font-variant-numeric: tabular-nums; white-space: nowrap; }
  .logcard .op { font-weight: 750; letter-spacing: -0.01em; }
  .logcard .toolchip, .logcard .xchip { font-family: "SF Mono", ui-monospace, Menlo, Consolas, monospace; font-size: 0.72rem; color: var(--muted); border: 1px solid var(--hairline); padding: 1px 6px; }
  .logcard .branchchip, td .branchchip { font-size: 0.7rem; padding: 1px 6px; border-color: var(--hairline); background: var(--code-bg); }
  td .branchchip { margin-top: 6px; }
  .logcard .spacer { flex: 1 1 auto; }
  .logcard .summary { margin-top: 8px; font-size: 0.95rem; }
  .logcard .task { margin-top: 6px; font-size: 0.78rem; color: var(--muted); }
  .logcard .task b { color: var(--accent); font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em; font-size: 0.68rem; }
  .files { margin-top: 8px; display: flex; flex-wrap: wrap; gap: 6px; }
  .files .file { font-family: "SF Mono", ui-monospace, Menlo, Consolas, monospace; font-size: 0.72rem; background: var(--code-bg); border: 1px solid var(--hairline); padding: 1px 6px; word-break: break-all; }
  .logcard details { margin-top: 10px; }
  .logcard summary { cursor: pointer; font-size: 0.7rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.1em; color: var(--accent); }
  .logcard details p { margin-top: 8px; font-size: 0.86rem; color: var(--text); line-height: 1.6; }
  .empty { border: 1px solid var(--border); background: var(--surface); padding: 28px; text-align: center; color: var(--muted); margin-top: 16px; }
  .card-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 16px; margin-top: 24px; }
  .navcard { display: block; border: 1px solid var(--border); border-left: 3px solid var(--accent); background: var(--surface); padding: 20px 22px; }
  .navcard:hover { text-decoration: none; background: var(--code-bg); }
  .navcard h3 { font-size: 0.7rem; font-weight: 800; text-transform: uppercase; letter-spacing: 0.12em; color: var(--accent); }
  .navcard p { margin-top: 8px; font-size: 0.9rem; color: var(--muted); }
  footer { margin-top: 48px; padding-top: 18px; border-top: 1px solid var(--border); display: flex; justify-content: space-between; flex-wrap: wrap; gap: 8px; font-size: 0.78rem; color: var(--muted); }
  @media print { :root { --bg: #ffffff; --text: #000000; --muted: #333333; } .masthead, footer, .filter { border-color: #999; } .logcard { break-inside: avoid; } }
"""

BACK_SVG = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            'stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" '
            'aria-hidden="true"><path d="M19 12H5"/><path d="M12 19l-7-7 7-7"/></svg>')

# git-branch glyph. An inline SVG (never an emoji) so it inherits currentColor
# and stays identical across platforms.
BRANCH_SVG = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" '
              'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" '
              'aria-hidden="true"><line x1="6" y1="3" x2="6" y2="15"/>'
              '<circle cx="18" cy="6" r="3"/><circle cx="6" cy="18" r="3"/>'
              '<path d="M18 9a9 9 0 0 1-9 9"/></svg>')

NO_BRANCH = "no branch"


def branch_chip(branch: str, extra_class: str = "") -> str:
    """Inline branch indicator: icon + name, with a visually-hidden "Branch"
    label so the meaning never rests on the icon or colour alone."""
    name = branch or NO_BRANCH
    cls = "branchchip" + (" none" if not branch else "")
    if extra_class:
        cls += " " + extra_class
    return (f'<span class="{cls}" title="Branch: {esc(name)}">{BRANCH_SVG}'
            f'<span class="sr-only">Branch </span>'
            f'<span class="bname">{esc(name)}</span></span>')


def project_name(profile: dict, root: Path) -> str:
    return (profile.get("project", {}) or {}).get("name") or root.name


def tabnav(active: str, prefix: str) -> str:
    """Reports/Logs tab-nav. `prefix` is the relative path back to monitor/.
    active is 'reports' or 'logs'."""
    def a(name, href, key):
        cls = ' class="active" aria-current="page"' if key == active else ''
        return f'<a href="{href}"{cls}>{name}</a>'
    return (f'<nav class="tabnav" aria-label="Dashboard pages">'
            f'{a("Reports", prefix + "reports/index.html", "reports")}'
            f'{a("Logs", prefix + "logs/index.html", "logs")}</nav>')


def page(title: str, brand: str, tag_kind: str, tag_text: str,
         header_html: str, body_html: str, footer_html: str,
         branch: str | None = None) -> str:
    """Render a page shell. `branch` is the current branch shown in the masthead
    of every page; pass None to omit the chip (e.g. the report template, which
    carries a `{{ branch }}` placeholder instead)."""
    chip = f"{branch_chip(branch)}\n      " if branch is not None else ""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<style>{PALETTE_CSS}</style>
</head>
<body>
<div class="wrap">

  <div class="masthead" id="top">
    <span><span class="brand">{esc(brand)}</span> · {esc(tag_text)}</span>
    <span class="mh-right">
      {chip}<span class="mono">{esc(now_stamp())}</span>
    </span>
  </div>

{header_html}

{body_html}

{footer_html}

</div>
</body>
</html>
"""
