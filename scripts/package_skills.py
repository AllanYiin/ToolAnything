#!/usr/bin/env python3
"""Package repo-local skill folders into .skill archives.

Default behavior:
  - Discover skill folders under ./skills
  - Validate each skill minimally
  - Write <skill-name>.skill next to the skill folders under ./skills

Examples:
  python scripts/package_skills.py
  python scripts/package_skills.py toolanything-tool-wrapper
  python scripts/package_skills.py skills/toolanything-tool-wrapper --output-dir dist
"""

from __future__ import annotations

import argparse
import re
import sys
import zipfile
from pathlib import Path

try:
    import yaml
except ModuleNotFoundError:  # pragma: no cover - exercised via fallback parser
    yaml = None


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SKILLS_DIR = REPO_ROOT / "skills"


class FrontmatterParseError(ValueError):
    """Raised when SKILL.md frontmatter cannot be parsed."""


def _parse_scalar(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        return ""
    if len(stripped) >= 2 and stripped[0] == stripped[-1] and stripped[0] in {'"', "'"}:
        return stripped[1:-1]
    return stripped


def _parse_frontmatter_without_yaml(frontmatter_text: str) -> dict[str, object]:
    frontmatter: dict[str, object] = {}
    current_key: str | None = None

    for raw_line in frontmatter_text.splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue

        stripped = raw_line.strip()
        is_indented = raw_line[:1].isspace()
        if is_indented:
            if current_key is None:
                raise FrontmatterParseError(f"Unexpected indentation: {raw_line}")
            container = frontmatter[current_key]
            if stripped.startswith("- "):
                if not isinstance(container, list):
                    frontmatter[current_key] = []
                    container = frontmatter[current_key]
                container.append(_parse_scalar(stripped[2:]))
                continue
            if ":" not in stripped:
                raise FrontmatterParseError(f"Invalid nested line: {raw_line}")
            if not isinstance(container, dict):
                frontmatter[current_key] = {}
                container = frontmatter[current_key]
            nested_key, nested_value = stripped.split(":", 1)
            container[nested_key.strip()] = _parse_scalar(nested_value)
            continue

        current_key = None
        if ":" not in stripped:
            raise FrontmatterParseError(f"Invalid frontmatter line: {raw_line}")

        key, raw_value = stripped.split(":", 1)
        key = key.strip()
        value = raw_value.strip()
        if not key:
            raise FrontmatterParseError(f"Missing key in line: {raw_line}")
        if value:
            frontmatter[key] = _parse_scalar(value)
            continue

        current_key = key
        frontmatter[key] = {}

    return frontmatter


def _load_frontmatter(frontmatter_text: str) -> dict[str, object]:
    if yaml is not None:
        frontmatter = yaml.safe_load(frontmatter_text)
    else:
        frontmatter = _parse_frontmatter_without_yaml(frontmatter_text)

    if not isinstance(frontmatter, dict):
        raise FrontmatterParseError("Frontmatter must be a YAML dictionary")
    return frontmatter


def validate_skill_dir(skill_dir: Path) -> tuple[bool, str]:
    """Run the minimum checks needed before packaging a skill folder."""

    if not skill_dir.exists():
        return False, f"skill folder not found: {skill_dir}"
    if not skill_dir.is_dir():
        return False, f"path is not a directory: {skill_dir}"

    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        return False, f"SKILL.md not found in {skill_dir}"

    try:
        content = skill_md.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        return False, f"SKILL.md must be valid UTF-8: {exc}"

    if not content.startswith("---"):
        return False, "SKILL.md is missing YAML frontmatter"

    match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return False, "SKILL.md has invalid YAML frontmatter delimiters"

    try:
        frontmatter = _load_frontmatter(match.group(1))
    except Exception as exc:  # pragma: no cover - exercised in subprocess validation paths
        return False, f"failed to parse frontmatter: {exc}"

    name = frontmatter.get("name")
    description = frontmatter.get("description")
    if not isinstance(name, str) or not name.strip():
        return False, "frontmatter.name is required"
    if not isinstance(description, str) or not description.strip():
        return False, "frontmatter.description is required"
    if name.strip() != skill_dir.name:
        return False, (
            f"frontmatter.name '{name.strip()}' does not match folder name '{skill_dir.name}'"
        )

    return True, "valid"


def _should_exclude(file_path: Path) -> bool:
    parts = set(file_path.parts)
    if "__pycache__" in parts:
        return True
    if file_path.suffix == ".pyc":
        return True
    if file_path.suffix == ".skill":
        return True
    if file_path.name in {".DS_Store"}:
        return True
    return False


def package_skill(skill_dir: Path, output_dir: Path) -> Path:
    """Package a single skill folder into output_dir."""

    skill_filename = output_dir / f"{skill_dir.name}.skill"
    with zipfile.ZipFile(skill_filename, "w", zipfile.ZIP_DEFLATED) as archive:
        for file_path in sorted(skill_dir.rglob("*")):
            if not file_path.is_file() or _should_exclude(file_path):
                continue
            archive.write(file_path, file_path.relative_to(skill_dir.parent))
    return skill_filename


def discover_skills(skills_dir: Path) -> list[Path]:
    """Return direct child directories that look like skill folders."""

    if not skills_dir.exists():
        return []
    return sorted(
        path
        for path in skills_dir.iterdir()
        if path.is_dir() and (path / "SKILL.md").exists()
    )


def resolve_targets(raw_targets: list[str], skills_dir: Path) -> list[Path]:
    """Resolve CLI targets as either skill names under skills_dir or explicit paths."""

    if not raw_targets:
        return discover_skills(skills_dir)

    resolved: list[Path] = []
    for raw_target in raw_targets:
        explicit_path = Path(raw_target)
        if explicit_path.exists():
            resolved.append(explicit_path.resolve())
            continue

        named_skill = skills_dir / raw_target
        if named_skill.exists():
            resolved.append(named_skill.resolve())
            continue

        raise FileNotFoundError(
            f"skill target '{raw_target}' not found as a path or under {skills_dir}"
        )

    return resolved


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Package repo-local skills into .skill archives"
    )
    parser.add_argument(
        "targets",
        nargs="*",
        help="Skill folder names under ./skills, or explicit skill folder paths. Defaults to all skills.",
    )
    parser.add_argument(
        "--skills-dir",
        default=str(DEFAULT_SKILLS_DIR),
        help="Directory that contains skill folders. Defaults to ./skills.",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Directory for .skill archives. Defaults to --skills-dir.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    skills_dir = Path(args.skills_dir).resolve()
    output_dir = Path(args.output_dir).resolve() if args.output_dir else skills_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        targets = resolve_targets(args.targets, skills_dir)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}")
        return 1

    if not targets:
        print(f"ERROR: no skill folders found under {skills_dir}")
        return 1

    failures = 0
    for skill_dir in targets:
        valid, message = validate_skill_dir(skill_dir)
        if not valid:
            print(f"ERROR: {skill_dir.name}: {message}")
            failures += 1
            continue

        archive_path = package_skill(skill_dir, output_dir)
        print(f"PACKAGED: {skill_dir.name} -> {archive_path}")

    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
