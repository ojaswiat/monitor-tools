#!/usr/bin/env python3
"""Render monitor/tasks/tasks.mtr into paginated monitor/tasks/*.html.

Groups task-start/task-update/task-close events by task_id into one card per
task: current status, aggregated metrics (tokens/credits/cost summed,
skills_used/tools_called unioned), and a collapsible oldest-to-newest
timeline. Called by tasks.py after every event; also runnable standalone.

Usage:  python3 render_tasks.py --project-root <repo>
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import monitor_lib as mlib

SEPARATOR = "=" * 80
_HEADER = re.compile(
    r"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d,\d+) (\w+) \[([^\]]*)\] \(([^)]*)\) (.*)$")
_PAGE_FILE_RE = re.compile(r"^page-(\d+)\.html$")

NONTERMINAL = ("open", "in_progress", "needs_approval", "needs_retry", "blocked")
TERMINAL = ("success", "failed", "cancelled")
STATUS_TAG_CLASS = {
    "open": "info", "in_progress": "info",
    "needs_approval": "warn", "needs_retry": "warn", "blocked": "warn",
    "success": "pass", "failed": "fail", "cancelled": "fail",
}


def split_blocks(text: str) -> list[str]:
    """Split tasks.mtr into its raw event blocks, exactly the way parse_tasks
    does (so block N here is event N there)."""
    return [b for b in (blk.strip("\n") for blk in text.split("\n" + SEPARATOR + "\n")) if b]


def block_task_id(block: str) -> str:
    """The task_id a raw block *belongs to*, read from its own header line.
    Empty for an unparseable block. Callers must use this rather than
    substring-searching a block's text: `details` may legitimately mention
    another task's id, and that must never make the block look like that
    task's event."""
    m = _HEADER.match(block.split("\n", 1)[0])
    return m.group(4) if m else ""


def parse_tasks(text: str) -> list[dict]:
    """Parse tasks.mtr into flat events, newest-first — one dict per
    task-start/task-update/task-close block. Tolerant the same way
    render_logs.parse_log is: an unparseable block is skipped with a stderr
    warning rather than corrupting the rest of the read."""
    entries: list[dict] = []
    for block in split_blocks(text):
        lines = block.split("\n")
        m = _HEADER.match(lines[0])
        if not m:
            sys.stderr.write(f"render_tasks: WARNING skipped unparseable block: {lines[0]!r}\n")
            continue
        timestamp, level, event, task_id, rest = m.groups()
        summary, status = rest, ""
        if " -- " in rest:
            summary, status = rest.rsplit(" -- ", 1)
        e = {"timestamp": timestamp, "level": level, "event": event,
             "task_id": task_id, "summary": summary, "status": status,
             "title": "", "branch": "", "last_commit_hash": "",
             "tokens": None, "credits": None, "cost": None,
             "skills_used": [], "tools_called": [], "details": ""}
        for line in lines[1:]:
            if ":" not in line:
                continue
            key, val = line.split(":", 1)
            key, val = key.strip(), val.strip()
            if key == "title":
                e["title"] = val
            elif key == "branch":
                e["branch"] = val
            elif key == "last_commit_hash":
                e["last_commit_hash"] = val
            elif key in ("tokens", "credits", "cost"):
                try:
                    e[key] = float(val)
                except ValueError:
                    pass
            elif key == "skills_used":
                e["skills_used"] = [s.strip() for s in val.split(",") if s.strip()]
            elif key == "tools_called":
                e["tools_called"] = [t.strip() for t in val.split(",") if t.strip()]
            elif key == "details":
                e["details"] = val
        entries.append(e)
    return entries


def group_tasks(entries: list[dict]) -> list[dict]:
    """Group flat events (newest-first) by task_id. Each group's `status` is
    whichever event was encountered first per id (since the input is
    newest-first, that's the most recent event); `created_at` is the
    timestamp of its task-start event specifically (falling back to the
    earliest event seen for that id, if task-start isn't in the retained
    window); `events` is collected then reversed to oldest-to-newest for
    timeline display."""
    groups: dict[str, dict] = {}
    order: list[str] = []
    for e in entries:
        tid = e["task_id"]
        if tid not in groups:
            groups[tid] = {"task_id": tid, "title": "", "status": e["status"],
                          "branch": e.get("branch", ""), "tokens": 0.0,
                          "has_tokens": False, "credits": 0.0, "cost": 0.0,
                          "skills_used": [], "tools_called": [], "events": [],
                          "created_at": e["timestamp"]}
            order.append(tid)
        g = groups[tid]
        g["events"].append(e)
        if e.get("title"):
            g["title"] = e["title"]
        if e["event"] == "task-start" or e["timestamp"] < g["created_at"]:
            g["created_at"] = e["timestamp"]
        if e.get("tokens") is not None:
            # Tracked separately from the sum so a task that reported
            # `--tokens 0` still shows a tokens chip, and one that never
            # reported tokens at all shows none — same rule as credits/cost.
            g["tokens"] += e["tokens"]
            g["has_tokens"] = True
        if e.get("credits") is not None:
            g["credits"] += e["credits"]
        if e.get("cost") is not None:
            g["cost"] += e["cost"]
        for s in e.get("skills_used", []):
            if s not in g["skills_used"]:
                g["skills_used"].append(s)
        for t in e.get("tools_called", []):
            if t not in g["tools_called"]:
                g["tools_called"].append(t)
    result = [groups[tid] for tid in order]
    for g in result:
        g["events"].reverse()  # oldest-to-newest for the timeline
    return result


