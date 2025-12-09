"""簡易 MCP Tool Server 健康檢查工具。"""

from __future__ import annotations

import json
import time
from typing import Any

import requests


def check_server(url: str = "http://localhost:9090/tools") -> bool:
    """檢查指定 URL 是否回應可用的工具列表。

    Args:
        url: MCP Tool Server 的工具列舉端點。

    Returns:
        若回傳 200 並成功解析 JSON 則為 ``True``，否則為 ``False``。
    """

    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            print("Server is running!")
            print("Tools available:")
            parsed: Any = response.json()
            print(json.dumps(parsed, indent=2, ensure_ascii=False))
            return True

        print(f"Server returned status code: {response.status_code}")
        return False
    except Exception as exc:
        print(f"Failed to connect to server: {exc}")
        return False


if __name__ == "__main__":
    # Wait a bit for server to start
    time.sleep(2)
    check_server()
