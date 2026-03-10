"""Minimal OpenCV example showing MCP export and OpenAI tool calling."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from toolanything import OpenAIChatRuntime

if __package__ in (None, ""):
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

from examples.opencv_mcp_web.server import build_demo_image_base64, registry


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="OpenCV MCP + OpenAI tool calling 極簡示範")
    parser.add_argument("--mode", choices=("local", "live-openai"), default="local")
    parser.add_argument("--model", default="", help="live-openai 模式使用的 OpenAI model")
    parser.add_argument("--api-key", default="", help="未提供時改讀 OPENAI_API_KEY")
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max-rounds", type=int, default=3)
    return parser


def _build_live_prompt(image_base64: str) -> str:
    return (
        "請只做一件事：呼叫 opencv.info 一次。"
        "不要自己猜圖片資訊，也不要改動參數鍵名。"
        "請直接使用以下 JSON 當作工具參數：\n"
        f"{json.dumps({'image_base64': image_base64}, ensure_ascii=False)}"
    )


def main() -> None:
    args = _build_parser().parse_args()
    runtime = OpenAIChatRuntime(registry)

    mcp_names = sorted(tool["name"] for tool in registry.to_mcp_tools())
    openai_original_names = sorted(
        runtime.adapter.from_openai_name(tool["function"]["name"])
        for tool in runtime.to_schema()
    )
    print("[dual_protocol_demo] 共用工具名稱：")
    print(json.dumps(sorted(set(mcp_names) & set(openai_original_names)), ensure_ascii=False, indent=2))

    tool_call = runtime.create_tool_call(
        "opencv.info",
        {"image_base64": build_demo_image_base64(width=64, height=40)},
        tool_call_id="opencv_info_local_demo",
    )
    local_result = runtime.execute_tool_call(tool_call)
    print("[dual_protocol_demo] 本地 OpenAI tool_call payload：")
    print(json.dumps(tool_call, ensure_ascii=False, indent=2))
    print("[dual_protocol_demo] 本地 tool message 結果：")
    print(json.dumps(json.loads(local_result["content"]), ensure_ascii=False, indent=2))

    if args.mode == "local":
        return

    api_key = args.api_key or os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        raise SystemExit("live-openai 模式需要 --api-key 或 OPENAI_API_KEY")
    if not args.model:
        raise SystemExit("live-openai 模式需要 --model")

    live_result = runtime.run(
        api_key=api_key,
        model=args.model,
        prompt=_build_live_prompt(build_demo_image_base64(width=64, height=40)),
        system_prompt="如果工具可以回答，就優先使用工具，不要自己推測。",
        temperature=args.temperature,
        max_rounds=args.max_rounds,
    )
    print("[dual_protocol_demo] OpenAI live roundtrip：")
    print(json.dumps({"transport": "in_process", "result": live_result}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
