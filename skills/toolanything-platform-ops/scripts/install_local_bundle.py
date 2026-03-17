#!/usr/bin/env python3
"""Install the local ToolAnything skill bundle for Codex, OpenClaw, or Claude Code."""

from __future__ import annotations

import argparse
import json
import locale
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


BUNDLE_SKILL_NAMES = (
    "toolanything-mcp-router",
    "toolanything-platform-ops",
    "toolanything-tool-wrapper",
)
PRIMARY_SKILL_NAME = "toolanything-mcp-router"
PRIMARY_BLOCK_START = "<!-- toolanything-mcp-router:BEGIN -->"
PRIMARY_BLOCK_END = "<!-- toolanything-mcp-router:END -->"
LEGACY_BLOCKS = (
    ("<!-- toolanything-tool-wrapper:BEGIN -->", "<!-- toolanything-tool-wrapper:END -->"),
)
AGENTS_HEADING = "## ToolAnything MCP Router"
AGENTS_INSTRUCTIONS = {
    "en": (
        "When a task involves creating, wrapping, extending, or validating reusable MCP/OpenAI "
        "tools, or when the tool source is a Python function, class method, HTTP API, SQL query, "
        "or model inference, load the skill: ToolAnything MCP router "
        "(`toolanything-mcp-router`) first.\n"
        "FastMCP or another smaller solution is acceptable only when all of the following are true:\n"
        "1. the result is a throwaway prototype;\n"
        "2. MCP-only is needed;\n"
        "3. the source is a single local Python callable;\n"
        "4. no doctor / inspect / CLI / shared server / source-based API is needed.\n"
        "If the task moves into local bundle installation, shared server setup, host sync, or "
        "auto-start, load the skill: ToolAnything platform ops (`toolanything-platform-ops`)."
    ),
    "zh-TW": (
        "當任務涉及建立、包裝、擴充或驗證可重用的 MCP/OpenAI tool，或工具來源是 Python "
        "function、class method、HTTP API、SQL、model inference 時，先載入 skill: "
        "ToolAnything MCP router（`toolanything-mcp-router`）。\n"
        "只有在以下條件同時成立時，才可優先改用 FastMCP 或其他更小方案：\n"
        "1. 需求是一次性原型；\n"
        "2. 只需要 MCP，不需要 OpenAI tool calling；\n"
        "3. 來源是單一本地 Python callable；\n"
        "4. 不需要 doctor / inspect / CLI / shared server / source-based API。\n"
        "若任務進入本地 bundle 安裝、shared server、host 同步或自動啟動，改載入 skill: "
        "ToolAnything platform ops（`toolanything-platform-ops`）。"
    ),
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Install the local ToolAnything skill bundle for the current host."
    )
    parser.add_argument(
        "--host",
        default="auto",
        choices=("auto", "codex", "openclaw", "claude-code"),
        help="Host to target. Defaults to auto detection.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the detected actions without changing the environment.",
    )
    return parser


def home_dir() -> Path:
    return Path.home()


def skill_dir() -> Path:
    return Path(__file__).resolve().parents[1]


def repo_root(skill_path: Path) -> Path:
    return skill_path.parent.parent


def bundle_skill_dirs(skill_path: Path) -> list[Path]:
    skills_root = repo_root(skill_path) / "skills"
    resolved: list[Path] = []
    for skill_name in BUNDLE_SKILL_NAMES:
        candidate = skills_root / skill_name
        if candidate.exists():
            resolved.append(candidate)
    return resolved


def detect_hosts(home: Path) -> list[str]:
    candidates: list[str] = []

    codex_home = os.environ.get("CODEX_HOME")
    if codex_home or (home / ".codex").exists():
        candidates.append("codex")

    if os.environ.get("OPENCLAW_WORKSPACE") or (home / ".openclaw").exists():
        candidates.append("openclaw")

    if (home / ".claude").exists():
        candidates.append("claude-code")

    return candidates


