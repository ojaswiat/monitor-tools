"""Integration: /monitor:status's real CLI entrypoint (subprocess, not the
compute_status() function directly), against a project that has been through
a real log + task + pending-commit flow -- this is what an agent session
actually sees when it runs the command."""

import json
import subprocess
import sys


def test_status_cli_reflects_full_project_state(project_root):
    import logger
    import tasks
    import pending

    logger.log_operation(project_root, operation="fix-bug", tool="Edit",
                         summary="Fixed the login bug", status="success",
                         details="DECISION: patched the session check\\n"
                                 "NEXT: add a regression test\\n"
                                 "GAPS: not verified on staging")
    task_id = tasks.start_task(project_root, title="Ship the login fix")

    (project_root / "f.txt").write_text("x")
    subprocess.run(["git", "add", "f.txt"], cwd=project_root, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "add f.txt"], cwd=project_root, check=True)
    sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=project_root,
                         capture_output=True, text=True, check=True).stdout.strip()
    pending.track(project_root, "commit", sha, "add f.txt")

    result = subprocess.run(
        [sys.executable, str(project_root / "monitor" / "scripts" / "status.py"),
         "--project-root", str(project_root)],
        capture_output=True, text=True, check=True,
    )
    data = json.loads(result.stdout)

    assert data["open_tasks"][0]["task_id"] == task_id
    assert data["current_activity"] == {"source": "open_task", "summary": "Ship the login fix"}
    assert any(e["summary"] == "Fixed the login bug" for e in data["recent_logs"])
    assert {"field": "NEXT", "text": "add a regression test", "from_operation": "fix-bug"} \
        in data["next_steps"]
    assert any(e["sha"] == sha for e in data["pending"]["logs"])

    # The command is chat-only -- nothing besides stdout is produced.
    assert result.stderr == ""


def test_status_cli_fails_before_init(tmp_path):
    (tmp_path / "monitor" / "scripts").mkdir(parents=True)
    import shutil
    from pathlib import Path
    engine_dir = Path(__file__).resolve().parent.parent.parent / \
        "plugins" / "monitor" / "skills" / "monitor" / "scripts"
    for f in engine_dir.glob("*.py"):
        shutil.copy(f, tmp_path / "monitor" / "scripts" / f.name)

    result = subprocess.run(
        [sys.executable, str(tmp_path / "monitor" / "scripts" / "status.py"),
         "--project-root", str(tmp_path)],
        capture_output=True, text=True,
    )
    assert result.returncode == 2
