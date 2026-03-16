"""ToolAnything CLI 入口，提供 MCP server 與輔助指令。"""
from __future__ import annotations

import argparse
import json
import os
import platform
import shlex

import socket
import subprocess
import sys
import time

from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict
from urllib import request as url_request
from urllib.parse import urljoin

from .cli_export import (
    DEFAULT_CONFIG_FILENAME,
    CLIExportOptions,
    build_cli_app,
    export_cli_project,
    load_cli_project,
    write_cli_launcher,
)
from .cli_export.config import cli_project_to_dict
from .core import FailureLogManager, ToolRegistry, ToolSearchTool
from .core.connection_tester import ConnectionTester, render_report
from .utils.logger import logger


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
    from .server.mcp_tool_server import run_server

    run_server(port=port, host=host)


def _run_streamable_http_server(port: int, host: str) -> None:
    from .server.mcp_streamable_http import run_server

    run_server(port=port, host=host)


def _run_stdio_server() -> None:
    from .server.mcp_stdio_server import run_stdio_server

    run_stdio_server()


def _serve_module(
    module: str,
    host: str,
    port: int,
    stdio: bool,
    streamable_http: bool,
) -> None:
    from .runtime import run

    run(
        module=module,
        host=host,
        port=port,
        stdio=stdio,
        streamable_http=streamable_http,
    )


def _load_cli_registry(module: str) -> ToolRegistry:
    from .runtime.serve import load_tool_module

    loaded_module = load_tool_module(module)
    module_registry = getattr(loaded_module, "registry", None)
    if isinstance(module_registry, ToolRegistry):
        return module_registry

    tool_registry = getattr(loaded_module, "tool_registry", None)
    if isinstance(tool_registry, ToolRegistry):
        return tool_registry

    return ToolRegistry.global_instance()


def _resolve_cli_context(
    *,
    module: str | None,
    config_path: str | None,
    app_name: str | None = None,
    app_description: str | None = None,
    default_output_mode: str | None = None,
    include_tools: list[str] | None = None,
    exclude_tools: list[str] | None = None,
    overwrite: bool = False,
):
    project_config = load_cli_project(config_path) if config_path else None
    resolved_module = module or (project_config.module if project_config else None)
    if not resolved_module:
        raise ValueError("CLI export 需要 --module 或 config 中的 module")

    registry = _load_cli_registry(resolved_module)
    effective_include = include_tools or (project_config.tools if project_config else None)
    effective_output_mode = (
        default_output_mode
        or (project_config.default_output_mode if project_config else "text")
    )
    options = CLIExportOptions(
        app_name=app_name or (project_config.app_name if project_config else "tools"),
        app_description=app_description or (project_config.app_description if project_config else None),
        default_output_mode=effective_output_mode,
        include_tools=effective_include,
        exclude_tools=exclude_tools,
        overwrite=overwrite,
    )
    app = build_cli_app(registry, options, project_config=project_config)
    return app, project_config, resolved_module


