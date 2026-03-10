"""Serve the repository OpenCV example web UI."""
from __future__ import annotations

import argparse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

WEB_DIR = Path(__file__).resolve().parent / "web"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="啟動 repo 內的 OpenCV MCP Web 靜態頁")
    parser.add_argument("--host", default="127.0.0.1", help="監聽 host，預設 127.0.0.1")
    parser.add_argument("--port", type=int, default=5173, help="監聽 port，預設 5173")
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    def build_handler(*handler_args, **handler_kwargs):
        return SimpleHTTPRequestHandler(
            *handler_args,
            directory=str(WEB_DIR),
            **handler_kwargs,
        )

    server = ThreadingHTTPServer((args.host, args.port), build_handler)
    print(f"[opencv_mcp_web] Web UI 已啟動：http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
