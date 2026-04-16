from __future__ import annotations

import asyncio
import json

from toolanything import (
    StandardSearchResult,
    StandardToolOptions,
    ToolRegistry,
    register_standard_tools,
)


def search_provider(query: str, limit: int):
    results = [
        StandardSearchResult(
            title=f"{query} handbook",
            url="https://example.com/toolanything-handbook",
            snippet="Provider-owned search result for standard tool demos.",
            source="demo-provider",
        ),
        {
            "title": f"{query} changelog",
            "url": "https://example.com/toolanything-changelog",
            "snippet": "Dictionary results are also normalized.",
            "source": "demo-provider",
        },
    ]
    return results[:limit]


async def main() -> None:
    registry = ToolRegistry()
    register_standard_tools(
        registry,
        StandardToolOptions(search_provider=search_provider),
    )

    search_result = await registry.invoke_tool_async(
        "standard.web.search",
        arguments={"query": "ToolAnything", "limit": 2},
    )
    search_spec = registry.get_tool("standard.web.search")

    payload = {
        "requires_provider": search_spec.metadata.get("requires_provider"),
        "results": search_result["results"],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())

