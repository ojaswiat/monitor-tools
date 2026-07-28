import json
import subprocess
import sys

import status
import tasks


def test_compute_status_empty_project_has_sane_defaults(project_root):
    s = status.compute_status(project_root)
    assert s["branch"] in ("main", "master", "")
    assert s["open_tasks"] == []
    assert s["recent_logs"] == []
    assert s["pending"] == {"logs": [], "report": None, "task_signal": None}
    assert s["current_activity"] == {"source": "none", "summary": ""}
    assert s["next_steps"] == []
    # project_root's fixture scaffolds monitor/scripts/*.py before git init,
    # so those files are untracked from the start -- "clean" reflects that
    # real state rather than a genuinely empty repo.
    assert isinstance(s["git"]["uncommitted"]["clean"], bool)


def test_current_activity_prefers_open_task_over_log(project_root):
    import logger
    logger.log_operation(project_root, operation="op", tool="Bash",
                         summary="did a thing", status="success")
    tasks.start_task(project_root, title="The real task")
    s = status.compute_status(project_root)
    assert s["current_activity"] == {"source": "open_task", "summary": "The real task"}


def test_current_activity_falls_back_to_last_log_when_no_open_task(project_root):
    import logger
    logger.log_operation(project_root, operation="op", tool="Bash",
                         summary="did a thing", status="success")
    s = status.compute_status(project_root)
    assert s["current_activity"] == {"source": "last_log", "summary": "did a thing"}


def test_open_tasks_excludes_closed(project_root):
    open_id = tasks.start_task(project_root, title="Still open")
    closed_id = tasks.start_task(project_root, title="Will close")
    tasks.close_task(project_root, task_id=closed_id, status="success", summary="done")
    s = status.compute_status(project_root)
    assert [t["task_id"] for t in s["open_tasks"]] == [open_id]


def test_recent_logs_respects_log_limit(project_root):
    import logger
    for i in range(7):
        logger.log_operation(project_root, operation=f"op{i}", tool="Bash",
                             summary=f"entry {i}", status="success")
    s = status.compute_status(project_root, log_limit=3)
    assert len(s["recent_logs"]) == 3
    # newest-first
    assert s["recent_logs"][0]["summary"] == "entry 6"


def test_next_steps_extracts_labeled_fields_from_details(project_root):
    import logger
    logger.log_operation(project_root, operation="op", tool="Bash",
                         summary="did a thing", status="success",
                         details="DECISION: chose X\\nNEXT: wire up Y\\nGAPS: Z untested")
    s = status.compute_status(project_root)
    fields = {(step["field"], step["text"]) for step in s["next_steps"]}
    assert ("NEXT", "wire up Y") in fields
    assert ("GAPS", "Z untested") in fields
    assert not any(f == "DECISION" for f, _ in fields)


def test_next_steps_empty_when_no_details(project_root):
    import logger
    logger.log_operation(project_root, operation="op", tool="Bash",
                         summary="did a thing", status="success")
    s = status.compute_status(project_root)
    assert s["next_steps"] == []


def test_pending_section_mirrors_pending_json(project_root):
    import pending
    data = pending.load_pending(project_root)
    data["pending_logs"] = [{"sha": "deadbeef", "message": "x", "committed_at": "now"}]
    pending.save_pending(project_root, data)
    s = status.compute_status(project_root)
    assert s["pending"]["logs"] == data["pending_logs"]


def test_git_summary_reports_uncommitted_and_untracked(project_root):
    # Trigger __pycache__ creation (importing pending -> render_tasks) before
    # the baseline commit, so it's captured as part of "scaffold" rather than
    # showing up as untracked noise in the assertion below.
    status.compute_status(project_root)
    subprocess.run(["git", "add", "-A"], cwd=project_root, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "scaffold"], cwd=project_root, check=True)
    clean = status.compute_status(project_root)
    assert clean["git"]["uncommitted"] == {"modified": 0, "untracked": 0, "clean": True}

    (project_root / "f.txt").write_text("x")
    dirty = status.compute_status(project_root)
    assert dirty["git"]["uncommitted"]["untracked"] == 1
    assert dirty["git"]["uncommitted"]["clean"] is False


def test_git_summary_recent_commits_respects_commit_limit(project_root):
    for i in range(4):
        (project_root / f"f{i}.txt").write_text("x")
        subprocess.run(["git", "add", f"f{i}.txt"], cwd=project_root, check=True)
        subprocess.run(["git", "commit", "-q", "-m", f"commit {i}"], cwd=project_root, check=True)
    s = status.compute_status(project_root, commit_limit=2)
    assert len(s["git"]["recent_commits"]) == 2
    assert s["git"]["recent_commits"][0]["subject"] == "commit 3"


def test_main_prints_valid_json_to_stdout(project_root, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", [
        "status.py", "--project-root", str(project_root),
    ])
    status.main()
    captured = capsys.readouterr()
    parsed = json.loads(captured.out)
    assert "branch" in parsed
    assert "open_tasks" in parsed


def _non_cache_paths(root):
    return {p for p in root.rglob("*") if "__pycache__" not in p.parts}


def test_main_writes_no_files(project_root, monkeypatch, capsys):
    before = _non_cache_paths(project_root)
    monkeypatch.setattr(sys, "argv", [
        "status.py", "--project-root", str(project_root),
    ])
    status.main()
    capsys.readouterr()
    after = _non_cache_paths(project_root)
    assert before == after
