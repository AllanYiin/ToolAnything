"""ToolAnything CLI 入口，提供 MCP server 與輔助指令。"""
from __future__ import annotations

import argparse
import json
import os
import platform
from pathlib import Path
from typing import Any, Dict

from toolanything.core import FailureLogManager, ToolRegistry, ToolSearchTool


def _get_default_claude_config_path() -> Path:
    """取得 Claude Desktop 設定檔的預設路徑 (跨平台)。"""
    if platform.system() == "Windows":
        return Path(os.environ["APPDATA"]) / "Claude" / "config.json"
    return Path.home() / "Library" / "Application Support" / "Claude" / "config.json"


def _build_mcp_entry(port: int, module: str | None = None, *, stdio: bool = False) -> Dict[str, Any]:
    if module:
        args = ["-m", "toolanything.cli", "serve", module]
        if stdio:
            args.append("--stdio")
        args.extend(["--port", str(port)])
        return _build_custom_entry(command="python", args=args)

    return _build_custom_entry(
        command="python",
        args=["-m", "toolanything.cli", "run-mcp", "--port", str(port)],
    )


def _build_custom_entry(command: str, args: list[str]) -> Dict[str, Any]:
    return {
        "command": command,
        "args": args,
        "autoStart": True,
    }


def _init_claude_config(path: Path, port: int, force: bool, module: str | None) -> None:
    template: Dict[str, Any] = {
        "mcpServers": {"toolanything": _build_mcp_entry(port, module, stdio=True)}
    }

    if path.exists() and not force:
        raise FileExistsError(f"{path} 已存在，如要覆寫請加入 --force")

    path.write_text(json.dumps(template, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已生成 {path}，將內容加入 Claude Desktop 設定即可完成註冊。")


def _run_mcp_server(port: int, host: str) -> None:
    from toolanything.server.mcp_tool_server import run_server

    run_server(port=port, host=host)


def _run_stdio_server() -> None:
    from toolanything.server.mcp_stdio_server import run_stdio_server

    run_stdio_server()


def _serve_module(module: str, host: str, port: int, stdio: bool) -> None:
    from toolanything.runtime import run

    run(module=module, host=host, port=port, stdio=stdio)


def _install_claude_config(path: Path, port: int, name: str, module: str | None) -> None:
    path = path.expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists():
        content = path.read_text(encoding="utf-8")
        config = json.loads(content) if content.strip() else {}
    else:
        config = {}

    mcp_servers = config.setdefault("mcpServers", {})
    mcp_servers[name] = _build_mcp_entry(port, module, stdio=True)

    path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"已更新 {path}，新增 {name} MCP 伺服器設定，重新啟動 Claude Desktop 後即可自動載入。"
    )


def _install_claude_opencv_config(path: Path, port: int, name: str) -> None:
    path = path.expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists():
        content = path.read_text(encoding="utf-8")
        config = json.loads(content) if content.strip() else {}
    else:
        config = {}

    mcp_servers = config.setdefault("mcpServers", {})
    mcp_servers[name] = _build_custom_entry(
        command="python",
        args=[
            "-m",
            "toolanything.cli",
            "serve",
            "examples.opencv_mcp_web.server",
            "--stdio",
            "--port",
            str(port),
        ],
    )

    path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"已更新 {path}，新增 {name} OpenCV MCP Web 設定，重新啟動 Claude Desktop 後即可自動載入。"
    )