def choose_host(requested_host: str, home: Path) -> str:
    if requested_host != "auto":
        return requested_host

    candidates = detect_hosts(home)
    if not candidates:
        raise SystemExit(
            "無法自動判斷 host。請改用 --host codex、--host openclaw 或 --host claude-code。"
        )
    if len(candidates) > 1:
        joined = ", ".join(candidates)
        raise SystemExit(f"偵測到多個 host 候選：{joined}。請用 --host 明確指定。")
    return candidates[0]


def wheel_candidates(skill_path: Path) -> list[Path]:
    repo_path = repo_root(skill_path)
    candidates: list[Path] = []
    for relative in ("wheels", "wheel"):
        folder = skill_path / relative
        if folder.exists():
            candidates.extend(sorted(folder.glob("toolanything-*.whl")))
    dist_folder = repo_path / "dist"
    if dist_folder.exists():
        candidates.extend(sorted(dist_folder.glob("toolanything-*.whl")))
    return candidates


def pick_latest_wheel(skill_path: Path) -> Path:
    candidates = wheel_candidates(skill_path)
    if not candidates:
        raise SystemExit(
            "找不到 ToolAnything wheel。請先把 toolanything-*.whl 放進 wheels/，"
            "或在 repo dist/ 內產生 wheel。"
        )
    return max(candidates, key=lambda path: path.stat().st_mtime)


def pip_install(wheel_path: Path, dry_run: bool) -> None:
    command = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--upgrade",
        "--force-reinstall",
        str(wheel_path),
    ]
    print("Installing wheel:")
    print(" ".join(command))
    if dry_run:
        return
    subprocess.run(command, check=True)


def copy_skill_tree(source: Path, target: Path, dry_run: bool) -> None:
    print(f"Syncing skill folder: {source} -> {target}")
    try:
        if source.resolve() == target.resolve():
            print("Source and target are the same path; skipping folder sync.")
            return
    except FileNotFoundError:
        pass
    if dry_run:
        return
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(
        source,
        target,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.skill"),
    )


def read_skill_markdown(skill_md_path: Path) -> tuple[str, str, str]:
    content = skill_md_path.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n?(.*)$", content, re.DOTALL)
    if not match:
        raise SystemExit("SKILL.md frontmatter 格式錯誤，無法生成 Claude Code skill。")
    frontmatter = match.group(1)
    body = match.group(2).rstrip() + "\n"

    name_match = re.search(r"^name:\s*(.+)$", frontmatter, re.MULTILINE)
    description_match = re.search(r"^description:\s*(.+)$", frontmatter, re.MULTILINE)
    if not name_match or not description_match:
        raise SystemExit("SKILL.md frontmatter 缺少 name 或 description。")

    name = name_match.group(1).strip().strip("'\"")
    description = description_match.group(1).strip().strip("'\"")
    return name, description, body


def render_claude_skill(skill_path: Path) -> tuple[str, str]:
    name, description, body = read_skill_markdown(skill_path / "SKILL.md")
    rendered = (
        "---\n"
        f"name: {name}\n"
        f"description: {json.dumps(description, ensure_ascii=False)}\n"
        "---\n\n"
        f"{body}"
    )
    return name, rendered


def write_text(target: Path, content: str, dry_run: bool) -> None:
    print(f"Writing file: {target}")
    if dry_run:
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def preferred_language_hint() -> str | None:
    for key in ("LC_ALL", "LC_MESSAGES", "LANG"):
        value = os.environ.get(key)
        if value:
            return value

    language, _ = locale.getlocale()
    return language


