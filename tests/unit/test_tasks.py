import pytest

import tasks


def test_start_task_returns_id_and_writes_block(project_root):
    task_id = tasks.start_task(project_root, title="Demo task")
    text = (project_root / "monitor" / "tasks" / "tasks.mtr").read_text()
    assert f"task_id: {task_id}" in text
    assert "title:   Demo task" in text


def test_update_rejects_terminal_status(project_root):
    task_id = tasks.start_task(project_root, title="Demo task")
    with pytest.raises(ValueError, match="requires a non-terminal status"):
        tasks.update_task(project_root, task_id=task_id, status="success", summary="bad")


def test_close_rejects_nonterminal_status(project_root):
    task_id = tasks.start_task(project_root, title="Demo task")
    with pytest.raises(ValueError, match="requires a terminal status"):
        tasks.close_task(project_root, task_id=task_id, status="open", summary="bad")


def test_update_unknown_task_id_rejected(project_root):
    with pytest.raises(ValueError, match="unknown task_id"):
        tasks.update_task(project_root, task_id="doesnotexist", status="open", summary="x")


def test_metrics_accumulate_across_events(project_root):
    task_id = tasks.start_task(project_root, title="Demo", tokens=100)
    tasks.update_task(project_root, task_id=task_id, status="in_progress",
                      summary="more work", tokens=50)
    tasks.close_task(project_root, task_id=task_id, status="success",
                     summary="done", tokens=25)
    import render_tasks
    text = (project_root / "monitor" / "tasks" / "tasks.mtr").read_text()
    groups = render_tasks.group_tasks(render_tasks.parse_tasks(text))
    assert groups[0]["tokens"] == 175
