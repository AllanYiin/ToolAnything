from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from toolanything import (
    StandardToolOptions,
    StandardToolRoot,
    ToolRegistry,
    register_standard_tools,
)


async def main() -> None:
    with TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        registry = ToolRegistry()
        register_standard_tools(
            registry,
            StandardToolOptions(
                roots=(StandardToolRoot("workspace", root, writable=True),),
                include_write_tools=True,
            ),
        )

        created = await registry.invoke_tool_async(
            "standard.fs.write",
            arguments={
                "root_id": "workspace",
                "relative_path": "draft.txt",
                "content": "one",
            },
        )

        expected_sha256 = hashlib.sha256(b"one").hexdigest()
        replaced = await registry.invoke_tool_async(
            "standard.fs.write",
            arguments={
                "root_id": "workspace",
                "relative_path": "draft.txt",
                "content": "two",
                "expected_sha256": expected_sha256,
            },
        )

        payload = {
            "created": created,
            "replaced": replaced,
            "final_content": (root / "draft.txt").read_text(encoding="utf-8"),
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())