def contains_cjk(text: str) -> bool:
    return bool(re.search(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]", text))


def resolve_agents_language(existing_content: str, locale_hint: str | None = None) -> str:
    if contains_cjk(existing_content):
        return "zh-TW"
    if locale_hint and locale_hint.lower().startswith("zh"):
        return "zh-TW"
    return "en"


def render_agents_block(language: str) -> str:
    instruction = AGENTS_INSTRUCTIONS["zh-TW" if language == "zh-TW" else "en"]
    return (
        f"{PRIMARY_BLOCK_START}\n"
        f"{AGENTS_HEADING}\n"
        f"{instruction}\n"
        f"{PRIMARY_BLOCK_END}\n"
    )


def _remove_block(content: str, start_marker: str, end_marker: str) -> str:
    pattern = re.compile(
        rf"{re.escape(start_marker)}.*?{re.escape(end_marker)}\n?",
        re.DOTALL,
    )
    return pattern.sub("", content)


def upsert_agents_content(
    existing_content: str,
    *,
    locale_hint: str | None = None,
) -> tuple[str, str]:
    language = resolve_agents_language(existing_content, locale_hint)
    normalized = existing_content
    for start_marker, end_marker in LEGACY_BLOCKS:
        normalized = _remove_block(normalized, start_marker, end_marker)
    normalized = _remove_block(normalized, PRIMARY_BLOCK_START, PRIMARY_BLOCK_END)
    normalized = normalized.rstrip()

    block = render_agents_block(language)
    if normalized:
        updated = normalized + "\n\n" + block
        return updated, language

    updated = "# AGENTS\n\n" + block
    return updated, language


def codex_skills_root(home: Path) -> Path:
    codex_home = Path(os.environ.get("CODEX_HOME", home / ".codex")).expanduser()
    return codex_home / "skills"


def openclaw_skills_root(home: Path) -> Path:
    workspace = Path(
        os.environ.get("OPENCLAW_WORKSPACE", home / ".openclaw" / "workspace")
    ).expanduser()
    return workspace / "skills"


def claude_skills_root(home: Path) -> Path:
    return home / ".claude" / "skills"


def agents_target(home: Path, host: str) -> Path:
    if host == "codex":
        codex_home = Path(os.environ.get("CODEX_HOME", home / ".codex")).expanduser()
        return codex_home / "AGENTS.md"

    if host == "openclaw":
        workspace = Path(
            os.environ.get("OPENCLAW_WORKSPACE", home / ".openclaw" / "workspace")
        ).expanduser()
        return workspace / "AGENTS.md"

    if host == "claude-code":
        return home / ".claude" / "AGENTS.md"

    raise SystemExit(f"不支援的 host: {host}")


def sync_agents_instruction(home: Path, host: str, dry_run: bool) -> Path:
    target = agents_target(home, host)
    existing_content = target.read_text(encoding="utf-8") if target.exists() else ""
    updated_content, language = upsert_agents_content(
        existing_content,
        locale_hint=preferred_language_hint(),
    )

    print(f"Updating AGENTS.md instruction ({language}): {target}")
    if not dry_run:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(updated_content, encoding="utf-8")
    return target


def sync_bundle(skill_path: Path, host: str, home: Path, dry_run: bool) -> list[Path]:
    skill_dirs = bundle_skill_dirs(skill_path)
    if host == "codex":
        target_root = codex_skills_root(home)
        targets: list[Path] = []
        for source in skill_dirs:
            target = target_root / source.name
            copy_skill_tree(source, target, dry_run)
            targets.append(target)
        return targets

    if host == "openclaw":
        target_root = openclaw_skills_root(home)
        targets = []
        for source in skill_dirs:
            target = target_root / source.name
            copy_skill_tree(source, target, dry_run)
            targets.append(target)
        return targets

    if host == "claude-code":
        target_root = claude_skills_root(home)
        targets = []
        for source in skill_dirs:
            skill_name, rendered = render_claude_skill(source)
            target = target_root / f"{skill_name}.md"
            write_text(target, rendered, dry_run)
            targets.append(target)
        return targets

    raise SystemExit(f"不支援的 host: {host}")


def print_post_install_hint(host: str, targets: list[Path]) -> None:
    print(f"Host: {host}")
    print("Installed bundle targets:")
    for target in targets:
        print(f"- {target}")
    print('Next check: python -c "import toolanything; print(toolanything.__file__)"')


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    home = home_dir()
    skill_path = skill_dir()
    host = choose_host(args.host, home)
    wheel_path = pick_latest_wheel(skill_path)

    print(f"Detected host: {host}")
    print(f"Selected wheel: {wheel_path}")

    pip_install(wheel_path, args.dry_run)
    targets = sync_bundle(skill_path, host, home, args.dry_run)
    agents_path = sync_agents_instruction(home, host, args.dry_run)
    print_post_install_hint(host, targets)
    print(f"Updated AGENTS.md: {agents_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
