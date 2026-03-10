"""Demonstrate the OpenCV example serving MCP and OpenAI tool calling together."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import threading
from http.server import ThreadingHTTPServer
from typing import Any

from toolanything.adapters import OpenAIAdapter
from toolanything.inspector.service import MCPInspectorService
from toolanything.server.mcp_tool_server import _build_handler

from .server import build_demo_image_base64, registry


def build_protocol_summary() -> dict[str, Any]:
    """Return the tool names exported through MCP and OpenAI adapters."""

    mcp_tools = registry.to_mcp_tools()
    openai_tools = OpenAIAdapter(registry).to_schema()
    mcp_names = sorted(tool["name"] for tool in mcp_tools)
    openai_names = sorted(tool["function"]["name"] for tool in openai_tools)
    return {
        "mcp_tools": mcp_tools,
        "openai_tools": openai_tools,
        "mcp_names": mcp_names,
        "openai_names": openai_names,
        "shared_names": sorted(set(mcp_names) & set(openai_names)),
    }


async def run_local_openai_roundtrip() -> dict[str, Any]:
    """Run a local OpenAI-style tool_call payload through the same registry."""

    adapter = OpenAIAdapter(registry)
    image_base64 = build_demo_image_base64(width=64, height=40)
    tool_call = adapter.to_function_call("opencv.info", {"image_base64": image_base64})
    invocation = await adapter.to_invocation(
        "opencv.info",
        tool_call["function"]["arguments"],
        tool_call_id="opencv_info_local_demo",
    )
    return {
        "tool_call": tool_call,
        "invocation": invocation,
        "parsed_content": json.loads(invocation["content"]),
    }


def build_live_openai_prompt(image_base64: str) -> str:
    """Build a deterministic prompt for a real OpenAI tool-calling roundtrip."""

    arguments = {"image_base64": image_base64}
    return (
        "請只做一件事：呼叫 opencv.info 一次。"
        "不要自己猜圖片資訊，也不要改動參數鍵名。"
        "請直接使用以下 JSON 當作工具參數：\n"
        f"{json.dumps(arguments, ensure_ascii=False)}"
    )


def _start_local_mcp_http_server() -> tuple[ThreadingHTTPServer, threading.Thread]:
    handler_cls = _build_handler(registry, host="127.0.0.1", port=0)
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler_cls)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def run_live_openai_roundtrip(
    *,
    api_key: str | None = None,
    model: str,
    temperature: float = 0.0,
    max_rounds: int = 3,
) -> dict[str, Any]:
    """Run a real OpenAI tool loop against the local MCP server."""

    server, thread = _start_local_mcp_http_server()
    port = server.server_address[1]
    base_url = f"http://127.0.0.1:{port}"
    service = MCPInspectorService(default_timeout=20.0)
    prompt = build_live_openai_prompt(build_demo_image_base64(width=64, height=40))
    previous_api_key = os.getenv("OPENAI_API_KEY")

    if api_key:
        os.environ["OPENAI_API_KEY"] = api_key

    try:
        result = service.run_openai_test(
            {"mode": "http", "url": base_url},
            model=model,
            prompt=prompt,
            system_prompt="如果工具可以回答，就優先使用工具，不要自己推測。",
            temperature=temperature,
            max_rounds=max_rounds,
        )
        return {
            "server_url": base_url,
            "result": result,
        }
    finally:
        if api_key:
            if previous_api_key is None:
                os.environ.pop("OPENAI_API_KEY", None)
            else:
                os.environ["OPENAI_API_KEY"] = previous_api_key
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="OpenCV MCP + OpenAI tool calling 雙協議示範")
    parser.add_argument(
        "--mode",
        choices=("local", "live-openai"),
        default="local",
        help="local 只做本地 tool_call roundtrip；live-openai 會真的呼叫 OpenAI API",
    )
    parser.add_argument("--model", default="", help="live-openai 模式使用的 OpenAI model")
    parser.add_argument(
        "--api-key",
        default="",
        help="live-openai 模式使用的 OpenAI API key；未提供時改讀 OPENAI_API_KEY",
    )
    parser.add_argument("--temperature", type=float, default=0.0, help="OpenAI 呼叫溫度，預設 0")
    parser.add_argument("--max-rounds", type=int, default=3, help="最多工具回合數，預設 3")
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    summary = build_protocol_summary()
    print("[dual_protocol_demo] 共用工具名稱：")
    print(json.dumps(summary["shared_names"], ensure_ascii=False, indent=2))

    local_result = asyncio.run(run_local_openai_roundtrip())
    print("[dual_protocol_demo] 本地 OpenAI tool_call payload：")
    print(json.dumps(local_result["tool_call"], ensure_ascii=False, indent=2))
    print("[dual_protocol_demo] 本地 tool message 結果：")
    print(json.dumps(local_result["parsed_content"], ensure_ascii=False, indent=2))

    if args.mode == "local":
        return

    api_key = args.api_key or os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        parser.error("live-openai 模式需要 --api-key 或 OPENAI_API_KEY")
    if not args.model:
        parser.error("live-openai 模式需要 --model")

    live_result = run_live_openai_roundtrip(
        api_key=api_key,
        model=args.model,
        temperature=args.temperature,
        max_rounds=args.max_rounds,
    )
    print("[dual_protocol_demo] OpenAI live roundtrip：")
    print(json.dumps(live_result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
