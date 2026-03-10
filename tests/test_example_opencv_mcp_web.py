import asyncio
import importlib
import json
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

import numpy as np
import pytest

from toolanything.inspector.service import MCPInspectorService
from toolanything.server.mcp_tool_server import _build_handler


def _start_http_server(registry):
    handler_cls = _build_handler(registry, host="127.0.0.1", port=0)
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler_cls)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def _import_opencv_example_module():
    try:
        return importlib.import_module("examples.opencv_mcp_web.server")
    except Exception as exc:  # pragma: no cover - depends on local OpenCV runtime
        pytest.skip(f"OpenCV runtime unavailable: {exc}")


def test_opencv_example_exposes_tools_and_accepts_inspector_calls():
    module = _import_opencv_example_module()
    server, thread = _start_http_server(module.registry)
    port = server.server_address[1]
    service = MCPInspectorService(default_timeout=8.0)

    try:
        report = service.test_connection({"mode": "http", "url": f"http://127.0.0.1:{port}"})
        assert report["ok"] is True

        tools_result = service.list_tools({"mode": "http", "url": f"http://127.0.0.1:{port}"})
        tool_names = [tool["name"] for tool in tools_result["tools"]]
        assert "__ping__" in tool_names
        assert "opencv.info" in tool_names
        assert "opencv.resize" in tool_names
        assert "opencv.canny" in tool_names
        assert "opencv.clahe" in tool_names
        assert "opencv.adjust_color" in tool_names

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

        clahe_result = service.call_tool(
            {"mode": "http", "url": f"http://127.0.0.1:{port}"},
            name="opencv.clahe",
            arguments={"image_base64": image_base64, "clip_limit": 2.5, "tile_grid_size": 6},
        )
        clahe_payload = json.loads(clahe_result["result"]["content"][0]["text"])
        assert clahe_payload["image_base64"].startswith("data:image/png;base64,")
        assert clahe_payload["width"] == 320

        adjust_result = service.call_tool(
            {"mode": "http", "url": f"http://127.0.0.1:{port}"},
            name="opencv.adjust_color",
            arguments={
                "image_base64": image_base64,
                "brightness": 18,
                "saturation": 24,
                "hue_shift": 12,
            },
        )
        adjust_payload = json.loads(adjust_result["result"]["content"][0]["text"])
        assert adjust_payload["image_base64"].startswith("data:image/png;base64,")
        original = module._decode_image(image_base64)
        adjusted = module._decode_image(adjust_payload["image_base64"])
        assert not np.array_equal(original, adjusted)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def test_opencv_example_web_ui_mentions_demo_image_and_connection_flow():
    html = Path("examples/opencv_mcp_web/web/index.html").read_text(encoding="utf-8")
    assert "使用示範圖片" in html
    assert "MCP Server URL" in html
    assert "工具列表" in html


def test_repo_opencv_example_readme_uses_external_file_paths():
    readme = Path("examples/opencv_mcp_web/README.md").read_text(encoding="utf-8")
    assert "toolanything serve examples/opencv_mcp_web/server.py" in readme
    assert "python -m examples.opencv_mcp_web.web_server" in readme


def test_repo_opencv_example_includes_web_assets():
    content = Path("examples/opencv_mcp_web/web/index.html").read_text(encoding="utf-8")
    assert "使用本機 9091" in content
    assert "使用示範圖片" in content


def test_opencv_dual_protocol_demo_exports_shared_tools_and_local_roundtrip():
    try:
        module = importlib.import_module("examples.opencv_mcp_web.dual_protocol_demo")
    except Exception as exc:  # pragma: no cover - depends on local OpenCV runtime
        pytest.skip(f"OpenCV runtime unavailable: {exc}")

    summary = module.build_protocol_summary()
    assert "opencv.info" in summary["shared_names"]
    assert summary["mcp_names"] == summary["openai_original_names"]

    roundtrip = asyncio.run(module.run_local_openai_roundtrip())
    assert roundtrip["tool_call"]["function"]["name"] == "opencv_info"
    assert roundtrip["invocation"]["role"] == "tool"
    assert roundtrip["invocation"]["tool_call_id"] == "opencv_info_local_demo"
    assert roundtrip["invocation"]["name"] == "opencv.info"
    assert roundtrip["parsed_content"]["width"] == 64
    assert roundtrip["parsed_content"]["height"] == 40


def test_opencv_dual_protocol_demo_runs_mocked_live_openai_loop(monkeypatch):
    try:
        module = importlib.import_module("examples.opencv_mcp_web.dual_protocol_demo")
    except Exception as exc:  # pragma: no cover - depends on local OpenCV runtime
        pytest.skip(f"OpenCV runtime unavailable: {exc}")

    replies = [
        {
            "content": None,
            "tool_calls": [
                {
                    "id": "call_opencv_info",
                    "type": "function",
                    "function": {
                        "name": "opencv_info",
                        "arguments": json.dumps(
                            {"image_base64": module.build_demo_image_base64(width=64, height=40)},
                            ensure_ascii=False,
                        ),
                    },
                }
            ],
        },
        {"content": "完成", "tool_calls": []},
    ]

    def fake_request_openai_chat_completion(self, **kwargs):
        return replies.pop(0)

    monkeypatch.setattr(
        MCPInspectorService,
        "_request_openai_chat_completion",
        fake_request_openai_chat_completion,
    )

    result = module.run_live_openai_roundtrip(api_key="sk-test", model="gpt-test")
    assert result["server_url"].startswith("http://127.0.0.1:")
    assert result["result"]["final_text"] == "完成"
    assert any(
        entry["role"] == "tool" and entry["name"] == "opencv.info"
        for entry in result["result"]["transcript"]
    )
