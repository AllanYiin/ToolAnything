import json
import sys
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

from fastapi.testclient import TestClient

from toolanything import tool
from toolanything.core.registry import ToolRegistry
from toolanything.inspector.app import create_app
from toolanything.inspector.service import MCPInspectorService
from toolanything.server.mcp_tool_server import _build_handler


def _start_http_server(registry: ToolRegistry):
    handler_cls = _build_handler(registry, host="127.0.0.1", port=0)
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler_cls)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def _build_stdio_command() -> str:
    src_dir = Path(__file__).resolve().parents[1] / "src"
    escaped_src = str(src_dir).replace("\\", "\\\\")
    script = (
        "import sys; "
        f"sys.path.insert(0, r'{escaped_src}'); "
        "from toolanything.core.doctor_server import main; "
        "sys.argv=['toolanything-doctor-server','--tools','examples.quickstart.tools']; "
        "main()"
    )
    return f'"{sys.executable}" -c "{script}"'


def test_inspector_service_lists_and_calls_http_tools():
    registry = ToolRegistry()

    @tool(name="ping", description="Ping", registry=registry)
    def ping():
        return {"pong": True}

    @tool(name="echo", description="Echo message", registry=registry)
    def echo(message: str):
        return {"echo": message}

    server, thread = _start_http_server(registry)
    port = server.server_address[1]
    service = MCPInspectorService()

    try:
        payload = {"mode": "http", "url": f"http://127.0.0.1:{port}"}
        tools_result = service.list_tools(payload)
        assert tools_result["count"] == 2
        assert any(tool["name"] == "echo" for tool in tools_result["tools"])
        assert any(entry["kind"] == "request" for entry in tools_result["trace"])
        assert any(entry["kind"] == "response" for entry in tools_result["trace"])

        call_result = service.call_tool(payload, name="echo", arguments={"message": "hi"})
        assert call_result["result"]["meta"]["contentType"] == "application/json"
        content = call_result["result"]["content"][0]
        assert content["type"] == "text"
        assert json.loads(content["text"]) == {"echo": "hi"}
        assert any(
            entry["payload"].get("method") == "tools/call"
            for entry in call_result["trace"]
            if entry["direction"] == "outbound"
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def test_inspector_service_supports_stdio_tools():
    service = MCPInspectorService(default_timeout=5.0)
    payload = {
        "mode": "stdio",
        "command": _build_stdio_command(),
        "timeout": 5.0,
    }

    tools_result = service.list_tools(payload)
    assert tools_result["count"] >= 1
    assert any(tool["name"] == "__ping__" for tool in tools_result["tools"])

    call_result = service.call_tool(payload, name="__ping__", arguments={})
    assert json.loads(call_result["result"]["content"][0]["text"]) == {"ok": True, "message": "pong"}
    assert any(entry["kind"] == "notification" for entry in call_result["trace"])


def test_inspector_service_runs_mocked_openai_tool_loop():
    registry = ToolRegistry()

    @tool(name="echo", description="Echo message", registry=registry)
    def echo(message: str):
        return {"echo": message}

    server, thread = _start_http_server(registry)
    port = server.server_address[1]
    service = MCPInspectorService()

    replies = [
        {
            "content": None,
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {
                        "name": "echo",
                        "arguments": json.dumps({"message": "hello"}, ensure_ascii=False),
                    },
                }
            ],
        },
        {"content": "完成", "tool_calls": []},
    ]

    def fake_request_openai_chat_completion(**kwargs):
        return replies.pop(0)

    service._request_openai_chat_completion = fake_request_openai_chat_completion  # type: ignore[method-assign]

    try:
        result = service.run_openai_test(
            {"mode": "http", "url": f"http://127.0.0.1:{port}"},
            api_key="sk-test",
            model="gpt-test",
            prompt="請呼叫 echo",
        )
        assert result["final_text"] == "完成"
        assert any(entry["role"] == "tool" and entry["name"] == "echo" for entry in result["transcript"])
        assert any(
            entry["payload"].get("method") == "tools/call"
            for entry in result["trace"]
            if entry["direction"] == "outbound"
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def test_inspector_app_tools_endpoints():
    registry = ToolRegistry()

    @tool(name="ping", description="Ping", registry=registry)
    def ping():
        return {"pong": True}

    @tool(name="echo", description="Echo message", registry=registry)
    def echo(message: str):
        return {"echo": message}

    server, thread = _start_http_server(registry)
    port = server.server_address[1]
    client = TestClient(create_app())

    try:
        response = client.get("/")
        assert response.status_code == 200
        assert "MCP Test Client" in response.text

        response = client.post(
            "/api/connection/test",
            json={"connection": {"mode": "http", "url": f"http://127.0.0.1:{port}"}},
        )
        assert response.status_code == 200
        assert response.json()["ok"] is True

        response = client.post(
            "/api/tools/list",
            json={"connection": {"mode": "http", "url": f"http://127.0.0.1:{port}"}},
        )
        assert response.status_code == 200
        assert response.json()["count"] == 2
        assert response.json()["trace"]

        response = client.post(
            "/api/tools/call",
            json={
                "connection": {"mode": "http", "url": f"http://127.0.0.1:{port}"},
                "name": "echo",
                "arguments": {"message": "from-app"},
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert json.loads(payload["result"]["content"][0]["text"]) == {"echo": "from-app"}
        assert payload["trace"]
    finally:
        client.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
