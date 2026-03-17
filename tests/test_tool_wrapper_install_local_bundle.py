from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = (
    ROOT
    / "skills"
    / "toolanything-platform-ops"
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
    assert module.PRIMARY_BLOCK_START in updated
    assert "toolanything-mcp-router" in updated
    assert updated.count(module.PRIMARY_BLOCK_START) == 1


def test_upsert_agents_content_replaces_existing_block_without_duplication():
    module = _load_install_script_module()
    existing = (
        "# AGENTS\n\n"
        f"{module.PRIMARY_BLOCK_START}\n"
        "old content\n"
        f"{module.PRIMARY_BLOCK_END}\n"
    )

    updated, language = module.upsert_agents_content(existing, locale_hint="en_US")

    assert language == "en"
    assert "old content" not in updated
    assert "load the skill: ToolAnything MCP router" in updated
    assert updated.count(module.PRIMARY_BLOCK_START) == 1
    assert updated.count(module.PRIMARY_BLOCK_END) == 1


def test_upsert_agents_content_replaces_legacy_tool_wrapper_block():
    module = _load_install_script_module()
    legacy_start, legacy_end = module.LEGACY_BLOCKS[0]
    existing = (
        "# AGENTS\n\n"
        f"{legacy_start}\n"
        "legacy fallback\n"
        f"{legacy_end}\n"
    )

    updated, language = module.upsert_agents_content(existing, locale_hint="zh_TW")

    assert language == "zh-TW"
    assert "legacy fallback" not in updated
    assert legacy_start not in updated
    assert "toolanything-mcp-router" in updated


def test_sync_agents_instruction_writes_host_specific_agents_file(tmp_path, monkeypatch):
    module = _load_install_script_module()
    home = tmp_path / "home"
    codex_home = home / ".codex"
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    monkeypatch.setenv("LANG", "zh_TW.UTF-8")

    target = module.sync_agents_instruction(home, "codex", dry_run=False)

    assert target == codex_home / "AGENTS.md"
    content = target.read_text(encoding="utf-8")
    assert "ToolAnything MCP Router" in content
    assert "toolanything-platform-ops" in content
