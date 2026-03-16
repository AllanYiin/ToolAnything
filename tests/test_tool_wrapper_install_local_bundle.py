from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = (
    ROOT
    / "skills"
    / "toolanything-tool-wrapper"
    / "scripts"
    / "install_local_bundle.py"
)


def _load_install_script_module():
    spec = importlib.util.spec_from_file_location(
        "toolanything_tool_wrapper_install_local_bundle",
        SCRIPT_PATH,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_upsert_agents_content_uses_zh_tw_for_empty_file():
    module = _load_install_script_module()

    updated, language = module.upsert_agents_content("", locale_hint="zh_TW")

    assert language == "zh-TW"
    assert updated.startswith("# AGENTS\n\n")
    assert module.AGENTS_BLOCK_START in updated
    assert "執行每個任務步驟前" in updated
    assert updated.count(module.AGENTS_BLOCK_START) == 1


def test_upsert_agents_content_replaces_existing_block_without_duplication():
    module = _load_install_script_module()
    existing = (
        "# AGENTS\n\n"
        f"{module.AGENTS_BLOCK_START}\n"
        "old content\n"
        f"{module.AGENTS_BLOCK_END}\n"
    )

    updated, language = module.upsert_agents_content(existing, locale_hint="en_US")

    assert language == "en"
    assert "old content" not in updated
    assert "Before executing each task step" in updated
    assert updated.count(module.AGENTS_BLOCK_START) == 1
    assert updated.count(module.AGENTS_BLOCK_END) == 1


def test_sync_agents_instruction_writes_host_specific_agents_file(tmp_path, monkeypatch):
    module = _load_install_script_module()
    home = tmp_path / "home"
    codex_home = home / ".codex"
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    monkeypatch.setenv("LANG", "zh_TW.UTF-8")

    target = module.sync_agents_instruction(home, "codex", dry_run=False)

    assert target == codex_home / "AGENTS.md"
    content = target.read_text(encoding="utf-8")
    assert "ToolAnything tool wrapper" in content
    assert "執行每個任務步驟前" in content