def _run_cli_export(args: argparse.Namespace) -> None:
    config_path = args.config
    app, project_config, resolved_module = _resolve_cli_context(
        module=args.module,
        config_path=config_path if Path(config_path).exists() else None,
        app_name=args.app_name,
        app_description=args.app_description,
        default_output_mode=args.default_output_mode,
        include_tools=args.include_tools,
        exclude_tools=args.exclude_tools,
        overwrite=args.overwrite,
    )
    config = export_cli_project(
        app.registry,
        config_path,
        app.options,
        module=resolved_module,
        launcher_path=args.launcher,
        command_overrides=project_config.command_overrides if project_config else None,
    )
    if args.launcher:
        launcher_path = Path(args.launcher)
        if launcher_path.exists():
            if not args.overwrite:
                raise FileExistsError(f"{launcher_path} 已存在，如要覆寫請加入 --overwrite")
            launcher_path.unlink()
        write_cli_launcher(config_path, args.launcher)
    inspection = app.inspect()
    if args.json:
        print(
            json.dumps(
                {
                    "config": cli_project_to_dict(config),
                    "inspection": asdict(inspection),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print(f"已輸出 CLI project config: {config_path}")
        print(f"app: {inspection.app_name}")
        for command in inspection.commands:
            print(f"- {' '.join(command['command_path'])} -> {command['tool_name']}")
        if args.launcher:
            print(f"launcher: {args.launcher}")


def _run_cli_dynamic(args: argparse.Namespace) -> None:
    app, _, _ = _resolve_cli_context(
        module=args.module,
        config_path=args.config,
        app_name=args.app_name,
        app_description=args.app_description,
        default_output_mode=args.default_output_mode,
        include_tools=args.include_tools,
        exclude_tools=args.exclude_tools,
        overwrite=args.overwrite,
    )
    argv = list(args.argv or [])
    if argv[:1] == ["--"]:
        argv = argv[1:]
    raise SystemExit(app.run(argv))


def _run_cli_inspect(args: argparse.Namespace) -> None:
    app, project_config, resolved_module = _resolve_cli_context(
        module=args.module,
        config_path=args.config,
        app_name=args.app_name,
        app_description=args.app_description,
        default_output_mode=args.default_output_mode,
        include_tools=args.include_tools,
        exclude_tools=args.exclude_tools,
    )
    inspection = asdict(app.inspect())
    inspection["module"] = resolved_module
    inspection["config"] = cli_project_to_dict(project_config) if project_config else None
    print(json.dumps(inspection, ensure_ascii=False, indent=2))


def _run_cli_show_config(args: argparse.Namespace) -> None:
    config = load_cli_project(args.config)
    print(json.dumps(cli_project_to_dict(config), ensure_ascii=False, indent=2))


def _run_cli_delete_project(args: argparse.Namespace) -> None:
    config = load_cli_project(args.config)
    config_path = Path(args.config)
    launcher_path = Path(config.launcher_path) if config.launcher_path else None
    config_path.unlink(missing_ok=False)
    if args.delete_launcher and launcher_path and launcher_path.exists():
        launcher_path.unlink()
    print(f"已刪除 CLI project config: {config_path}")


def run_exported_cli(config_path: str, argv: list[str]) -> int:
    app, _, _ = _resolve_cli_context(module=None, config_path=config_path)
    return app.run(argv)


def _run_inspector_ui(host: str, port: int, timeout: float, no_open: bool) -> None:
    from .inspector import run_inspector

    run_inspector(
        host=host,
        port=port,
        default_timeout=timeout,
        open_browser=not no_open,
    )


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


def _run_doctor(args: argparse.Namespace) -> None:
    tester = ConnectionTester(timeout=args.timeout)

    if args.mode == "stdio":
        if args.cmd and args.tools:
            report = tester.build_config_error(
                mode="stdio",
                message="--cmd 與 --tools 不可同時使用",
                suggestion="請擇一提供 stdio server 啟動方式",
            )
        elif args.cmd:
            cmd = shlex.split(args.cmd)
            report = tester.run_stdio(cmd)
        elif args.tools:
            cmd = [
                sys.executable,
                "-m",
                "toolanything.core.doctor_server",
                "--tools",
                args.tools,
            ]
            report = tester.run_stdio(cmd)
        else:
            report = tester.build_config_error(
                mode="stdio",
                message="缺少 stdio 啟動參數",
                suggestion="請提供 --cmd 或 --tools 啟動 stdio server",
            )
    else:

        report = _run_doctor_http(args, tester)

    if args.json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(render_report(report))

    if not report.ok:
        raise SystemExit(1)



def _run_doctor_http(args: argparse.Namespace, tester: ConnectionTester) -> Any:
    if args.url and (args.cmd or args.tools):
        return tester.build_config_error(
            mode="http",
            message="--url 不可與 --cmd/--tools 同時使用",
            suggestion="請擇一提供 HTTP 連線或啟動方式",
        )

    if args.url:
        return tester.run_http(args.url)

    if args.cmd:
        url = args.url or "http://127.0.0.1:9090"
        return _run_http_subprocess(tester, url, shlex.split(args.cmd), args.timeout)

    if args.tools:
        port = _pick_free_port()
        url = f"http://127.0.0.1:{port}"
        cmd = [
            sys.executable,
            "-m",
            "toolanything.cli",
            "serve",
            args.tools,
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ]
        return _run_http_subprocess(tester, url, cmd, args.timeout)

    return tester.build_config_error(
        mode="http",
        message="缺少 HTTP 連線或啟動參數",
        suggestion="請提供 --url 連線既有 server，或使用 --tools/--cmd 自動啟動",
    )


def _pick_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _wait_for_http_ready(url: str, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    health_url = urljoin(url, "/health")
    last_error: str | None = None
    while time.monotonic() < deadline:
        try:
            with url_request.urlopen(health_url, timeout=1) as response:
                if response.status == 200:
                    return
                last_error = f"status {response.status}"
        except Exception as exc:
            last_error = str(exc)
        time.sleep(0.2)
    raise RuntimeError(last_error or "unknown error")


def _run_http_subprocess(
    tester: ConnectionTester, url: str, cmd: list[str], timeout: float
) -> Any:
    process: subprocess.Popen[str] | None = None
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            _wait_for_http_ready(url, timeout=min(5.0, timeout))
        except Exception as exc:
            report = tester.build_config_error(
                mode="http",
                message="HTTP server 未就緒",
                suggestion="請確認啟動命令是否正確或提高 --timeout",
            )
            report.steps[0].details = {
                "exception": str(exc),
                "stderr": _collect_stderr(process),
            }
            return report
        return tester.run_http(url)
    finally:
        if process is not None:
            _terminate_process(process)


def _collect_stderr(process: subprocess.Popen[str]) -> str:
    if process.stderr is None:
        return ""
    try:
        _, stderr = process.communicate(timeout=1)
    except subprocess.TimeoutExpired:
        process.kill()
        _, stderr = process.communicate(timeout=1)
    return stderr or ""


def _terminate_process(process: subprocess.Popen[str]) -> None:
    try:
        process.terminate()
        process.wait(timeout=2)
    except Exception:
        try:
            process.kill()
        except Exception:
            pass



def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="toolanything", description="ToolAnything CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run-mcp", help="啟動內建 MCP Tool Server")
    run_parser.add_argument("--port", type=int, default=9090, help="監聽 port，預設 9090")
    run_parser.add_argument("--host", default="127.0.0.1", help="監聽 host，預設 127.0.0.1")
    run_parser.set_defaults(func=lambda args: _run_mcp_server(port=args.port, host=args.host))

    streamable_parser = subparsers.add_parser(
        "run-streamable-http",
        help="啟動 MCP Streamable HTTP transport",
    )
    streamable_parser.add_argument("--port", type=int, default=9092, help="監聽 port，預設 9092")
    streamable_parser.add_argument("--host", default="127.0.0.1", help="監聽 host，預設 127.0.0.1")
    streamable_parser.set_defaults(
        func=lambda args: _run_streamable_http_server(port=args.port, host=args.host)
    )

    stdio_parser = subparsers.add_parser("run-stdio", help="啟動 MCP Stdio Server (供 Claude Desktop 使用)")
    stdio_parser.set_defaults(func=lambda args: _run_stdio_server())

    serve_parser = subparsers.add_parser("serve", help="載入工具模組並啟動伺服器")
    serve_parser.add_argument(
        "module",
        help="工具模組或檔案路徑（例如 my_tools.weather 或 examples/opencv_mcp_web/server.py）",
    )
    serve_parser.add_argument("--port", type=int, default=9090, help="監聽 port，預設 9090")
    serve_parser.add_argument("--host", default="127.0.0.1", help="監聽 host，預設 127.0.0.1")
    serve_parser.add_argument(
        "--stdio",
        action="store_true",
        help="改用 stdio 啟動（供 MCP Desktop 類型使用）",
    )
    serve_parser.add_argument(
        "--streamable-http",
        action="store_true",
        help="改用 MCP Streamable HTTP 啟動（/mcp）",
    )
    serve_parser.set_defaults(
        func=lambda args: _serve_module(
            module=args.module,
            host=args.host,
            port=args.port,
            stdio=args.stdio,
            streamable_http=args.streamable_http,
        )
    )

    init_parser = subparsers.add_parser("init-claude", help="生成 Claude Desktop MCP 設定片段")
    init_parser.add_argument("--output", default="claude_desktop_config.json", help="輸出檔案路徑")
    init_parser.add_argument("--port", type=int, default=9090, help="MCP server port，預設 9090")
    init_parser.add_argument(
        "--module",
        help="工具模組或檔案路徑（例如 my_tools.weather 或 examples/opencv_mcp_web/server.py），提供時會使用 serve 模式",
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
        help="工具模組或檔案路徑（例如 my_tools.weather 或 examples/opencv_mcp_web/server.py），提供時會使用 serve 模式",
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
            "  策略示例：python examples/tool_selection/03_custom_strategy.py\n\n"
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

    doctor_parser = subparsers.add_parser(
        "doctor",
        aliases=["connection-test"],
        help="檢查 MCP transport 與工具呼叫狀態",
    )
    doctor_parser.add_argument(
        "--mode",
        choices=["stdio", "http"],
        default="stdio",
        help="診斷模式（stdio 或 http），預設 stdio",
    )
    doctor_parser.add_argument(
        "--cmd",

        help=(
            "stdio/http 模式啟動命令（例如 \"python -m toolanything.cli run-stdio\"；"
            "http 模式預設連 http://127.0.0.1:9090）"
        ),
    )
    doctor_parser.add_argument(
        "--tools",
        help="工具模組路徑，stdio 會啟動 doctor 專用 server；http 會自動啟動 serve",

    )
    doctor_parser.add_argument(
        "--url",
        help="http 模式 MCP server base URL（例如 http://localhost:9090）",
    )
    doctor_parser.add_argument(
        "--timeout",
        type=float,
        default=8.0,
        help="每一步驟的 timeout 秒數，預設 8 秒",
    )
    doctor_parser.add_argument(
        "--json",
        action="store_true",
        help="輸出 JSON 格式報告",
    )
    doctor_parser.set_defaults(func=_run_doctor)

    inspect_parser = subparsers.add_parser(
        "inspect",
        help="啟動內建 Web 版 MCP Test Client",
    )
    inspect_parser.add_argument("--port", type=int, default=9060, help="監聽 port，預設 9060")
    inspect_parser.add_argument("--host", default="127.0.0.1", help="監聽 host，預設 127.0.0.1")
    inspect_parser.add_argument(
        "--timeout",
        type=float,
        default=8.0,
        help="Inspector 預設 timeout 秒數，預設 8 秒",
    )
    inspect_parser.add_argument(
        "--no-open",
        action="store_true",
        help="不要自動開啟瀏覽器",
    )
    inspect_parser.set_defaults(
        func=lambda args: _run_inspector_ui(
            host=args.host,
            port=args.port,
            timeout=args.timeout,
            no_open=args.no_open,
        )
    )

    cli_parser = subparsers.add_parser(
        "cli",
        help="將同一份 ToolContract 匯出為 CLI command tree",
    )
    cli_subparsers = cli_parser.add_subparsers(dest="cli_command", required=True)

    cli_export_parser = cli_subparsers.add_parser("export", help="保存 CLI project config")
    cli_export_parser.add_argument("--module", required=True, help="工具模組或檔案路徑")
    cli_export_parser.add_argument(
        "--config",
        default=DEFAULT_CONFIG_FILENAME,
        help="CLI project config 路徑",
    )
    cli_export_parser.add_argument("--app-name", required=True, help="CLI app 名稱")
    cli_export_parser.add_argument("--app-description", help="CLI app 說明")
    cli_export_parser.add_argument(
        "--default-output-mode",
        choices=["text", "json"],
        default="text",
        help="預設輸出模式",
    )
    cli_export_parser.add_argument(
        "--include-tools",
        nargs="*",
        default=None,
        help="只匯出指定工具名稱",
    )
    cli_export_parser.add_argument(
        "--exclude-tools",
        nargs="*",
        default=None,
        help="排除指定工具名稱",
    )
    cli_export_parser.add_argument("--launcher", help="輸出可執行 launcher 路徑")
    cli_export_parser.add_argument("--overwrite", action="store_true", help="允許覆寫")
    cli_export_parser.add_argument("--json", action="store_true", help="輸出 JSON")
    cli_export_parser.set_defaults(func=_run_cli_export)

    cli_run_parser = cli_subparsers.add_parser(
        "run",
        help="用動態 CLI app 執行工具",
        description="用動態 CLI app 執行工具；建議以 -- 後接實際 command argv。",
    )
    cli_run_parser.add_argument("--module", help="工具模組或檔案路徑")
    cli_run_parser.add_argument("--config", help="CLI project config 路徑")
    cli_run_parser.add_argument("--app-name", help="覆寫 CLI app 名稱")
    cli_run_parser.add_argument("--app-description", help="覆寫 CLI app 說明")
    cli_run_parser.add_argument(
        "--default-output-mode",
        choices=["text", "json"],
        help="覆寫預設輸出模式",
    )
    cli_run_parser.add_argument("--include-tools", nargs="*", default=None)
    cli_run_parser.add_argument("--exclude-tools", nargs="*", default=None)
    cli_run_parser.add_argument("--overwrite", action="store_true")
    cli_run_parser.add_argument(
        "argv",
        nargs=argparse.REMAINDER,
        help="CLI command argv（建議格式：-- <command> <subcommand> ...）",
    )
    cli_run_parser.set_defaults(func=_run_cli_dynamic)

    cli_inspect_parser = cli_subparsers.add_parser("inspect", help="檢視 CLI command tree")
    cli_inspect_parser.add_argument("--module", help="工具模組或檔案路徑")
    cli_inspect_parser.add_argument("--config", help="CLI project config 路徑")
    cli_inspect_parser.add_argument("--app-name", help="覆寫 CLI app 名稱")
    cli_inspect_parser.add_argument("--app-description", help="覆寫 CLI app 說明")
    cli_inspect_parser.add_argument(
        "--default-output-mode",
        choices=["text", "json"],
        help="覆寫預設輸出模式",
    )
    cli_inspect_parser.add_argument("--include-tools", nargs="*", default=None)
    cli_inspect_parser.add_argument("--exclude-tools", nargs="*", default=None)
    cli_inspect_parser.set_defaults(func=_run_cli_inspect)

    cli_show_parser = cli_subparsers.add_parser("show-config", help="顯示 CLI project config")
    cli_show_parser.add_argument(
        "--config",
        default=DEFAULT_CONFIG_FILENAME,
        help="CLI project config 路徑",
    )
    cli_show_parser.set_defaults(func=_run_cli_show_config)

    cli_delete_parser = cli_subparsers.add_parser("delete-project", help="刪除 CLI project config")
    cli_delete_parser.add_argument(
        "--config",
        default=DEFAULT_CONFIG_FILENAME,
        help="CLI project config 路徑",
    )
    cli_delete_parser.add_argument(
        "--delete-launcher",
        action="store_true",
        help="同時刪除 config 內記錄的 launcher",
    )
    cli_delete_parser.set_defaults(func=_run_cli_delete_project)

    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    try:
        args.func(args)
    except SystemExit:
        raise
    except Exception:
        logger.exception("CLI 執行失敗")
        print("[ToolAnything] CLI 執行失敗，請查看 logs/toolanything.log")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
