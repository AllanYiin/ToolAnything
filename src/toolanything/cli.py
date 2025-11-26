"""ToolAnything CLI 入口，提供 MCP server 與輔助指令。"""
from __future__ import annotations

import argparse
import json
import os
import platform
from pathlib import Path
from typing import Any, Dict


def _get_default_claude_config_path() -> Path:
    """取得 Claude Desktop 設定檔的預設路徑 (跨平台)。"""
    if platform.system() == "Windows":
        return Path(os.environ["APPDATA"]) / "Claude" / "config.json"
    return Path.home() / "Library" / "Application Support" / "Claude" / "config.json"


def _init_claude_config(path: Path, port: int, force: bool) -> None:
    template: Dict[str, Any] = {
        "mcpServers": {
            "toolanything": {
                "command": "python",
                "args": ["-m", "toolanything.server.mcp_tool_server", "--port", str(port)],
                "autoStart": True,
            }
        }
    }

    if path.exists() and not force:
        raise FileExistsError(f"{path} 已存在，如要覆寫請加入 --force")

    path.write_text(json.dumps(template, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已生成 {path}，將內容加入 Claude Desktop 設定即可完成註冊。")


def _run_mcp_server(port: int, host: str) -> None:
    from toolanything.server.mcp_tool_server import run_server

    run_server(port=port, host=host)


def _install_claude_config(path: Path, port: int, name: str) -> None:
    path = path.expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)

    mcp_entry = {
        "command": "python",
        "args": ["-m", "toolanything.server.mcp_tool_server", "--port", str(port)],
        "autoStart": True,
    }

    if path.exists():
        content = path.read_text(encoding="utf-8")
        config = json.loads(content) if content.strip() else {}
    else:
        config = {}

    mcp_servers = config.setdefault("mcpServers", {})
    mcp_servers[name] = mcp_entry

    path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"已更新 {path}，新增 {name} MCP 伺服器設定，重新啟動 Claude Desktop 後即可自動載入。"
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="toolanything", description="ToolAnything CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run-mcp", help="啟動內建 MCP Tool Server")
    run_parser.add_argument("--port", type=int, default=9090, help="監聽 port，預設 9090")
    run_parser.add_argument("--host", default="0.0.0.0", help="監聽 host，預設 0.0.0.0")
    run_parser.set_defaults(func=lambda args: _run_mcp_server(port=args.port, host=args.host))

    init_parser = subparsers.add_parser("init-claude", help="生成 Claude Desktop MCP 設定片段")
    init_parser.add_argument("--output", default="claude_desktop_config.json", help="輸出檔案路徑")
    init_parser.add_argument("--port", type=int, default=9090, help="MCP server port，預設 9090")
    init_parser.add_argument("--force", action="store_true", help="已存在時覆寫輸出檔案")
    init_parser.set_defaults(
        func=lambda args: _init_claude_config(
            path=Path(args.output),
            port=args.port,
            force=args.force,
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
        "--name",
        default="toolanything",
        help="在 Claude Desktop 中顯示的 mcpServers 名稱，預設 toolanything",
    )
    install_parser.set_defaults(
        func=lambda args: _install_claude_config(path=args.config, port=args.port, name=args.name)
    )

    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
