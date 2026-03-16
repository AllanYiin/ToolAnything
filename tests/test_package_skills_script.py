from __future__ import annotations

import subprocess
import sys
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "package_skills.py"


def _write_skill(skill_dir: Path, *, name: str) -> None:
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "references").mkdir(exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        (
            "---\n"
            f"name: {name}\n"
            "description: Use when packaging a demo skill.\n"
            "---\n\n"
            "# Demo Skill\n"
        ),
        encoding="utf-8",
    )
    (skill_dir / "references" / "guide.md").write_text(
        "guide\n",
        encoding="utf-8",
    )
    pycache_dir = skill_dir / "__pycache__"
    pycache_dir.mkdir(exist_ok=True)
    (pycache_dir / "ignored.pyc").write_bytes(b"pyc")


def test_package_skills_packages_named_skill_into_skills_dir(tmp_path):
    skills_dir = tmp_path / "skills"
    skill_dir = skills_dir / "demo-skill"
    _write_skill(skill_dir, name="demo-skill")

    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "demo-skill",
            "--skills-dir",
            str(skills_dir),
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    archive_path = skills_dir / "demo-skill.skill"
    assert archive_path.exists()
    with zipfile.ZipFile(archive_path) as archive:
        names = archive.namelist()
    assert "demo-skill/SKILL.md" in names
    assert "demo-skill/references/guide.md" in names
    assert all("__pycache__" not in name for name in names)


def test_package_skills_rejects_name_mismatch(tmp_path):
    skills_dir = tmp_path / "skills"
    skill_dir = skills_dir / "demo-skill"
    _write_skill(skill_dir, name="different-name")

    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "demo-skill",
            "--skills-dir",
            str(skills_dir),
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 1
    assert "does not match folder name" in completed.stdout
