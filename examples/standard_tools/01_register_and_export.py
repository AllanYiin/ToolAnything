from __future__ import annotations

import asyncio
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from toolanything import StandardToolOptions, ToolRegistry, register_standard_tools


async def main() -> None:
    with TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        (root / "note.txt").write_text("alpha\nbeta\n", encoding="utf-8")

        registry = ToolRegistry()
        specs = register_standard_tools(registry, StandardToolOptions(roots={"workspace": root}))

        fs_read = registry.get_tool("standard.fs.read")
        read_result = await registry.invoke_tool_async(
            "standard.fs.read",
            arguments={"root_id": "workspace", "relative_path": "note.txt", "max_lines": 1},
        )
        json_result = await registry.invoke_tool_async(
            "standard.data.json_parse",
            arguments={"text": '{"ok": true, "count": 2}'},
        )

        payload = {
            "registered_count": len(specs),
            "mcp": {
                "name": fs_read.to_mcp()["name"],
                "has_inputSchema": "inputSchema" in fs_read.to_mcp(),
                "has_outputSchema": "outputSchema" in fs_read.to_mcp(),
            },
            "openai": {
                "name": fs_read.to_openai()["function"]["name"],
                "strict": fs_read.to_openai()["function"]["strict"],
                "schema_field": "parameters",
            },
            "cli": {
                "commandPath": fs_read.to_cli()["commandPath"],
            },
            "calls": {
                "fs_read": read_result,
                "json_parse": json_result,
            },
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
