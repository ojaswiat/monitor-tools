import render_report


def test_template_has_date_created_and_last_modified_placeholders(project_root):
    profile = {"project": {"name": "demo"}, "kpis": [], "notes": {}}
    (project_root / "monitor" / "reports").mkdir(parents=True, exist_ok=True)
    render_report.render_template(profile, project_root)
    template = (project_root / "monitor" / "reports" / "template.html").read_text()
    assert "{{ date_created }}" in template
    assert "{{ last_modified }}" in template


def test_lock_report_stamps_last_modified(project_root):
    reports_dir = project_root / "monitor" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_path = reports_dir / "2026-07-27-demo.html"
    report_path.write_text(
        f"<html><head><style>{render_report.mlib.PALETTE_CSS}</style></head>"
        "<body><p>{{ last_modified }}</p></body></html>")
    render_report.lock_report_style(project_root, "2026-07-27-demo.html")
    text = report_path.read_text()
    assert "{{ last_modified }}" not in text  # got replaced with a real stamp
