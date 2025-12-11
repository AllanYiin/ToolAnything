"""提供工具搜尋與排序功能。"""
from __future__ import annotations

import difflib
import time
from typing import Iterable, List, Optional

from .failure_log import FailureLogManager
from .models import ToolSpec
from .registry import ToolRegistry


class ToolSearchTool:
    """支援依名稱、描述與標籤搜尋工具，並可依失敗分數排序。"""

    def __init__(self, registry: ToolRegistry, failure_log: FailureLogManager) -> None:
        self.registry = registry
        self.failure_log = failure_log

    def _similarity_score(self, query: str, spec: ToolSpec) -> float:
        if not query:
            return 0.0

        target = f"{spec.name} {spec.description} {' '.join(spec.tags)}"
        if query.lower() in target.lower():
            return 1.0
        return difflib.SequenceMatcher(None, query.lower(), target.lower()).ratio()

    def _filter_by_tags(self, specs: Iterable[ToolSpec], tags: Optional[List[str]]) -> list[ToolSpec]:
        if not tags:
            return list(specs)

        tag_set = set(tags)
        return [spec for spec in specs if tag_set.issubset(set(spec.tags))]

    def _filter_by_prefix(self, specs: Iterable[ToolSpec], prefix: Optional[str]) -> list[ToolSpec]:
        if not prefix:
            return list(specs)

        return [spec for spec in specs if spec.name.startswith(prefix)]

    def search(
        self,
        query: str = "",
        tags: Optional[list[str]] = None,
        prefix: Optional[str] = None,
        top_k: int = 10,
        sort_by_failure: bool = True,
        *,
        now: Optional[float] = None,
    ) -> list[ToolSpec]:
        specs = self.registry.list()
        specs = self._filter_by_tags(specs, tags)
        specs = self._filter_by_prefix(specs, prefix)

        snapshot_time = now if now is not None else time.time()
        scored = []
        for spec in specs:
            similarity = self._similarity_score(query, spec)
            failure_score = self.failure_log.failure_score(spec.name, now=snapshot_time)
            scored.append((spec, similarity, failure_score))

        scored.sort(key=lambda item: (-item[1], item[2] if sort_by_failure else 0, item[0].name))
        return [spec for spec, _, _ in scored[:top_k]]


def build_search_tool(searcher: ToolSearchTool):
    """生成可註冊給 LLM 的搜尋工具函式。"""

    def search_tool(
        query: str = "",
        tags: Optional[list[str]] = None,
        prefix: Optional[str] = None,
        top_k: int = 10,
    ) -> list[dict[str, object]]:
        """根據名稱、描述或標籤搜尋可用工具，會將近期失敗較多的項目排後。"""

        results = searcher.search(query=query, tags=tags, prefix=prefix, top_k=top_k)
        return [
            {"name": spec.name, "description": spec.description, "tags": list(spec.tags)}
            for spec in results
        ]

    return search_tool
