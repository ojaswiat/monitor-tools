#!/usr/bin/env python3
"""Render monitor/logs/operations.log into monitor/logs/index.html (Logs page).

The text log stays canonical; this is a tolerant, human-readable view of it —
it renders entries from any schema version, showing unknown extra fields as
chips. Called by logger.py after every entry; also runnable standalone.

Usage:  python3 render_logs.py --project-root <repo>
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import monitor_lib as mlib

SEPARATOR = "=" * 80
STATUSES = {"success", "failure", "partial"}
STATUS_TAG = {"success": "pass", "partial": "warn", "failure": "fail"}
STATUS_CARD = {"success": "success", "partial": "partial", "failure": "fail"}
_HEADER = re.compile(r"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d,\d+) (\w+) \[([^\]]*)\] (.*)$")
KNOWN_EXTRA = {"task", "files", "details", "branch"}


def _extract_tool(rest: str) -> tuple[str, str]:
    if not rest.startswith("("):
        return "", rest
    depth = 0
    for i, ch in enumerate(rest):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return rest[1:i], rest[i + 1:].strip()
    return "", rest


def parse_log(text: str) -> list[dict]:
    """Parse the text log into entries, newest-first.

    Resilient and non-silent: if a block does not start with a valid header
    (e.g. a corrupted line was inserted after a separator), we scan for the
    first line that IS a valid header and parse the entry from there. The
    preceding garbage is preserved as an ``{"fragment": <text>}`` entry so a
    valid entry never vanishes because of an adjacent bad line, and the skipped
    fragment is surfaced (stderr warning + a distinct card) rather than dropped.
    """
    entries: list[dict] = []
    for block in text.split("\n" + SEPARATOR + "\n"):
        block = block.strip("\n")
        if not block:
            continue
        lines = block.split("\n")
        # Locate the first valid header line within the block.
        idx = 0
        while idx < len(lines) and not _HEADER.match(lines[idx]):
            idx += 1
        if idx > 0:
            # Lines before the first header are an unparseable fragment.
            frag = "\n".join(lines[:idx])
            sys.stderr.write(
                "render_logs: WARNING skipped unparseable log fragment "
                f"({idx} line(s)): {frag!r}\n")
            entries.append({"fragment": frag})
        if idx >= len(lines):
            continue  # whole block was garbage (already recorded as a fragment)
        m = _HEADER.match(lines[idx])
        lines = lines[idx:]
        timestamp, level, operation, rest = m.groups()
        status = ""
        if " -- " in rest:
            head, tail = rest.rsplit(" -- ", 1)
            if tail.strip() in STATUSES:
                rest, status = head, tail.strip()
        tool, summary = _extract_tool(rest)
        e = {"timestamp": timestamp, "level": level, "operation": operation,
             "tool": tool, "summary": summary, "status": status,
             "task": "", "files": [], "details": "", "branch": "", "extra": {}}
        for line in lines[1:]:
            if ":" not in line:
                continue
            key, val = line.split(":", 1)
            key, val = key.strip(), val.strip()
            if key == "branch":
                e["branch"] = val
            elif key == "task":
                e["task"] = val
            elif key == "files":
                e["files"] = [f.strip() for f in val.split(",") if f.strip()]
            elif key == "details":
                e["details"] = val
            else:
                e["extra"][key] = val
        entries.append(e)
    return entries


def _frag_card(e: dict) -> str:
    """Distinct card for an unparseable log fragment (sharp corners, .tag fail,
    dual-theme via the shared palette, no scripts/external assets)."""
    p = ['  <article class="logcard fail">', '    <div class="row">',
         '      <span class="op">⚠ unparseable log fragment</span>',
         '      <span class="spacer"></span>',
         '      <span class="tag fail">SKIPPED</span>', '    </div>',
         '    <p class="summary">A log block did not start with a valid header line and was skipped by the renderer. The canonical <code>operations.log</code> text is unchanged.</p>',
         '    <details>', '      <summary>Raw fragment</summary>',
         f'      <p><code>{mlib.esc(e["fragment"])}</code></p>',
         '    </details>', '  </article>']
    return "\n".join(p)


def _card(e: dict) -> str:
    if e.get("fragment") is not None:
        return _frag_card(e)
    card_cls = STATUS_CARD.get(e["status"], "")
    tag_cls = STATUS_TAG.get(e["status"], "info")
    tag_label = e["status"].upper() if e["status"] else "LOGGED"
    p = [f'  <article class="logcard {card_cls}">', '    <div class="row">',
         f'      <time>{mlib.esc(e["timestamp"])}</time>',
         f'      <span class="op">{mlib.esc(e["operation"])}</span>']
    if e["tool"]:
        p.append(f'      <span class="toolchip">{mlib.esc(e["tool"])}</span>')
    # The branch this operation was made on. Omitted (not "no branch") when the
    # entry predates the field, so old entries stay clean rather than look wrong.
    if e.get("branch"):
        p.append("      " + mlib.branch_chip(e["branch"]))
    for k, v in e["extra"].items():
        p.append(f'      <span class="xchip">{mlib.esc(k)}: {mlib.esc(v)}</span>')
    p.append('      <span class="spacer"></span>')
    p.append(f'      <span class="tag {tag_cls}">{mlib.esc(tag_label)}</span>')
    p.append('    </div>')
    if e["summary"]:
        p.append(f'    <p class="summary">{mlib.esc(e["summary"])}</p>')
    if e["task"]:
        p.append(f'    <p class="task"><b>Task</b> {mlib.esc(e["task"])}</p>')
    if e["files"]:
        chips = "".join(f'<span class="file">{mlib.esc(f)}</span>' for f in e["files"])
        p.append(f'    <div class="files">{chips}</div>')
    if e["details"]:
        p += ['    <details>', '      <summary>Details</summary>',
              f'      <p>{mlib.esc(e["details"])}</p>', '    </details>']
    p.append('  </article>')
    return "\n".join(p)


def build_html(entries: list[dict], brand: str, branch: str = "") -> str:
    real = [e for e in entries if e.get("fragment") is None]
    frags = [e for e in entries if e.get("fragment") is not None]
    total = len(real)
    counts = {"success": 0, "partial": 0, "failure": 0}
    for e in real:
        if e["status"] in counts:
            counts[e["status"]] += 1
    last = real[0]["timestamp"] if real else "—"
    fragkpi = (f'\n    <div class="kpi fail"><div class="label">Skipped fragments</div>'
               f'<div class="value">{len(frags)}</div></div>') if frags else ""
    header = f"""  <header class="report">
    <h1>Logs</h1>
    <p class="subtitle">Agent operation log — newest first. Rendered from <code>monitor/logs/operations.log</code>.</p>
    {mlib.tabnav("logs", "../")}
  </header>

  <div class="kpis">
    <div class="kpi"><div class="label">Current branch</div><div class="value small mono">{mlib.esc(branch or mlib.NO_BRANCH)}</div></div>
    <div class="kpi"><div class="label">Total ops</div><div class="value">{total}</div></div>
    <div class="kpi pass"><div class="label">Success</div><div class="value">{counts['success']}</div></div>
    <div class="kpi warn"><div class="label">Partial</div><div class="value">{counts['partial']}</div></div>
    <div class="kpi fail"><div class="label">Failure</div><div class="value">{counts['failure']}</div></div>
    <div class="kpi"><div class="label">Last activity</div><div class="value small mono">{mlib.esc(last)}</div></div>{fragkpi}
  </div>

  <fieldset class="filter" aria-label="Filter by status">
    <span class="flabel">Filter</span>
    <input type="radio" name="f" id="f-all" checked>
    <input type="radio" name="f" id="f-success">
    <input type="radio" name="f" id="f-partial">
    <input type="radio" name="f" id="f-fail">
    <label for="f-all">All</label><label for="f-success">Success</label>
    <label for="f-partial">Partial</label><label for="f-fail">Failure</label>
  </fieldset>"""
    if entries:
        body = '  <div class="log">\n' + "\n".join(_card(e) for e in entries) + "\n  </div>"
    else:
        body = '  <div class="empty">No operations logged yet.</div>'
    footer = (f'  <footer><span>Rendered from monitor/logs/operations.log · {total} entries.</span>'
              f'<span><a href="../index.html">← Dashboard</a> · <a href="#top">↑ Back to Top</a></span></footer>')
    return mlib.page(f"Logs — {brand} Monitor", brand, "info", "Monitor · Logs",
                     header, body, footer, branch=branch)


def render(root: Path) -> Path:
    mdir = mlib.monitor_dir(root)
    log_path = mdir / "logs" / "operations.log"
    out = mdir / "logs" / "index.html"
    text = log_path.read_text(encoding="utf-8") if log_path.exists() else ""
    profile = mlib.load_profile(root)
    brand = mlib.project_name(profile, root)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build_html(parse_log(text), brand, mlib.git_branch(root)),
                   encoding="utf-8")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mlib.add_root_arg(ap)
    args = ap.parse_args()
    root = mlib.resolve_root(args)
    mlib.require_init(root)
    print(f"wrote {render(root)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
