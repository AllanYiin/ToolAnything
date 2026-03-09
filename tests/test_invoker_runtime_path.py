from __future__ import annotations

import pytest

from tests.fixtures.sample_tools import registry as sample_registry
from toolanything.adapters.mcp_adapter import MCPAdapter
from toolanything.adapters.openai_adapter import OpenAIAdapter
from toolanything.core.invokers import CallableInvoker
from toolanything.core.registry import ToolRegistry
from toolanything.core.tool_manager import ToolManager


@pytest.mark.asyncio
async def test_registry_exposes_contract_and_invoker_for_tool():
    contract = sample_registry.get_tool_contract("math.add")
    invoker = sample_registry.get_invoker("math.add")

    assert contract.name == "math.add"
    assert isinstance(invoker, CallableInvoker)


@pytest.mark.asyncio
async def test_registry_invoke_tool_async_uses_invoker_runtime_path():
    result = await sample_registry.invoke_tool_async("math.add", arguments={"a": 2, "b": 3})

    assert result == 5


@pytest.mark.asyncio
async def test_tool_manager_invoke_uses_registry_invoke_tool_async(monkeypatch: pytest.MonkeyPatch):
    registry = ToolRegistry()
    manager = ToolManager(registry=registry)
    calls: list[tuple[str, dict[str, int]]] = []

    async def fake_invoke_tool_async(name: str, **kwargs):
        calls.append((name, kwargs["arguments"]))
        return {"ok": True}

    monkeypatch.setattr(registry, "invoke_tool_async", fake_invoke_tool_async)
    result = await manager.invoke("demo.tool", {"value": 1})

    assert result == {"ok": True}
    assert calls == [("demo.tool", {"value": 1})]


@pytest.mark.asyncio
async def test_openai_adapter_uses_registry_invoke_tool_async(monkeypatch: pytest.MonkeyPatch):
    registry = ToolRegistry()
    adapter = OpenAIAdapter(registry)
    calls: list[tuple[str, dict[str, int]]] = []

    async def fake_invoke_tool_async(name: str, **kwargs):
        calls.append((name, kwargs["arguments"]))
        return 7

    monkeypatch.setattr(registry, "invoke_tool_async", fake_invoke_tool_async)
    invocation = await adapter.to_invocation("demo.tool", {"value": 7})

    assert invocation["content"] == "7"
    assert calls == [("demo.tool", {"value": 7})]


@pytest.mark.asyncio
async def test_mcp_adapter_uses_registry_invoke_tool_async(monkeypatch: pytest.MonkeyPatch):
    registry = ToolRegistry()
    adapter = MCPAdapter(registry)
    calls: list[tuple[str, dict[str, int]]] = []

    async def fake_invoke_tool_async(name: str, **kwargs):
        calls.append((name, kwargs["arguments"]))
        return 11

    monkeypatch.setattr(registry, "invoke_tool_async", fake_invoke_tool_async)
    invocation = await adapter.to_invocation("demo.tool", {"value": 11})

    assert invocation["result"] == {"contentType": "text/plain", "content": "11"}
    assert calls == [("demo.tool", {"value": 11})]
