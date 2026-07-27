import pending
import tasks


def test_open_tasks_lists_nonterminal_only(project_root):
    tasks.start_task(project_root, title="Still open")
    closed_id = tasks.start_task(project_root, title="Will close")
    tasks.close_task(project_root, task_id=closed_id, status="success", summary="done")
    open_list = pending.open_tasks(project_root)
    assert len(open_list) == 1
    assert open_list[0]["title"] == "Still open"


def test_check_text_mentions_open_task(project_root):
    tasks.start_task(project_root, title="Needs attention")
    text = pending.check_text(project_root)
    assert "Needs attention" in text
    assert "open task" in text


def test_check_text_empty_when_nothing_pending(project_root):
    assert pending.check_text(project_root) == ""


def test_clear_log_drains_oldest_reachable_entry(project_root):
    data = pending.load_pending(project_root)
    data["pending_logs"] = [{"sha": "deadbeef", "message": "x", "committed_at": "now"}]
    pending.save_pending(project_root, data)
    pending.clear_log(project_root, "deadbeef")
    assert pending.load_pending(project_root)["pending_logs"] == []
