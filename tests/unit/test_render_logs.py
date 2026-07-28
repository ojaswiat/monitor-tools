import render_logs


SAMPLE_MTR = """2026-07-27 10:00:00,000 INFO [edit-file] (Edit) Touched the parser -- success
branch:  main
last_commit_hash: abc1234
task_id: aaaa1111
files:   parser.py, lexer.py
tests: 54/54
details: DECISION: kept the hand-rolled parser.\\nWHY: no new dependency.
================================================================================
2026-07-27 09:00:00,000 ERROR [run-build] (Bash) Build broke -- failure
branch:  feat/x
================================================================================
"""

FRAGMENT_MTR = """this line is not a header
2026-07-27 10:00:00,000 INFO [edit-file] (Edit) Still parsed -- success
branch:  main
================================================================================
"""


def test_parse_log_round_trips_every_field():
    entries = render_logs.parse_log(SAMPLE_MTR)
    assert len(entries) == 2
    e = entries[0]
    assert e["timestamp"] == "2026-07-27 10:00:00,000"
    assert e["level"] == "INFO"
    assert e["operation"] == "edit-file"
    assert e["tool"] == "Edit"
    assert e["summary"] == "Touched the parser"
    assert e["status"] == "success"
    assert e["branch"] == "main"
    assert e["last_commit_hash"] == "abc1234"
    assert e["task_id"] == "aaaa1111"
    assert e["files"] == ["parser.py", "lexer.py"]
    assert e["extra"] == {"tests": "54/54"}
    assert e["details"].startswith("DECISION: kept the hand-rolled parser.")


def test_parse_log_is_newest_first():
    entries = render_logs.parse_log(SAMPLE_MTR)
    assert entries[0]["operation"] == "edit-file"
    assert entries[1]["operation"] == "run-build"
    assert entries[1]["status"] == "failure"


def test_parse_log_keeps_the_valid_entry_after_a_bad_line():
    entries = render_logs.parse_log(FRAGMENT_MTR)
    assert len(entries) == 2
    assert entries[0]["fragment"] == "this line is not a header"
    assert entries[1]["summary"] == "Still parsed"


def test_parse_log_records_an_all_garbage_block_as_a_fragment_only():
    entries = render_logs.parse_log("total nonsense\nmore nonsense\n")
    assert len(entries) == 1
    assert entries[0]["fragment"] == "total nonsense\nmore nonsense"


def test_parse_log_leaves_status_in_summary_when_not_a_known_status():
    entries = render_logs.parse_log(
        "2026-07-27 10:00:00,000 INFO [note] (Edit) a -- b\n")
    assert entries[0]["status"] == ""
    assert entries[0]["summary"] == "a -- b"


def test_render_writes_page_and_counts(project_root):
    log_path = project_root / "monitor" / "logs" / "operations.mtr"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(SAMPLE_MTR, encoding="utf-8")
    out = render_logs.render(project_root)
    html = out.read_text()
    assert "Touched the parser" in html
    assert "Build broke" in html
    assert "parser.py" in html
    # Total ops KPI counts both real entries.
    assert '<div class="value">2</div>' in html