def count_open(root: Path) -> int:
    path = mlib.monitor_dir(root) / "tasks" / "tasks.mtr"
    if not path.exists():
        return 0
    entries = parse_tasks(path.read_text(encoding="utf-8"))
    groups = group_tasks(entries)
    return sum(1 for g in groups if g["status"] in NONTERMINAL)


def _card(g: dict) -> str:
    tag_cls = STATUS_TAG_CLASS.get(g["status"], "info")
    p = ['  <article class="logcard">', '    <div class="row">',
         f'      <span class="op">{mlib.esc(g["title"] or g["task_id"])}</span>',
         f'      <span class="toolchip">id: {mlib.esc(g["task_id"])}</span>']
    if g.get("branch"):
        p.append("      " + mlib.branch_chip(g["branch"]))
    if g.get("has_tokens"):
        p.append(f'      <span class="toolchip">tokens: {int(g["tokens"])}</span>')
    if g["credits"]:
        p.append(f'      <span class="toolchip">credits: {g["credits"]:g}</span>')
    if g["cost"]:
        p.append(f'      <span class="toolchip">cost: {g["cost"]:g}</span>')
    p.append('      <span class="spacer"></span>')
    p.append(f'      <span class="tag {tag_cls}">{mlib.esc(g["status"].upper())}</span>')
    p.append('    </div>')
    if g["skills_used"] or g["tools_called"]:
        chips = "".join(f'<span class="file">{mlib.esc(s)}</span>' for s in g["skills_used"] + g["tools_called"])
        p.append(f'    <div class="files">{chips}</div>')
    p += ['    <details>', '      <summary>Timeline</summary>']
    for e in g["events"]:
        p.append(f'      <p>{mlib.esc(e["timestamp"])} — <b>{mlib.esc(e["status"])}</b> — {mlib.esc(e["summary"])}</p>')
        if e.get("details"):
            # Same convention log entries use: literal \n between points,
            # decoded into a real list by format_list_block.
            p.append(f'      {mlib.format_list_block(e["details"])}')
    p += ['    </details>', '  </article>']
    return "\n".join(p)


def build_html(page_groups: list[dict], brand: str, branch: str, *, total: int,
               n_open: int, page_num: int, total_pages: int) -> str:
    header = f"""  <header class="report">
    <h1>Tasks</h1>
    <p class="subtitle">Lifecycle-tracked units of work, newest first. Rendered from <code>monitor/tasks/tasks.mtr</code>.</p>
    {mlib.tabnav("tasks", "../")}
  </header>

  <div class="kpis">
    <div class="kpi"><div class="label">Current branch</div><div class="value small mono">{mlib.esc(branch or mlib.NO_BRANCH)}</div></div>
    <div class="kpi"><div class="label">Total tasks</div><div class="value">{total}</div></div>
    <div class="kpi warn"><div class="label">Open</div><div class="value">{n_open}</div></div>
  </div>"""
    if page_groups:
        body = '  <div class="log">\n' + "\n".join(_card(g) for g in page_groups) + "\n  </div>"
    else:
        body = '  <div class="empty">No tasks yet.</div>'
    body += "\n" + mlib.pagination_nav(page_num, total_pages, total)
    noun = "task" if total == 1 else "tasks"
    footer = (f'  <footer><span>Rendered from monitor/tasks/tasks.mtr · {total} {noun}.</span>'
              f'<span><a href="../index.html">← Dashboard</a> · <a href="#top">↑ Back to Top</a></span></footer>')
    title = "Tasks" if total_pages <= 1 else f"Tasks (page {page_num}/{total_pages})"
    return mlib.page(f"{title} — {brand} Monitor", brand, "info", "Monitor · Tasks",
                     header, body, footer, branch=branch)


def _prune_stale_pages(tasks_dir: Path, total_pages: int) -> None:
    for f in tasks_dir.glob("page-*.html"):
        m = _PAGE_FILE_RE.match(f.name)
        if m and int(m.group(1)) > total_pages:
            f.unlink()


def render(root: Path) -> Path:
    mdir = mlib.monitor_dir(root)
    tasks_dir = mdir / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    tasks_path = tasks_dir / "tasks.mtr"
    text = tasks_path.read_text(encoding="utf-8") if tasks_path.exists() else ""
    profile = mlib.load_profile(root)
    brand = mlib.project_name(profile, root)
    branch = mlib.git_branch(root)

    entries = parse_tasks(text)
    groups = group_tasks(entries)
    total = len(groups)
    n_open = sum(1 for g in groups if g["status"] in NONTERMINAL)
    total_pages = max(1, -(-total // mlib.PAGE_SIZE))

    for page_num in range(1, total_pages + 1):
        start = (page_num - 1) * mlib.PAGE_SIZE
        page_groups = groups[start:start + mlib.PAGE_SIZE]
        html = build_html(page_groups, brand, branch, total=total, n_open=n_open,
                          page_num=page_num, total_pages=total_pages)
        (tasks_dir / mlib.page_filename(page_num)).write_text(html, encoding="utf-8")

    _prune_stale_pages(tasks_dir, total_pages)
    return tasks_dir / "index.html"


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
