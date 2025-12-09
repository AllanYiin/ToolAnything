"""協議轉換的對映與快照測試。"""

import json
from pathlib import Path

from tests.fixtures.sample_tools import registry
from toolanything.adapters.mcp_adapter import MCPAdapter
from toolanything.adapters.openai_adapter import OpenAIAdapter


def _openai_parameter_map() -> dict[str, dict]:
    adapter = OpenAIAdapter(registry)
    tools = adapter.to_schema()
    return {tool["function"]["name"]: tool["function"]["parameters"] for tool in tools}


def _mcp_parameter_map() -> dict[str, dict]:
    adapter = MCPAdapter(registry)
    tools = adapter.to_schema()
    return {tool["name"]: tool["input_schema"] for tool in tools}


def test_adapter_schema_alignment_between_protocols():
    openai_params = _openai_parameter_map()
    mcp_params = _mcp_parameter_map()

    assert set(openai_params.keys()) == set(mcp_params.keys())

    for name, openai_schema in openai_params.items():
        mcp_schema = mcp_params[name]
        assert openai_schema["properties"] == mcp_schema["properties"]
        assert openai_schema["required"] == mcp_schema["required"]


def test_adapter_schema_snapshot(tmp_path):
    openai_adapter = OpenAIAdapter(registry)
    mcp_adapter = MCPAdapter(registry)

    payload = {
        "openai": openai_adapter.to_schema(),
        "mcp": mcp_adapter.to_schema(),
    }

    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2)

    snapshot_path = Path(__file__).parent / "fixtures" / "snapshots" / "adapter_schema.json"
    assert snapshot_path.exists(), "Snapshot 檔案不存在，請先建立 baseline"

    expected = snapshot_path.read_text(encoding="utf-8").strip()
    assert serialized == expected
