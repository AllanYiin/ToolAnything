"""Configuration for ToolAnything standard tools."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Protocol


SearchProvider = Callable[[str, int], Any]
BrowserReadonlyProvider = Callable[[str, str, int], Any]


class StandardSearchProvider(Protocol):
    def __call__(self, query: str, limit: int) -> Any:
        """Return a list of search results or {'results': [...]}."""


@dataclass(frozen=True)
class StandardSearchResult:
    title: str
    url: str
    snippet: str = ""
    source: str = ""
    published_at: str = ""
    rank: int | None = None


@dataclass(frozen=True)
class StandardToolRoot:
    """Named filesystem root exposed to standard filesystem tools."""

    root_id: str
    path: str | Path
    writable: bool = False

    def normalized(self) -> "StandardToolRoot":
        root_id = self.root_id.strip()
        if not root_id:
            raise ValueError("root_id must not be empty")
        return StandardToolRoot(
            root_id=root_id,
            path=Path(self.path).expanduser().resolve(),
            writable=self.writable,
        )


@dataclass(frozen=True)
class StandardToolOptions:
    """Runtime policy for reusable cross-agent tools."""

    roots: Mapping[str, str | Path | StandardToolRoot] | Sequence[StandardToolRoot] | None = None
    include_write_tools: bool = False
    allowed_domains: tuple[str, ...] = ()
    blocked_domains: tuple[str, ...] = ()
    allow_private_network: bool = False
    max_file_bytes: int = 2_000_000
    max_read_chars: int = 100_000
    max_search_results: int = 200
    max_web_bytes: int = 2_000_000
    web_timeout_sec: float = 20.0
    web_user_agent: str = "ToolAnything-StandardTools/1.0"
    web_max_redirects: int = 6
    serpapi_api_key_env: str = "SERPAPI_KEY"
    allowed_content_types: tuple[str, ...] = (
        "text/",
        "application/json",
        "application/xml",
        "application/xhtml+xml",
        "application/rss+xml",
        "application/atom+xml",
    )
    blocked_content_types: tuple[str, ...] = (
        "application/octet-stream",
        "application/pdf",
        "image/",
        "audio/",
        "video/",
    )
    ignored_dirs: tuple[str, ...] = (
        ".git",
        ".hg",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".svn",
        ".venv",
        "__pycache__",
        "build",
        "dist",
        "node_modules",
    )
    max_scanned_files: int = 10_000
    fs_search_timeout_sec: float = 10.0
    search_provider: SearchProvider | StandardSearchProvider | None = None
    browser_readonly_provider: BrowserReadonlyProvider | None = None
    include_browser_tools: bool = False

    def normalized_roots(self) -> dict[str, StandardToolRoot]:
        roots = self.roots
        if roots is None:
            root = StandardToolRoot("workspace", Path.cwd(), writable=self.include_write_tools).normalized()
            return {root.root_id: root}

        normalized: dict[str, StandardToolRoot] = {}
        if isinstance(roots, Mapping):
            for root_id, value in roots.items():
                root = (
                    value
                    if isinstance(value, StandardToolRoot)
                    else StandardToolRoot(root_id, value, writable=self.include_write_tools)
                ).normalized()
                normalized[root.root_id] = root
        else:
            for value in roots:
                root = value.normalized()
                normalized[root.root_id] = root

        if not normalized:
            raise ValueError("at least one root must be configured")
        return normalized
