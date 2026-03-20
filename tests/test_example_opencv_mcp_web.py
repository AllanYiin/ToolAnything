import importlib
import json
import os
import subprocess
import sys
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

import numpy as np
import pytest

from toolanything.cli import _build_parser, run_exported_cli
from toolanything.cli_export import load_cli_project
from toolanything.inspector.service import MCPInspectorService
from toolanything.server.mcp_tool_server import _build_handler


def _example_subprocess_env() -> dict[str, str]:
    env = dict(os.environ)
    existing = env.get("PYTHONPATH", "")
    src_path = str(Path.cwd() / "src")
    env["PYTHONPATH"] = src_path if not existing else f"{src_path}{os.pathsep}{existing}"
    return env


def _start_http_server(registry):
    handler_cls = _build_handler(registry, host="127.0.0.1", port=0)
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler_cls)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def _import_opencv_example_module():
    try:
        module = importlib.import_module("examples.opencv_mcp_web.server")
    except Exception as exc:  # pragma: no cover - depends on local OpenCV runtime
        pytest.skip(f"OpenCV runtime unavailable: {exc}")
    required_attrs = [
        "imdecode",
        "imencode",
        "resize",
        "cvtColor",
        "Canny",
        "createCLAHE",
    ]
    missing = [name for name in required_attrs if not hasattr(module.cv2, name)]
    if missing:
        pytest.skip(f"OpenCV runtime incomplete: missing {', '.join(missing)}")
    try:
        module.build_demo_image_base64(width=16, height=16)
    except Exception as exc:  # pragma: no cover - depends on local OpenCV runtime
        pytest.skip(f"OpenCV demo image unavailable: {exc}")
    return module


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
        assert "opencv.demo_image" in tool_names
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
    assert "python examples/opencv_mcp_web/web_server.py" in readme
    assert "python examples/opencv_mcp_web/smoke_test.py" in readme
    assert "python examples/opencv_mcp_web/dual_protocol_demo.py" in readme
    assert "toolanything cli run --module examples/opencv_mcp_web/server.py" in readme
    assert "toolanything cli export --module examples/opencv_mcp_web/server.py" in readme


def test_repo_opencv_example_includes_web_assets():
    content = Path("examples/opencv_mcp_web/web/index.html").read_text(encoding="utf-8")
    assert "使用本機 9091" in content
    assert "使用示範圖片" in content


def test_opencv_dual_protocol_demo_runs_mocked_live_openai_loop(monkeypatch, capsys):
    _import_opencv_example_module()
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

    def fake_request_openai_chat_completion(**kwargs):
        return replies.pop(0)

    monkeypatch.setattr(
        module.OpenAIChatRuntime,
        "request_chat_completion",
        staticmethod(fake_request_openai_chat_completion),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["dual_protocol_demo.py", "--mode", "live-openai", "--model", "gpt-test", "--api-key", "sk-test"],
    )

    module.main()

    captured = capsys.readouterr().out
    assert "[dual_protocol_demo] OpenAI live roundtrip：" in captured
    assert '"transport": "in_process"' in captured
    assert '"name": "opencv.info"' in captured
    assert '"final_text": "完成"' in captured


def test_opencv_dual_protocol_demo_runs_as_direct_file():
    _import_opencv_example_module()
    completed = subprocess.run(
        [sys.executable, "examples/opencv_mcp_web/dual_protocol_demo.py", "--mode", "local"],
        cwd=Path.cwd(),
        env=_example_subprocess_env(),
        capture_output=True,
        text=True,
        check=True,
    )
    assert "[dual_protocol_demo] 共用工具名稱：" in completed.stdout
    assert "opencv.info" in completed.stdout


def test_opencv_server_runs_as_direct_file_help():
    completed = subprocess.run(
        [sys.executable, "examples/opencv_mcp_web/server.py", "--help"],
        cwd=Path.cwd(),
        env=_example_subprocess_env(),
        capture_output=True,
        text=True,
        check=True,
    )
    assert "啟動 OpenCV MCP Web 範例" in completed.stdout


def test_opencv_smoke_test_runs_as_direct_file():
    _import_opencv_example_module()
    completed = subprocess.run(
        [sys.executable, "examples/opencv_mcp_web/smoke_test.py"],
        cwd=Path.cwd(),
        env=_example_subprocess_env(),
        capture_output=True,
        text=True,
        check=True,
    )
    assert "[opencv_mcp_web] Inspector 已接通" in completed.stdout
    assert "opencv.info" in completed.stdout


def test_opencv_example_runs_via_dynamic_cli(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    module = _import_opencv_example_module()
    parser = _build_parser()
    demo_path = tmp_path / "demo.png"
    resized_path = tmp_path / "demo-resized.png"

    args = parser.parse_args(
        [
            "cli",
            "run",
            "--module",
            "examples/opencv_mcp_web/server.py",
            "--",
            "opencv",
            "demo-image",
            "--save-as",
            str(demo_path),
            "--json",
        ]
    )
    with pytest.raises(SystemExit) as exc_info:
        args.func(args)
    assert exc_info.value.code == 0
    demo_payload = json.loads(capsys.readouterr().out)
    assert demo_payload["ok"] is True
    assert Path(demo_payload["result"]["output_path"]).exists()

    args = parser.parse_args(
        [
            "cli",
            "run",
            "--module",
            "examples/opencv_mcp_web/server.py",
            "--",
            "opencv",
            "resize",
            "--input-path",
            str(demo_path),
            "--save-as",
            str(resized_path),
            "--target-width",
            "80",
            "--json",
        ]
    )
    with pytest.raises(SystemExit) as exc_info:
        args.func(args)
    assert exc_info.value.code == 0
    resize_payload = json.loads(capsys.readouterr().out)
    assert resize_payload["ok"] is True
    assert resize_payload["result"]["width"] == 80
    output_image = module.cv2.imread(str(resized_path), module.cv2.IMREAD_UNCHANGED)
    assert output_image is not None
    assert output_image.shape[1] == 80
    assert output_image.shape[0] == resize_payload["result"]["height"]


def test_opencv_example_exports_launcher_and_runs(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    _import_opencv_example_module()
    parser = _build_parser()
    config_path = tmp_path / "opencv-demo.cli.json"
    launcher_path = tmp_path / "opencv-demo.py"
    demo_path = tmp_path / "demo.png"

    args = parser.parse_args(
        [
            "cli",
            "export",
            "--module",
            "examples/opencv_mcp_web/server.py",
            "--config",
            str(config_path),
            "--app-name",
            "opencv-demo",
            "--launcher",
            str(launcher_path),
        ]
    )
    args.func(args)
    export_output = capsys.readouterr().out

    assert "opencv demo-image -> opencv.demo_image" in export_output
    assert config_path.exists()
    assert launcher_path.exists()
    project = load_cli_project(str(config_path))
    assert "opencv.demo_image" in project.tools

    exit_code = run_exported_cli(
        str(config_path),
        ["opencv", "demo-image", "--save-as", str(demo_path), "--json"],
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    payload = json.loads(output)
    assert payload["ok"] is True
    assert Path(payload["result"]["output_path"]).exists()