def _run_search(
    query: str,
    tags: list[str] | None,
    prefix: str | None,
    top_k: int,
    sort_by_failure: bool,
    max_cost: float | None,
    latency_budget_ms: int | None,
    allow_side_effects: bool,
    categories: list[str] | None,
) -> None:
    failure_log = FailureLogManager(Path(".tool_failures.json"))
    registry = ToolRegistry.global_instance()
    searcher = ToolSearchTool(registry, failure_log)

    results = searcher.search(
        query=query,
        tags=tags,
        prefix=prefix,
        top_k=top_k,
        sort_by_failure=sort_by_failure,
        max_cost=max_cost,
        latency_budget_ms=latency_budget_ms,
        allow_side_effects=allow_side_effects,
        categories=categories,
    )

    for spec in results:
        score = failure_log.failure_score(spec.name)
        metadata = spec.normalized_metadata()
        print(
            json.dumps(
                {
                    "name": spec.name,
                    "description": spec.description,
                    "tags": list(spec.tags),
                    "failure_score": score,
                    "cost": metadata.cost,
                    "latency_hint_ms": metadata.latency_hint_ms,
                    "side_effect": metadata.side_effect,
                    "category": metadata.category,
                },
                ensure_ascii=False,
            )
        )


def _print_examples_nav() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    entries = [
        (
            "Quickstart",
            repo_root / "examples" / "quickstart" / "README.md",
            "從 0 跑通 tools/list + search + call 的最短路徑",
        ),
        (
            "Tool Selection",
            repo_root / "examples" / "tool_selection" / "README.md",
            "metadata / constraints / strategy 的搜尋差異",
        ),
        (
            "Protocol Boundary",
            repo_root / "examples" / "protocol_boundary" / "README.md",
            "protocol/core 與 server/transport 邊界說明",
        ),
    ]
    print("ToolAnything examples 入口：")
    for title, path, description in entries:
        print(f"- {title}: {path} ({description})")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="toolanything", description="ToolAnything CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run-mcp", help="啟動內建 MCP Tool Server")
    run_parser.add_argument("--port", type=int, default=9090, help="監聽 port，預設 9090")
    run_parser.add_argument("--host", default="0.0.0.0", help="監聽 host，預設 0.0.0.0")
    run_parser.set_defaults(func=lambda args: _run_mcp_server(port=args.port, host=args.host))

    stdio_parser = subparsers.add_parser("run-stdio", help="啟動 MCP Stdio Server (供 Claude Desktop 使用)")
    stdio_parser.set_defaults(func=lambda args: _run_stdio_server())

    serve_parser = subparsers.add_parser("serve", help="載入工具模組並啟動伺服器")
    serve_parser.add_argument("module", help="工具模組路徑（例如 examples.opencv_mcp_web.server）")
    serve_parser.add_argument("--port", type=int, default=9090, help="監聽 port，預設 9090")
    serve_parser.add_argument("--host", default="0.0.0.0", help="監聽 host，預設 0.0.0.0")
    serve_parser.add_argument(
        "--stdio",
        action="store_true",
        help="改用 stdio 啟動（供 MCP Desktop 類型使用）",
    )
    serve_parser.set_defaults(
        func=lambda args: _serve_module(
            module=args.module,
            host=args.host,
            port=args.port,
            stdio=args.stdio,
        )
    )

    init_parser = subparsers.add_parser("init-claude", help="生成 Claude Desktop MCP 設定片段")
    init_parser.add_argument("--output", default="claude_desktop_config.json", help="輸出檔案路徑")
    init_parser.add_argument("--port", type=int, default=9090, help="MCP server port，預設 9090")
    init_parser.add_argument(
        "--module",
        help="工具模組路徑（例如 examples.opencv_mcp_web.server），提供時會使用 serve 模式",
    )
    init_parser.add_argument("--force", action="store_true", help="已存在時覆寫輸出檔案")
    init_parser.set_defaults(
        func=lambda args: _init_claude_config(
            path=Path(args.output),
            port=args.port,
            force=args.force,
            module=args.module,
        )
    )

    install_parser = subparsers.add_parser("install-claude", help="直接寫入 Claude Desktop 設定檔")
    install_parser.add_argument(
        "--config",
        default=_get_default_claude_config_path(),
        type=Path,
        help="Claude Desktop 設定檔路徑",
    )
    install_parser.add_argument("--port", type=int, default=9090, help="MCP server port，預設 9090")
    install_parser.add_argument(
        "--module",
        help="工具模組路徑（例如 examples.opencv_mcp_web.server），提供時會使用 serve 模式",
    )
    install_parser.add_argument(
        "--name",
        default="toolanything",
        help="在 Claude Desktop 中顯示的 mcpServers 名稱，預設 toolanything",
    )
    install_parser.set_defaults(
        func=lambda args: _install_claude_config(
            path=args.config, port=args.port, name=args.name, module=args.module
        )
    )

    install_opencv_parser = subparsers.add_parser(
        "install-claude-opencv",
        help="直接寫入 Claude Desktop 設定檔（OpenCV MCP Web 範例）",
    )
    install_opencv_parser.add_argument(
        "--config",
        default=_get_default_claude_config_path(),
        type=Path,
        help="Claude Desktop 設定檔路徑",
    )
    install_opencv_parser.add_argument("--port", type=int, default=9091, help="監聽 port，預設 9091")
    install_opencv_parser.add_argument(
        "--name",
        default="opencv_mcp_web",
        help="在 Claude Desktop 中顯示的 mcpServers 名稱，預設 opencv_mcp_web",
    )
    install_opencv_parser.set_defaults(
        func=lambda args: _install_claude_opencv_config(
            path=args.config, port=args.port, name=args.name
        )
    )

    search_parser = subparsers.add_parser(
        "search",
        help="搜尋已註冊的工具並依失敗分數排序",
        description=(
            "搜尋已註冊的工具並依失敗分數排序，支援 metadata / constraints 條件。"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "範例:\n"
            "  toolanything search --query weather --max-cost 0.1 --latency-budget-ms 200\n"
            "  toolanything search --tags finance realtime --allow-side-effects\n"
            "  toolanything search --category routing --category search\n"
            "  策略示例：python examples/tool_selection/03_custom_strategy.py (strategy 比較)\n\n"
            "See also: examples/tool_selection/README.md"
        ),
    )
    search_parser.add_argument("--query", default="", help="名稱或描述關鍵字")
    search_parser.add_argument(
        "--tags",
        nargs="*",
        default=None,
        help="需要包含的標籤，多個以空白分隔",
    )
    search_parser.add_argument("--prefix", default=None, help="工具名稱前綴過濾條件")
    search_parser.add_argument("--top-k", type=int, default=10, help="回傳前 K 筆結果")
    search_parser.add_argument(
        "--disable-failure-sort",
        action="store_true",
        help="關閉依近期失敗分數排序的功能",
    )
    search_parser.add_argument("--max-cost", type=float, default=None, help="最大成本門檻")
    search_parser.add_argument(
        "--latency-budget-ms",
        type=int,
        default=None,
        help="延遲預算（毫秒）",
    )
    search_parser.add_argument(
        "--allow-side-effects",
        action="store_true",
        help="允許含 side_effect 的工具（預設排除）",
    )
    search_parser.add_argument(
        "--category",
        action="append",
        default=None,
        help="工具分類（可重複指定或用逗號分隔）",
    )
    search_parser.set_defaults(
        func=lambda args: _run_search(
            query=args.query,
            tags=args.tags,
            prefix=args.prefix,
            top_k=args.top_k,
            sort_by_failure=not args.disable_failure_sort,
            max_cost=args.max_cost,
            latency_budget_ms=args.latency_budget_ms,
            allow_side_effects=args.allow_side_effects,
            categories=[
                item
                for entry in (args.category or [])
                for item in entry.split(",")
                if item
            ]
            or None,
        )
    )

    examples_parser = subparsers.add_parser(
        "examples",
        help="列出 examples 入口與簡介",
        description="輸出 examples 入口路徑與簡要說明。",
    )
    examples_parser.set_defaults(func=lambda args: _print_examples_nav())

    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
