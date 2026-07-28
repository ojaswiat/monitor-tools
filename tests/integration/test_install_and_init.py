"""Integration: install-monitor.sh itself — the manual-copy install path —
followed by the init that generates a project's monitor/ data folder."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
INSTALLER = REPO_ROOT / "install-monitor.sh"


@pytest.fixture
def installed_project(tmp_path: Path) -> Path:
    target = tmp_path / "scratch"
    target.mkdir()
    out = subprocess.run(["bash", str(INSTALLER), str(target)],
                         capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    return target


def test_installer_copies_engine_and_commands(installed_project: Path):
    skill = installed_project / ".claude" / "skills" / "monitor"
    assert (skill / "SKILL.md").is_file()
    assert (skill / "scripts" / "logger.py").is_file()
    assert (skill / "assets" / "base_template.html").is_file()
    assert not list(skill.rglob("__pycache__"))
    commands = installed_project / ".claude" / "commands" / "monitor"
    names = sorted(p.name for p in commands.glob("*.md"))
    for expected in ("init.md", "log.md", "report.md", "record.md", "search.md"):
        assert expected in names


def test_installer_leaves_the_data_folder_alone(installed_project: Path):
    assert not (installed_project / "monitor").exists()


def test_installer_refuses_to_overwrite_without_force(installed_project: Path):
    again = subprocess.run(["bash", str(INSTALLER), str(installed_project)],
                           capture_output=True, text=True)
    assert again.returncode == 1
    assert "already installed" in again.stderr
    forced = subprocess.run(["bash", str(INSTALLER), str(installed_project), "--force"],
                            capture_output=True, text=True)
    assert forced.returncode == 0, forced.stderr


def test_installer_rejects_a_missing_target(tmp_path: Path):
    out = subprocess.run(["bash", str(INSTALLER), str(tmp_path / "nope")],
                         capture_output=True, text=True)
    assert out.returncode == 1
    assert "not found" in out.stderr


def test_init_after_install_produces_a_wellformed_project(installed_project: Path):
    scripts = installed_project / ".claude" / "skills" / "monitor" / "scripts"
    subprocess.run(["git", "init", "-q"], cwd=installed_project, check=True)
    # /monitor:init's engine steps: seed the profile, then build the pages.
    for script in ("profile.py", "render_report.py", "render_logs.py"):
        out = subprocess.run([sys.executable, str(scripts / script),
                              "--project-root", str(installed_project)],
                             capture_output=True, text=True)
        assert out.returncode == 0, out.stderr

    profile_path = installed_project / "monitor" / "profile.json"
    assert profile_path.is_file()
    profile = json.loads(profile_path.read_text())
    assert profile["project"]["name"] == "scratch"
    assert profile["profileVersion"] >= 1
    assert isinstance(profile["kpis"], list)

    dashboard = (installed_project / "monitor" / "index.html").read_text()
    assert dashboard.lstrip().lower().startswith("<!doctype html>")
    assert dashboard.count("<html") == 1
    assert "</html>" in dashboard
    assert "scratch" in dashboard
    assert "http://" not in dashboard and "https://" not in dashboard  # self-contained
    for page in ("reports/index.html", "reports/template.html", "logs/index.html",
                 "tasks/index.html"):
        assert (installed_project / "monitor" / page).is_file()
