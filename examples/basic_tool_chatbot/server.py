from __future__ import annotations

import argparse
import json
import sys
import webbrowser
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Mapping, Sequence

from toolanything import (
    OpenAIChatRuntime,
    StandardSearchResult,
    StandardToolOptions,
    ToolRegistry,
    register_standard_tools,
)


HOST = "127.0.0.1"
PORT = 5174
DEMO_MODEL = "toolanything-demo-chatbot"


def build_registry(workspace: Path) -> ToolRegistry:
    (workspace / "notes").mkdir(parents=True, exist_ok=True)
    (workspace / "notes" / "intro.txt").write_text(
        "ToolAnything can expose one registry as MCP tools and OpenAI tools.\n"
        "This demo chatbot uses standard.fs.read, standard.data.json_parse, "
        "and standard.web.search.\n",
        encoding="utf-8",
    )

    registry = ToolRegistry()
    register_standard_tools(
        registry,
        StandardToolOptions(
            roots={"demo": workspace},
            search_provider=demo_search_provider,
            max_search_results=5,
        ),
    )
    return registry


def demo_search_provider(query: str, limit: int) -> list[StandardSearchResult]:
    results = [
        StandardSearchResult(
            title=f"{query} - ToolAnything standard tools",
            url="https://example.com/toolanything/standard-tools",
            snippet="Demo result showing how a host-owned search provider is normalized.",
            source="demo-provider",
        ),
        StandardSearchResult(
            title=f"{query} - MCP and OpenAI schema bridge",
            url="https://example.com/toolanything/tool-loop",
            snippet="Demo result for explaining one registry exported to multiple tool protocols.",
            source="demo-provider",
        ),
    ]
    return results[:limit]


def run_chat_turn(runtime: OpenAIChatRuntime, message: str) -> dict[str, Any]:
    return runtime.run(
        model=DEMO_MODEL,
        prompt=message,
        system_prompt=(
            "You are the deterministic demo model for a ToolAnything chatbot. "
            "Call exactly one suitable standard tool when the user asks to read, parse JSON, or search."
        ),
        api_key="demo-api-key",
        requester=DemoRequester(runtime),
        temperature=0.0,
        max_rounds=3,
    )


class DemoRequester:
    def __init__(self, runtime: OpenAIChatRuntime) -> None:
        self.runtime = runtime

    def __call__(
        self,
        *,
        api_key: str,
        model: str,
        messages: Sequence[Mapping[str, Any]],
        tools: Sequence[Mapping[str, Any]],
        temperature: float,
    ) -> dict[str, Any]:
        del api_key, model, tools, temperature

        last_tool = next((item for item in reversed(messages) if item.get("role") == "tool"), None)
        if last_tool:
            return {"content": self._final_answer(last_tool), "tool_calls": []}

        user_message = next((item.get("content", "") for item in reversed(messages) if item.get("role") == "user"), "")
        tool_name, arguments = route_user_message(str(user_message))
        if not tool_name:
            return {
                "content": (
                    "我可以示範三種基礎工具：讀取 notes/intro.txt、解析 JSON，"
                    "或搜尋 ToolAnything standard tools。"
                ),
                "tool_calls": [],
            }
        return {
            "content": None,
            "tool_calls": [
                self.runtime.create_tool_call(
                    tool_name,
                    arguments,
                    tool_call_id=f"demo_call_{tool_name.replace('.', '_')}",
                )
            ],
        }

    @staticmethod
    def _final_answer(tool_message: Mapping[str, Any]) -> str:
        try:
            payload = json.loads(str(tool_message.get("content", "{}")))
        except json.JSONDecodeError:
            payload = {"raw": tool_message.get("content")}
        tool_call_id = str(tool_message.get("tool_call_id", "tool"))
        pretty = json.dumps(payload, ensure_ascii=False, indent=2)
        return f"已完成 `{tool_call_id}`，工具回傳：\n```json\n{pretty}\n```"


def route_user_message(message: str) -> tuple[str, dict[str, Any]] | tuple[None, None]:
    normalized = message.strip()
    lowered = normalized.lower()

    if any(token in normalized for token in ("讀取", "讀", "read")):
        return "standard.fs.read", {"root_id": "demo", "relative_path": "notes/intro.txt", "max_lines": 8}

    json_text = extract_json_object(normalized)
    if json_text or "json" in lowered or "JSON" in normalized:
        return "standard.data.json_parse", {"text": json_text or '{"demo": true, "tool": "standard.data.json_parse"}'}

    if any(token in normalized for token in ("搜尋", "查詢", "search")):
        query = normalized
        for token in ("搜尋", "查詢", "search"):
            query = query.replace(token, " ")
        return "standard.web.search", {"query": " ".join(query.split()) or "ToolAnything", "limit": 2}

    return None, None


def extract_json_object(message: str) -> str:
    start = message.find("{")
    end = message.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return ""
    return message[start : end + 1]


class ChatbotHandler(SimpleHTTPRequestHandler):
    runtime: OpenAIChatRuntime
    web_root: Path

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(self.web_root), **kwargs)

    def do_POST(self) -> None:
        if self.path != "/api/chat":
            self.send_error(HTTPStatus.NOT_FOUND, "unknown endpoint")
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            message = str(body.get("message", "")).strip()
            if not message:
                raise ValueError("message is required")
            result = run_chat_turn(self.runtime, message)
            self._send_json(
                {
                    "reply": result["final_text"],
                    "tools_count": result["tools_count"],
                    "transcript": result["transcript"],
                }
            )
        except Exception as exc:  # pragma: no cover - example server boundary
            self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _send_json(self, payload: Mapping[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def build_handler(runtime: OpenAIChatRuntime) -> type[ChatbotHandler]:
    class ConfiguredHandler(ChatbotHandler):
        pass

    ConfiguredHandler.runtime = runtime
    ConfiguredHandler.web_root = Path(__file__).with_name("web")
    return ConfiguredHandler


def run_server(runtime: OpenAIChatRuntime, host: str, port: int, open_browser: bool) -> None:
    server = ThreadingHTTPServer((host, port), build_handler(runtime))
    url = f"http://{host}:{port}"
    print(f"[basic_tool_chatbot] serving {url}")
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[basic_tool_chatbot] stopping")
    finally:
        server.server_close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Standard tools chatbot UI demo")
    parser.add_argument("--host", default=HOST)
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument("--open-browser", action="store_true")
    parser.add_argument("--once", default="", help="Run one chat turn and print JSON instead of starting the server.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    with TemporaryDirectory() as temp_dir:
        registry = build_registry(Path(temp_dir))
        runtime = OpenAIChatRuntime(registry)
        if args.once:
            result = run_chat_turn(runtime, args.once)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return
        run_server(runtime, args.host, args.port, args.open_browser)


if __name__ == "__main__":
    if __package__ in (None, ""):
        sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    main()
