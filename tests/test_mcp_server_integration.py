import http.client
import io
import json
import sys
import threading
from http.server import ThreadingHTTPServer
from types import MethodType

import pytest

from toolanything import tool
from toolanything.core.registry import ToolRegistry
from toolanything.exceptions import ToolError
from toolanything.server.mcp_stdio_server import MCPStdioServer
from toolanything.server.mcp_tool_server import _build_handler


@pytest.fixture()
def registry_with_tools():
    registry = ToolRegistry()

    @tool(name="echo", description="Echo message", registry=registry)
    def echo(message: str):
        return {"echo": message}

    @tool(name="fail", description="Failing tool", registry=registry)
    def fail(api_key: str):
        raise ToolError("boom", error_type="bad_request", data={"hint": "nope"})

    @tool(name="explode", description="Unexpected crash", registry=registry)
    def explode():
        raise RuntimeError("crash")

    def execute_tool_stub(self, name: str, *, arguments=None, user_id=None, state_manager=None, failure_log=None):
        arguments = arguments or {}
        if name == "fail":
            raise ToolError("boom", error_type="bad_request", data={"hint": "nope"})
        if name == "explode":
            raise RuntimeError("crash")
        func = self.get(name)
        return func(**arguments)

    registry.execute_tool = MethodType(execute_tool_stub, registry)

    return registry


def start_http_server(registry: ToolRegistry):
    handler_cls = _build_handler(registry)
    server = ThreadingHTTPServer(("localhost", 0), handler_cls)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def test_mcp_http_server_endpoints(registry_with_tools):
    server, thread = start_http_server(registry_with_tools)
    port = server.server_address[1]
    conn = http.client.HTTPConnection("localhost", port, timeout=5)

    try:
        conn.request("GET", "/health")
        resp = conn.getresponse()
        body = json.loads(resp.read())
        assert resp.status == 200
        assert body["status"] == "ok"

        conn.request("GET", "/tools")
        resp = conn.getresponse()
        tools_body = json.loads(resp.read())
        assert resp.status == 200
        assert any(tool["name"] == "echo" for tool in tools_body["tools"])

        payload = json.dumps({"name": "echo", "arguments": {"message": "hi"}})
        conn.request("POST", "/invoke", body=payload, headers={"Content-Type": "application/json"})
        resp = conn.getresponse()
        invoke_body = json.loads(resp.read())
        assert resp.status == 200
        assert invoke_body["result"] == {"contentType": "application/json", "content": {"echo": "hi"}}
        assert invoke_body["audit"]["tool"] == "echo"

        invalid_body = "{bad"
        conn.request("POST", "/invoke", body=invalid_body, headers={"Content-Type": "application/json"})
        resp = conn.getresponse()
        error_body = json.loads(resp.read())
        assert resp.status == 400
        assert error_body["error"] == "invalid_json"

        conn.request("POST", "/invoke", body=json.dumps({"arguments": {}}), headers={"Content-Type": "application/json"})
        resp = conn.getresponse()
        missing_name_body = json.loads(resp.read())
        assert resp.status == 400
        assert missing_name_body["error"] == "missing_name"

        conn.request(
            "POST",
            "/invoke",
            body=json.dumps({"name": "fail", "arguments": {"api_key": "secret"}}),
            headers={"Content-Type": "application/json"},
        )
        resp = conn.getresponse()
        fail_body = json.loads(resp.read())
        assert resp.status == 400
        assert fail_body["error"]["type"] == "bad_request"
        assert fail_body["arguments"]["api_key"] == "***MASKED***"

        conn.request("POST", "/invoke", body=json.dumps({"name": "missing"}), headers={"Content-Type": "application/json"})
        resp = conn.getresponse()
        missing_body = json.loads(resp.read())
        assert resp.status == 500
        assert missing_body["error"]["type"] == "internal_error"
    finally:
        conn.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def test_mcp_stdio_server_flow(monkeypatch, registry_with_tools):
    server = MCPStdioServer(registry_with_tools)

    requests = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "echo", "arguments": {"message": "world"}},
        },
        {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {"name": "fail", "arguments": {"api_key": "top-secret"}},
        },
    ]

    input_data = "\n".join(json.dumps(r, ensure_ascii=False) for r in requests) + "\n"
    fake_stdin = io.StringIO(input_data)
    fake_stdout = io.StringIO()

    monkeypatch.setattr(sys, "stdin", fake_stdin)
    monkeypatch.setattr(sys, "stdout", fake_stdout)

    server.run()

    output_lines = [json.loads(line) for line in fake_stdout.getvalue().strip().splitlines()]
    assert output_lines[0]["result"]["protocolVersion"]
    assert any(tool["name"] == "echo" for tool in output_lines[1]["result"]["tools"])

    success = output_lines[2]["result"]
    assert success["arguments"] == {"message": "world"}
    assert success["meta"]["contentType"] == "application/json"

    fail_response = output_lines[3]["error"]
    assert fail_response["message"] == "bad_request"
    assert fail_response["data"]["arguments"]["api_key"] == "***MASKED***"
