from __future__ import annotations

import asyncio
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from toolanything import HttpFieldSpec, HttpSourceSpec, ToolManager


class DemoHandler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        if self.path.startswith("/users/"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(
                json.dumps({"path": self.path, "authorization": self.headers.get("Authorization")}).encode("utf-8")
            )
            return
        self.send_response(404)
        self.end_headers()

    def log_message(self, format, *args):  # noqa: A003
        del format, args


def main() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), DemoHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        manager = ToolManager()
        manager.register_http_tool(
            HttpSourceSpec(
                name="users.fetch",
                description="示範 HTTP source tool",
                method="GET",
                base_url=f"http://127.0.0.1:{server.server_port}",
                path="/users/{user_id}",
                path_params=(HttpFieldSpec("user_id", {"type": "string"}, required=True),),
                query_params=(HttpFieldSpec("include", {"type": "string"}),),
            )
        )

        result = asyncio.run(
            manager.invoke("users.fetch", {"user_id": "42", "include": "profile"})
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


if __name__ == "__main__":
    main()
