#!/usr/bin/env python3
"""SQLite log store for monitor/logs/log.db — the canonical operation log.

The schema is LOCKED: one table, fixed columns, created once by init_db() via
CREATE TABLE IF NOT EXISTS and never altered afterward. A future breaking
schema change is a new engine version, not a runtime migration — there is no
migration path here by design (see SKILL.md). An existing project's old
monitor/logs/operations.log (pre-SQLite installs) is left on disk untouched
but is never read by this module — it is abandoned, not imported.

`files` (list of paths) and `--set key=value` extras don't fit fixed scalar
columns, so they're stored as delimited/JSON TEXT rather than child tables:
  files   -- comma-joined paths, same convention as the old text log
  extras  -- compact JSON object string, e.g. '{"tests": "18/20"}'

`details` stays a single TEXT column. Structuring it (numbered points, bullet
points, labeled DECISION/WHY/... lines via a literal ``\\n`` between points,
never a freehand paragraph) is the writer's responsibility, not this module's
or the renderer's — see monitor_lib.format_list_block for how it's decoded
into real <ol>/<ul> markup at render time.

All queries are parameterized (?) — never string-build SQL with entry data.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR")
STATUSES = ("success", "partial", "failure")
SCHEMA_VERSION = 1

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS log_entries (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  timestamp     TEXT    NOT NULL,
  level         TEXT    NOT NULL CHECK(level IN ('DEBUG','INFO','WARNING','ERROR')),
  operation     TEXT    NOT NULL,
  tool          TEXT    NOT NULL,
  summary       TEXT    NOT NULL,
  status        TEXT    NOT NULL CHECK(status IN ('success','partial','failure')),
  branch        TEXT    NOT NULL DEFAULT '',
  task          TEXT    NOT NULL DEFAULT '',
  files         TEXT    NOT NULL DEFAULT '',
  details       TEXT    NOT NULL DEFAULT '',
  extras        TEXT    NOT NULL DEFAULT '{}',
  schemaVersion INTEGER NOT NULL
);
"""


def db_path(root: Path) -> Path:
    return root / "monitor" / "logs" / "log.db"


def connect(root: Path) -> sqlite3.Connection:
    path = db_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(root: Path) -> Path:
    """Create log.db + the locked schema if it doesn't exist yet. Idempotent."""
    conn = connect(root)
    try:
        conn.execute(SCHEMA_SQL)
        conn.commit()
    finally:
        conn.close()
    return db_path(root)


def insert_entry(root: Path, *, timestamp: str, level: str, operation: str,
                 tool: str, summary: str, status: str, branch: str = "",
                 task: str = "", files: list[str] | None = None,
                 details: str = "", extras: dict | None = None) -> int:
    """Insert one entry. Raises sqlite3.IntegrityError on a CHECK violation
    (bad level/status) — callers should catch and report a friendly error."""
    conn = connect(root)
    try:
        conn.execute(SCHEMA_SQL)  # belt-and-suspenders if init_db was skipped
        cur = conn.execute(
            "INSERT INTO log_entries "
            "(timestamp, level, operation, tool, summary, status, branch, "
            " task, files, details, extras, schemaVersion) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (timestamp, level, operation, tool, summary, status, branch,
             task, ", ".join(files or []), details,
             json.dumps(extras or {}), SCHEMA_VERSION))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def _row_to_entry(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"], "timestamp": row["timestamp"], "level": row["level"],
        "operation": row["operation"], "tool": row["tool"],
        "summary": row["summary"], "status": row["status"],
        "branch": row["branch"], "task": row["task"],
        "files": [f.strip() for f in row["files"].split(",") if f.strip()],
        "details": row["details"],
        "extra": json.loads(row["extras"] or "{}"),
    }


def fetch_all(root: Path) -> list[dict]:
    """All entries, newest first (highest id first)."""
    if not db_path(root).exists():
        return []
    conn = connect(root)
    try:
        conn.execute(SCHEMA_SQL)
        rows = conn.execute(
            "SELECT * FROM log_entries ORDER BY id DESC").fetchall()
        return [_row_to_entry(r) for r in rows]
    finally:
        conn.close()


def count(root: Path) -> int:
    if not db_path(root).exists():
        return 0
    conn = connect(root)
    try:
        conn.execute(SCHEMA_SQL)
        return conn.execute("SELECT COUNT(*) FROM log_entries").fetchone()[0]
    finally:
        conn.close()


def delete_newest(root: Path, n: int) -> int:
    """Delete the newest N entries (highest id first). Returns count deleted."""
    if not db_path(root).exists():
        return 0
    conn = connect(root)
    try:
        conn.execute(SCHEMA_SQL)
        ids = [r[0] for r in conn.execute(
            "SELECT id FROM log_entries ORDER BY id DESC LIMIT ?", (n,))]
        if ids:
            conn.executemany("DELETE FROM log_entries WHERE id = ?",
                             [(i,) for i in ids])
            conn.commit()
        return len(ids)
    finally:
        conn.close()
