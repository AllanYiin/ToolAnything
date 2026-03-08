import importlib
import json
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

from toolanything.inspector.service import MCPInspectorService
from toolanything.server.mcp_tool_server import _build_handler


def _start_http_server(registry):
    handler_cls = _build_handler(registry, host="127.0.0.1", port=0)
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler_cls)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def test_opencv_example_exposes_tools_and_accepts_inspector_calls():
    module = importlib.import_module("examples.opencv_mcp_web.server")
    server, thread = _start_http_server(module.registry)
    port = server.server_address[1]
    service = MCPInspectorService(default_timeout=8.0)

    try:
        tools_result = service.list_tools({"mode": "http", "url": f"http://127.0.0.1:{port}"})
        tool_names = [tool["name"] for tool in tools_result["tools"]]
        assert "opencv.info" in tool_names
        assert "opencv.resize" in tool_names
        assert "opencv.canny" in tool_names

        image_base64 = module.build_demo_image_base64()
        info_result = service.call_tool(
            {"mode": "http", "url": f"http://127.0.0.1:{port}"},
            name="opencv.info",
            arguments={"image_base64": image_base64},
        )
        payload = info_result["result"]
        parsed = json.loads(payload["content"][0]["text"])
        assert parsed["width"] == 320
        assert parsed["height"] == 200

        resize_result = service.call_tool(
            {"mode": "http", "url": f"http://127.0.0.1:{port}"},
            name="opencv.resize",
            arguments={"image_base64": image_base64, "target_width": 100},
        )
        resize_payload = json.loads(resize_result["result"]["content"][0]["text"])
        assert resize_payload["width"] == 100
        assert resize_payload["image_base64"].startswith("data:image/png;base64,")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def test_opencv_example_web_ui_mentions_demo_image_and_connection_flow():
    html = Path("examples/opencv_mcp_web/web/index.html").read_text(encoding="utf-8")
    assert "使用示範圖片" in html
    assert "MCP Server URL" in html
    assert "工具列表" in html
