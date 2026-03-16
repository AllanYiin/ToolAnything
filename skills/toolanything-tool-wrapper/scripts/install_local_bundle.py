#!/usr/bin/env python3
"""Install the local ToolAnything bundle for Codex, OpenClaw, or Claude Code."""

from __future__ import annotations

import argparse
import locale
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


SKILL_NAME = "toolanything-tool-wrapper"
CLAUDE_AGENT_NAME = f"{SKILL_NAME}.md"
CLAUDE_DESCRIPTION = (
    "Use this subagent when ToolAnything must be installed or refreshed from the bundled "
    "local wheel before wrapping Python callables, HTTP/SQL/model sources, or validating "
    "MCP and OpenAI tool calling."
)
AGENTS_BLOCK_START = "<!-- toolanything-tool-wrapper:BEGIN -->"
AGENTS_BLOCK_END = "<!-- toolanything-tool-wrapper:END -->"
AGENTS_HEADING = "## ToolAnything tool wrapper"
AGENTS_INSTRUCTIONS = {
    "en": (
        "Before executing each task step, think about whether any tool or skill applies. "
        "If the task needs a tool but no suitable tool can solve it, load the skill: "
        "ToolAnything tool wrapper (`toolanything-tool-wrapper`)."
    ),
    "zh-TW": (
        "執行每個任務步驟前，先思考是否有適合的工具或 skill；若任務需要工具，但目前沒有適合工具可解決，"
        "則載入 skill: ToolAnything tool wrapper（`toolanything-tool-wrapper`）。"
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


def read_skill_body(skill_md_path: Path) -> str:
    content = skill_md_path.read_text(encoding="utf-8")
    match = re.match(r"^---\n.*?\n---\n?", content, re.DOTALL)
    if not match:
        raise SystemExit("SKILL.md frontmatter 格式錯誤，無法生成 Claude Code subagent。")
    return content[match.end() :]


def render_claude_agent(skill_path: Path) -> str:
    body = read_skill_body(skill_path / "SKILL.md").rstrip() + "\n"
    return (
        "---\n"
        f"name: {SKILL_NAME}\n"
        f"description: {CLAUDE_DESCRIPTION}\n"
        "---\n\n"
        f"{body}"
    )


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
        f"{AGENTS_BLOCK_START}\n"
        f"{AGENTS_HEADING}\n"
        f"{instruction}\n"
        f"{AGENTS_BLOCK_END}\n"
    )


def upsert_agents_content(
    existing_content: str,
    *,
    locale_hint: str | None = None,
) -> tuple[str, str]:
    language = resolve_agents_language(existing_content, locale_hint)
    block = render_agents_block(language)
    pattern = re.compile(
        rf"{re.escape(AGENTS_BLOCK_START)}.*?{re.escape(AGENTS_BLOCK_END)}\n?",
        re.DOTALL,
    )
    if pattern.search(existing_content):
        updated = pattern.sub(block, existing_content)
        return updated.rstrip() + "\n", language

    if existing_content.strip():
        updated = existing_content.rstrip() + "\n\n" + block
        return updated, language

    updated = "# AGENTS\n\n" + block
    return updated, language


def codex_target(home: Path) -> Path:
    codex_home = Path(os.environ.get("CODEX_HOME", home / ".codex")).expanduser()
    return codex_home / "skills" / SKILL_NAME


def openclaw_target(home: Path) -> Path:
    workspace = Path(
        os.environ.get("OPENCLAW_WORKSPACE", home / ".openclaw" / "workspace")
    ).expanduser()
    return workspace / "skills" / SKILL_NAME


def claude_target(home: Path) -> Path:
    return home / ".claude" / "agents" / CLAUDE_AGENT_NAME


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


def sync_bundle(skill_path: Path, host: str, home: Path, dry_run: bool) -> Path:
    if host == "codex":
        target = codex_target(home)
        copy_skill_tree(skill_path, target, dry_run)
        return target

    if host == "openclaw":
        target = openclaw_target(home)
        copy_skill_tree(skill_path, target, dry_run)
        return target

    if host == "claude-code":
        target = claude_target(home)
        write_text(target, render_claude_agent(skill_path), dry_run)
        return target

    raise SystemExit(f"不支援的 host: {host}")


def print_post_install_hint(host: str, target: Path) -> None:
    print(f"Host: {host}")
    print(f"Installed bundle target: {target}")
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
    target = sync_bundle(skill_path, host, home, args.dry_run)
    agents_path = sync_agents_instruction(home, host, args.dry_run)
    print_post_install_hint(host, target)
    print(f"Updated AGENTS.md: {agents_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
