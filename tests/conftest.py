"""Shared fixtures for the monitor engine's pytest suite. Every test runs
against a fresh tmp_path project root — never this repo's own real
monitor/ directory."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ENGINE_DIR = Path(__file__).resolve().parent.parent / "plugins" / "monitor" / "skills" / "monitor" / "scripts"


@pytest.fixture
def project_root(tmp_path: Path) -> Path:
    """A fresh scratch project: engine copied into monitor/scripts/, a real
    git repo (tasks/logger record commit shas and branch), and
    monitor/profile.json seeded via profile.py. Yields the project root."""
    scripts = tmp_path / "monitor" / "scripts"
    scripts.mkdir(parents=True)
    for f in ENGINE_DIR.glob("*.py"):
        (scripts / f.name).write_text(f.read_text(encoding="utf-8"), encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.test"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=tmp_path, check=True)
    subprocess.run([sys.executable, str(scripts / "profile.py"),
                    "--project-root", str(tmp_path)], check=True, capture_output=True)
    sys.path.insert(0, str(scripts))
    yield tmp_path
    sys.path.remove(str(scripts))
    # Drop the engine modules from sys.modules so the next project_root
    # invocation imports fresh module objects from its own tmp_path's
    # sys.path entry rather than reusing the ones loaded from the previous
    # tmp_path.
    #
    # What this does and does not buy: tests share one process, so this is
    # sys.path/sys.modules bookkeeping, not process isolation. It guarantees
    # only that engine modules are re-imported from the current test's copy of
    # the scripts. It does NOT undo anything an already-imported module did on
    # first import, unregister anything registered globally (atexit, warning
    # filters, signal handlers), reset third-party or stdlib modules, restore
    # os.environ or the cwd, or drop any module not named in the list below.
    # It is safe here because engine modules take their project root as an
    # argument and keep no module-level state tied to it — a module that
    # cached a root at import time would still leak across tests.
    for mod in ("tasks", "pending", "clean", "logger", "search", "status", "profile",
               "render_tasks", "render_logs", "render_report", "monitor_lib"):
        sys.modules.pop(mod, None)
