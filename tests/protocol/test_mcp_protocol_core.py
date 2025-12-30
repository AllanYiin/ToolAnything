from __future__ import annotations

from typing import Any, Dict, Sequence

from toolanything.exceptions import ToolError
from toolanything.protocol.mcp_jsonrpc import (
    MCPJSONRPCProtocolCore,
    MCPRequestContext,
    build_notification,
    build_request,
)


class FakeCapabilitiesProvider:
    def __init__(self, payload: Dict[str, Any]) -> None:
        self.payload = payload

    def get_capabilities(self) -> Dict[str, Any]:
        return self.payload


class FakeToolSchemaProvider:
    def __init__(self, tools: Sequence[Dict[str, Any]]) -> None:
        self._tools = list(tools)

    def list_tools(self) -> Sequence[Dict[str, Any]]:
        return list(self._tools)


class FakeToolInvoker:
    def __init__(
        self,
        *,
        result: Dict[str, Any] | None = None,
        raise_error: Exception | None = None,
    ) -> None:
        self._result = result
        self._raise_error = raise_error

    def call_tool(
        self,
        name: str,
        arguments: Dict[str, Any],
        *,
        context: MCPRequestContext,
    ) -> Dict[str, Any]:
        if self._raise_error is not None:
            raise self._raise_error
        assert self._result is not None
        return self._result

    def _mask(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        return {"masked": True, **arguments}

    def _audit(self, name: str, arguments: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        return {"tool": name, "user_id": user_id, "arguments": arguments}


class FakeDeps:
    def __init__(
        self,
        *,
        capabilities: FakeCapabilitiesProvider,
        tools: FakeToolSchemaProvider,
        invoker: FakeToolInvoker,
    ) -> None:
        self.capabilities = capabilities
        self.tools = tools
        self.invoker = invoker


def _make_deps(
    *,
    capabilities: Dict[str, Any] | None = None,
    tools: Sequence[Dict[str, Any]] | None = None,
    invoker: FakeToolInvoker | None = None,
) -> FakeDeps:
    return FakeDeps(
        capabilities=FakeCapabilitiesProvider(capabilities or {"protocolVersion": "2024-01-01"}),
        tools=FakeToolSchemaProvider(tools or []),
        invoker=invoker
        or FakeToolInvoker(
            result={
                "content": [{"type": "text", "text": "ok"}],
                "meta": {"duration_ms": 5},
                "arguments": {},
                "audit": {},
            }
        ),
    )


def test_initialize_returns_capabilities() -> None:
    core = MCPJSONRPCProtocolCore()
    deps = _make_deps(capabilities={"protocolVersion": "2024-02-01", "serverInfo": {"name": "demo"}})
    request = build_request("initialize", "req-1")

    response = core.handle(request, context=MCPRequestContext(user_id="u1"), deps=deps)

    assert response == {
        "jsonrpc": "2.0",
        "id": "req-1",
        "result": {"protocolVersion": "2024-02-01", "serverInfo": {"name": "demo"}},
    }


def test_notifications_initialized_returns_none() -> None:
    core = MCPJSONRPCProtocolCore()
    deps = _make_deps()
    request = build_notification("notifications/initialized", {"ok": True})

    response = core.handle(request, context=MCPRequestContext(user_id="u1"), deps=deps)

    assert response is None


def test_tools_list_returns_schemas() -> None:
    core = MCPJSONRPCProtocolCore()
    tools = [
        {"name": "alpha", "description": "Alpha", "input_schema": {"type": "object"}},
        {"name": "beta", "description": "Beta", "input_schema": {"type": "object"}},
    ]
    deps = _make_deps(tools=tools)
    request = build_request("tools/list", 2)

    response = core.handle(request, context=MCPRequestContext(), deps=deps)

    assert response == {
        "jsonrpc": "2.0",
        "id": 2,
        "result": {"tools": tools},
    }


def test_tools_call_success_returns_result_payload() -> None:
    core = MCPJSONRPCProtocolCore()
    invoker = FakeToolInvoker(
        result={
            "content": [{"type": "text", "text": "done"}],
            "meta": {"tokens": 3},
            "arguments": {"a": 1},
            "audit": {"trace": "ok"},
        }
    )
    deps = _make_deps(invoker=invoker)
    request = build_request("tools/call", "call-1", params={"name": "demo", "arguments": {"a": 1}})

    response = core.handle(request, context=MCPRequestContext(user_id="user-1"), deps=deps)

    assert response == {
        "jsonrpc": "2.0",
        "id": "call-1",
        "result": {
            "content": [{"type": "text", "text": "done"}],
            "meta": {"tokens": 3},
            "arguments": {"a": 1},
            "audit": {"trace": "ok"},
        },
        "raw_result": None,
    }


def test_tools_call_tool_error_returns_structured_error() -> None:
    core = MCPJSONRPCProtocolCore()
    error = ToolError("boom", error_type="tool_failed", data={"reason": "bad input"})
    invoker = FakeToolInvoker(raise_error=error)
    deps = _make_deps(invoker=invoker)
    request = build_request("tools/call", "call-err", params={"name": "demo", "arguments": {"x": "y"}})

    response = core.handle(request, context=MCPRequestContext(user_id="user-9"), deps=deps)

    assert response == {
        "jsonrpc": "2.0",
        "id": "call-err",
        "error": {
            "code": -32001,
            "message": "tool_failed",
            "data": {
                "message": "boom",
                "details": {"reason": "bad input"},
                "arguments": {"masked": True, "x": "y"},
                "audit": {"tool": "demo", "user_id": "user-9", "arguments": {"x": "y"}},
            },
        },
    }


def test_unknown_method_returns_method_not_found() -> None:
    core = MCPJSONRPCProtocolCore()
    deps = _make_deps()
    request = build_request("unknown/method", "req-404")

    response = core.handle(request, context=MCPRequestContext(), deps=deps)

    assert response == {
        "jsonrpc": "2.0",
        "id": "req-404",
        "error": {"code": -32601, "message": "method_not_found"},
    }


def test_golden_initialize_response() -> None:
    core = MCPJSONRPCProtocolCore()
    deps = _make_deps(
        capabilities={
            "protocolVersion": "2024-02-01",
            "serverInfo": {"name": "golden", "version": "1.0.0"},
            "dependencies": [{"name": "toolanything", "version": "0.1.0"}],
        }
    )
    request = {
        "jsonrpc": "2.0",
        "id": "golden-init",
        "method": "initialize",
        "params": {"clientInfo": {"name": "tester", "version": "0.0.1"}},
    }

    response = core.handle(request, context=MCPRequestContext(user_id="golden-user"), deps=deps)

    assert response == {
        "jsonrpc": "2.0",
        "id": "golden-init",
        "result": {
            "protocolVersion": "2024-02-01",
            "serverInfo": {"name": "golden", "version": "1.0.0"},
            "dependencies": [{"name": "toolanything", "version": "0.1.0"}],
        },
    }


def test_golden_tools_call_response() -> None:
    core = MCPJSONRPCProtocolCore()
    invoker = FakeToolInvoker(
        result={
            "content": [{"type": "text", "text": "golden"}],
            "meta": {"latency_ms": 12},
            "arguments": {"query": "hello"},
            "audit": {"trace_id": "trace-1"},
            "raw_result": {"status": "ok"},
        }
    )
    deps = _make_deps(invoker=invoker)
    request = {
        "jsonrpc": "2.0",
        "id": 99,
        "method": "tools/call",
        "params": {"name": "golden_tool", "arguments": {"query": "hello"}},
    }

    response = core.handle(request, context=MCPRequestContext(user_id="golden-user"), deps=deps)

    assert response == {
        "jsonrpc": "2.0",
        "id": 99,
        "result": {
            "content": [{"type": "text", "text": "golden"}],
            "meta": {"latency_ms": 12},
            "arguments": {"query": "hello"},
            "audit": {"trace_id": "trace-1"},
        },
        "raw_result": {"status": "ok"},
    }
