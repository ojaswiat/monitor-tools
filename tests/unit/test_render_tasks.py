import render_tasks


SAMPLE_MTR = """2026-07-27 10:00:00,000 INFO [task-close] (aaaa1111) done -- success
task_id: aaaa1111
branch:  main
================================================================================
2026-07-27 09:00:00,000 INFO [task-start] (aaaa1111) started: Demo -- open
task_id: aaaa1111
title:   Demo
branch:  main
================================================================================
"""


def test_parse_tasks_extracts_fields():
    entries = render_tasks.parse_tasks(SAMPLE_MTR)
    assert len(entries) == 2
    assert entries[0]["event"] == "task-close"
    assert entries[1]["title"] == "Demo"


def test_group_tasks_created_at_is_task_start_time():
    entries = render_tasks.parse_tasks(SAMPLE_MTR)
    groups = render_tasks.group_tasks(entries)
    assert groups[0]["created_at"] == "2026-07-27 09:00:00,000"
    assert groups[0]["status"] == "success"  # most recent event's status


def test_block_task_id_ignores_mentions_in_details():
    block = ('2026-07-27 10:00:00,000 INFO [task-close] (bbbb2222) done -- success\n'
             'task_id: bbbb2222\n'
             'details: follow-on from task_id: aaaa1111')
    assert render_tasks.block_task_id(block) == "bbbb2222"
