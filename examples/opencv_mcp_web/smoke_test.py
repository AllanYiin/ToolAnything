"""Use the built-in MCP inspector service to verify the repository OpenCV example."""
from __future__ import annotations

import socket
import sys
import threading
import time
from contextlib import closing
from pathlib import Path
from urllib import error as url_error
from urllib import request as url_request

from toolanything.inspector.service import MCPInspectorService

if __package__ in (None, ""):
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

from examples.opencv_mcp_web.server import build_demo_image_base64, start_server


def _find_free_port() -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_server(url: str, timeout: float = 8.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with url_request.urlopen(f"{url}/health", timeout=1.5) as response:
                if response.status == 200:
                    return
        except url_error.URLError:
            time.sleep(0.2)
    raise RuntimeError("OpenCV MCP server 未在預期時間內就緒")


def main() -> None:
    port = _find_free_port()
    base_url = f"http://127.0.0.1:{port}"
    thread = threading.Thread(target=start_server, kwargs={"port": port, "host": "127.0.0.1"}, daemon=True)
    thread.start()
    _wait_for_server(base_url)

    service = MCPInspectorService(default_timeout=8.0)
    tools_result = service.list_tools({"mode": "http", "url": base_url})
    tool_names = [tool["name"] for tool in tools_result["tools"]]

    image_base64 = build_demo_image_base64()
    info_result = service.call_tool(
        {"mode": "http", "url": base_url},
        name="opencv.info",
        arguments={"image_base64": image_base64},
    )

    print("[opencv_mcp_web] Inspector 已接通")
    print(f"[opencv_mcp_web] tools/list: {tool_names}")
    print(f"[opencv_mcp_web] opencv.info result: {info_result['result']}")


if __name__ == "__main__":
    main()
