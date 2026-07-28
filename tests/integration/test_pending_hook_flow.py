"""Integration: the real hook entrypoints (hook_post_tool_use /
hook_user_prompt_submit), driven the same way Claude Code's hook runner
actually calls them — via stdin JSON, not the plain track()/check_text()
helpers directly."""

import io
import json
import subprocess
import sys

import pending


def test_unlogged_commit_then_clears_on_log(project_root, monkeypatch):
    (project_root / "f.txt").write_text("x")
    subprocess.run(["git", "add", "f.txt"], cwd=project_root, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "add f.txt"], cwd=project_root, check=True)
    sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=project_root,
                         capture_output=True, text=True, check=True).stdout.strip()

    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": "git commit -m x"}})
    monkeypatch.setattr(sys, "stdin", io.StringIO(payload))
    pending.hook_post_tool_use(project_root)
    data = pending.load_pending(project_root)
    assert any(e["sha"] == sha for e in data["pending_logs"])

    import logger
    logger.log_operation(project_root, operation="add-file", tool="Bash",
                         summary="added f.txt", status="success", last_commit_hash=sha)
    data = pending.load_pending(project_root)
    assert data["pending_logs"] == []


def test_plan_file_write_then_clears_on_task_start(project_root, monkeypatch):
    payload = json.dumps({"tool_name": "Write",
                          "tool_input": {"file_path": "docs/plans/x.md"}})
    monkeypatch.setattr(sys, "stdin", io.StringIO(payload))
    pending.hook_post_tool_use(project_root)
    data = pending.load_pending(project_root)
    assert data["pending_task_signal"]["path"] == "docs/plans/x.md"
    assert "no task tracked" in pending.check_text(project_root)

    import tasks
    tasks.start_task(project_root, title="Tracking the plan")
    data = pending.load_pending(project_root)
    assert data["pending_task_signal"] is None
