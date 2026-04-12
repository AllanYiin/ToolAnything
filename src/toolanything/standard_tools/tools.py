"""Standard reusable tools for common agent capabilities."""
from __future__ import annotations

import csv
import difflib
import hashlib
import html
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Mapping
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from toolanything.core import ToolRegistry, ToolSpec

from .options import StandardToolOptions
from .safety import (
    DomainPolicy,
    StandardToolError,
    ensure_text_file,
    resolve_under_root,
    validate_url,
)


DEFAULT_IGNORED_DIRS = {
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
}


def register_standard_tools(
    registry: ToolRegistry | None = None,
    options: StandardToolOptions | None = None,
) -> list[ToolSpec]:
    """Register the recommended standard tool bundle."""

    active_registry = registry or ToolRegistry.global_instance()
    active_options = options or StandardToolOptions()
    specs: list[ToolSpec] = []
    specs.extend(register_web_readonly_tools(active_registry, active_options))
    specs.extend(register_filesystem_readonly_tools(active_registry, active_options))
    if active_options.include_write_tools:
        specs.extend(register_filesystem_write_tools(active_registry, active_options))
    specs.extend(register_data_tools(active_registry, active_options))
    return specs


def register_web_readonly_tools(
    registry: ToolRegistry | None = None,
    options: StandardToolOptions | None = None,
) -> list[ToolSpec]:
    active_registry = registry or ToolRegistry.global_instance()
    active_options = options or StandardToolOptions()
    policy = DomainPolicy(
        allowed_domains=active_options.allowed_domains,
        blocked_domains=active_options.blocked_domains,
    )
    specs: list[ToolSpec] = []

    def web_fetch(url: str, max_bytes: int = 0) -> dict[str, Any]:
        """Fetch a web page or text resource with SSRF protections and size limits."""

        limit = _positive_limit(max_bytes, default=active_options.max_web_bytes)
        return _fetch_url(url, options=active_options, policy=policy, max_bytes=limit)

    def web_extract_text(url: str, max_chars: int = 20000) -> dict[str, Any]:
        """Fetch a URL and return readable text extracted from HTML or plain text."""

        response = _fetch_url(
            url,
            options=active_options,
            policy=policy,
            max_bytes=active_options.max_web_bytes,
        )
        text = response["text"]
        title = ""
        if "html" in response["content_type"].lower():
            parser = _HTMLTextExtractor()
            parser.feed(text)
            text = parser.text()
            title = parser.title
        max_chars = _positive_limit(max_chars, default=active_options.max_read_chars)
        return {
            "url": response["url"],
            "final_url": response["final_url"],
            "title": title,
            "text": text[:max_chars],
            "truncated": len(text) > max_chars or response["truncated"],
        }

    def web_extract_links(url: str, limit: int = 100) -> dict[str, Any]:
        """Fetch a URL and return normalized links from HTML anchors."""

        response = _fetch_url(
            url,
            options=active_options,
            policy=policy,
            max_bytes=active_options.max_web_bytes,
        )
        parser = _HTMLLinkExtractor(response["final_url"])
        parser.feed(response["text"])
        max_items = _positive_limit(limit, default=100)
        return {
            "url": response["url"],
            "final_url": response["final_url"],
            "links": parser.links[:max_items],
            "truncated": len(parser.links) > max_items or response["truncated"],
        }

    def web_search(query: str, limit: int = 10) -> dict[str, Any]:
        """Run a configured search provider and normalize its result shape."""

        if active_options.search_provider is None:
            raise StandardToolError(
                "standard.web.search requires StandardToolOptions(search_provider=...)"
            )
        max_items = min(_positive_limit(limit, default=10), active_options.max_search_results)
        raw_results = active_options.search_provider(query, max_items)
        return {
            "query": query,
            "results": _normalize_search_results(raw_results, max_items),
        }

    specs.append(
        _register_callable(
            active_registry,
            web_fetch,
            name="standard.web.fetch",
            description="Fetch an HTTP(S) resource with SSRF protections, domain policy, redirect validation, and byte limits.",
            category="web",
            scopes=("net:http:get",),
            read_only=True,
            open_world=True,
        )
    )
    specs.append(
        _register_callable(
            active_registry,
            web_extract_text,
            name="standard.web.extract_text",
            description="Fetch a URL and extract readable text from HTML or plain text with the standard web safety policy.",
            category="web",
            scopes=("net:http:get",),
            read_only=True,
            open_world=True,
        )
    )
    specs.append(
        _register_callable(
            active_registry,
            web_extract_links,
            name="standard.web.extract_links",
            description="Fetch a URL and extract normalized links from HTML anchors with the standard web safety policy.",
            category="web",
            scopes=("net:http:get",),
            read_only=True,
            open_world=True,
        )
    )
    specs.append(
        _register_callable(
            active_registry,
            web_search,
            name="standard.web.search",
            description="Search the web through a caller-supplied provider and return normalized title/url/snippet results.",
            category="web",
            scopes=("net:search",),
            read_only=True,
            open_world=True,
            extra_metadata={"requires_provider": True},
        )
    )
    return specs


def register_filesystem_readonly_tools(
    registry: ToolRegistry | None = None,
    options: StandardToolOptions | None = None,
) -> list[ToolSpec]:
    active_registry = registry or ToolRegistry.global_instance()
    active_options = options or StandardToolOptions()
    roots = active_options.normalized_roots()
    specs: list[ToolSpec] = []

    def fs_list(root_id: str = "workspace", relative_path: str = ".", limit: int = 200) -> dict[str, Any]:
        """List entries under a configured root without allowing path escape."""

        selected_root_id = _selected_root_id(roots, root_id)
        target = resolve_under_root(roots, root_id, relative_path)
        if not target.exists():
            raise StandardToolError("path does not exist")
        if not target.is_dir():
            raise StandardToolError("path is not a directory")
        max_items = _positive_limit(limit, default=200)
        entries = []
        root_path = roots[selected_root_id].path
        for child in sorted(target.iterdir(), key=lambda item: item.name.lower()):
            stat = child.stat()
            entries.append(
                {
                    "name": child.name,
                    "relative_path": _relative_to_root(child, root_path),
                    "type": "directory" if child.is_dir() else "file",
                    "size": stat.st_size,
                    "modified": stat.st_mtime,
                }
            )
            if len(entries) >= max_items:
                break
        return {
            "root_id": selected_root_id,
            "relative_path": relative_path,
            "entries": entries,
            "truncated": len(entries) >= max_items,
        }

    def fs_stat(root_id: str = "workspace", relative_path: str = ".") -> dict[str, Any]:
        """Return metadata for a file or directory under a configured root."""

        selected_root_id = _selected_root_id(roots, root_id)
        target = resolve_under_root(roots, root_id, relative_path)
        if not target.exists():
            return {"root_id": selected_root_id, "relative_path": relative_path, "exists": False}
        stat = target.stat()
        payload: dict[str, Any] = {
            "root_id": selected_root_id,
            "relative_path": relative_path,
            "exists": True,
            "type": "directory" if target.is_dir() else "file",
            "size": stat.st_size,
            "modified": stat.st_mtime,
        }
        if target.is_file() and stat.st_size <= active_options.max_file_bytes:
            payload["sha256"] = _sha256_file(target)
        return payload

    def fs_read_text(
        root_id: str = "workspace",
        relative_path: str = ".",
        encoding: str = "utf-8",
        start_line: int = 1,
        max_lines: int = 200,
    ) -> dict[str, Any]:
        """Read a UTF-compatible text file under a configured root with size and line limits."""

        selected_root_id = _selected_root_id(roots, root_id)
        target = resolve_under_root(roots, root_id, relative_path)
        if not target.exists() or not target.is_file():
            raise StandardToolError("path is not a file")
        ensure_text_file(target, max_file_bytes=active_options.max_file_bytes)
        raw = target.read_text(encoding=encoding)
        lines = raw.splitlines()
        start = max(start_line, 1) - 1
        count = _positive_limit(max_lines, default=200)
        selected = lines[start : start + count]
        rendered = "\n".join(f"{start + index + 1}|{line}" for index, line in enumerate(selected))
        truncated = start + count < len(lines) or len(rendered) > active_options.max_read_chars
        return {
            "root_id": selected_root_id,
            "relative_path": relative_path,
            "content": rendered[: active_options.max_read_chars],
            "start_line": start + 1,
            "lines_returned": len(selected),
            "line_count": len(lines),
            "truncated": truncated,
            "sha256": _sha256_file(target),
        }

    def fs_search(
        root_id: str = "workspace",
        relative_path: str = ".",
        query: str = "",
        mode: str = "content",
        glob: str = "*",
        limit: int = 100,
    ) -> dict[str, Any]:
        """Search files or file content under a configured root with traversal and binary guards."""

        selected_root_id = _selected_root_id(roots, root_id)
        target = resolve_under_root(roots, root_id, relative_path)
        if not target.exists():
            raise StandardToolError("path does not exist")
        max_items = min(_positive_limit(limit, default=100), active_options.max_search_results)
        if mode == "files":
            matches = _search_file_names(
                target,
                root_path=Path(roots[selected_root_id].path),
                glob=glob,
                query=query,
                limit=max_items,
            )
        elif mode == "content":
            matches = _search_file_content(
                target,
                root_path=Path(roots[selected_root_id].path),
                glob=glob,
                query=query,
                limit=max_items,
                max_file_bytes=active_options.max_file_bytes,
            )
        else:
            raise StandardToolError("mode must be 'content' or 'files'")
        return {"root_id": selected_root_id, "relative_path": relative_path, "mode": mode, "matches": matches}

    for func, name, description in (
        (fs_list, "standard.fs.list", "List files and directories under a configured root."),
        (fs_stat, "standard.fs.stat", "Return safe metadata and optional sha256 for a path under a configured root."),
        (fs_read_text, "standard.fs.read_text", "Read text files under a configured root with size, binary, and line limits."),
        (fs_search, "standard.fs.search", "Search file names or text content under a configured root."),
    ):
        specs.append(
            _register_callable(
                active_registry,
                func,
                name=name,
                description=description,
                category="filesystem",
                scopes=("fs:read",),
                read_only=True,
                open_world=False,
            )
        )
    return specs


def register_filesystem_write_tools(
    registry: ToolRegistry | None = None,
    options: StandardToolOptions | None = None,
) -> list[ToolSpec]:
    active_registry = registry or ToolRegistry.global_instance()
    active_options = options or StandardToolOptions(include_write_tools=True)
    roots = active_options.normalized_roots()
    specs: list[ToolSpec] = []

    def fs_write_create_only(
        root_id: str = "workspace",
        relative_path: str = "",
        content: str = "",
        encoding: str = "utf-8",
    ) -> dict[str, Any]:
        """Create a new text file only when it does not already exist."""

        selected_root_id = _selected_root_id(roots, root_id)
        target = resolve_under_root(roots, root_id, relative_path, require_writable=True)
        if target.exists():
            raise StandardToolError("target already exists")
        ensure_text_file(target, max_file_bytes=active_options.max_file_bytes)
        target.parent.mkdir(parents=True, exist_ok=True)
        encoded = content.encode(encoding)
        if len(encoded) > active_options.max_file_bytes:
            raise StandardToolError("content exceeds configured max_file_bytes")
        target.write_text(content, encoding=encoding)
        return {
            "root_id": selected_root_id,
            "relative_path": relative_path,
            "created": True,
            "sha256": _sha256_file(target),
            "bytes_written": len(encoded),
        }

    def fs_replace_if_match(
        root_id: str = "workspace",
        relative_path: str = "",
        content: str = "",
        expected_sha256: str = "",
        encoding: str = "utf-8",
    ) -> dict[str, Any]:
        """Replace a text file only when its current sha256 matches the caller expectation."""

        if not expected_sha256:
            raise StandardToolError("expected_sha256 is required")
        selected_root_id = _selected_root_id(roots, root_id)
        target = resolve_under_root(roots, root_id, relative_path, require_writable=True)
        if not target.exists() or not target.is_file():
            raise StandardToolError("target file does not exist")
        ensure_text_file(target, max_file_bytes=active_options.max_file_bytes)
        current_sha = _sha256_file(target)
        if current_sha != expected_sha256:
            raise StandardToolError("expected_sha256 does not match current file")
        encoded = content.encode(encoding)
        if len(encoded) > active_options.max_file_bytes:
            raise StandardToolError("content exceeds configured max_file_bytes")
        target.write_text(content, encoding=encoding)
        return {
            "root_id": selected_root_id,
            "relative_path": relative_path,
            "replaced": True,
            "previous_sha256": current_sha,
            "sha256": _sha256_file(target),
            "bytes_written": len(encoded),
        }

    def fs_patch_text(
        root_id: str = "workspace",
        relative_path: str = "",
        old_string: str = "",
        new_string: str = "",
        expected_sha256: str = "",
        replace_all: bool = False,
        dry_run: bool = True,
        encoding: str = "utf-8",
    ) -> dict[str, Any]:
        """Preview or apply a text replacement; applying requires the expected sha256."""

        selected_root_id = _selected_root_id(roots, root_id)
        target = resolve_under_root(roots, root_id, relative_path, require_writable=True)
        if not target.exists() or not target.is_file():
            raise StandardToolError("target file does not exist")
        ensure_text_file(target, max_file_bytes=active_options.max_file_bytes)
        current_sha = _sha256_file(target)
        if not dry_run and current_sha != expected_sha256:
            raise StandardToolError("applying a patch requires a matching expected_sha256")
        if not old_string:
            raise StandardToolError("old_string is required")
        current = target.read_text(encoding=encoding)
        if old_string not in current:
            raise StandardToolError("old_string was not found")
        updated = current.replace(old_string, new_string) if replace_all else current.replace(old_string, new_string, 1)
        diff = "\n".join(
            difflib.unified_diff(
                current.splitlines(),
                updated.splitlines(),
                fromfile=f"{relative_path}:before",
                tofile=f"{relative_path}:after",
                lineterm="",
            )
        )
        payload: dict[str, Any] = {
            "root_id": selected_root_id,
            "relative_path": relative_path,
            "dry_run": dry_run,
            "diff": diff,
            "previous_sha256": current_sha,
        }
        if not dry_run:
            target.write_text(updated, encoding=encoding)
            payload["sha256"] = _sha256_file(target)
            payload["patched"] = True
        return payload

    write_specs = (
        (
            fs_write_create_only,
            "standard.fs.write_create_only",
            "Create a new text file under a writable configured root, failing if it already exists.",
            False,
        ),
        (
            fs_replace_if_match,
            "standard.fs.replace_if_match",
            "Replace a text file under a writable configured root only when expected_sha256 matches.",
            True,
        ),
        (
            fs_patch_text,
            "standard.fs.patch_text",
            "Preview or apply a guarded text replacement under a writable configured root.",
            True,
        ),
    )
    for func, name, description, destructive in write_specs:
        specs.append(
            _register_callable(
                active_registry,
                func,
                name=name,
                description=description,
                category="filesystem",
                scopes=("fs:write",),
                read_only=False,
                open_world=False,
                destructive=destructive,
                requires_approval=True,
            )
        )
    return specs


def register_data_tools(
    registry: ToolRegistry | None = None,
    options: StandardToolOptions | None = None,
) -> list[ToolSpec]:
    active_registry = registry or ToolRegistry.global_instance()
    del options
    specs: list[ToolSpec] = []

    def data_json_parse(text: str) -> dict[str, Any]:
        """Parse JSON text and return the decoded value."""

        value = json.loads(text)
        return {"ok": True, "value": value, "type": type(value).__name__}

    def data_json_validate(text: str, schema_text: str) -> dict[str, Any]:
        """Validate JSON text against a small dependency-free JSON Schema subset."""

        value = json.loads(text)
        schema = json.loads(schema_text)
        errors = _validate_json_subset(value, schema)
        return {"valid": not errors, "errors": errors}

    def data_csv_inspect(text: str, delimiter: str = ",", limit: int = 20) -> dict[str, Any]:
        """Inspect CSV headers, sample rows, and rough shape without writing files."""

        reader = csv.reader(text.splitlines(), delimiter=delimiter)
        rows = list(reader)
        sample_limit = _positive_limit(limit, default=20)
        headers = rows[0] if rows else []
        data_rows = rows[1:] if rows else []
        width = max((len(row) for row in rows), default=0)
        return {
            "headers": headers,
            "row_count": len(data_rows),
            "column_count": width,
            "sample_rows": data_rows[:sample_limit],
            "truncated": len(data_rows) > sample_limit,
        }

    def data_markdown_extract_links(text: str, limit: int = 100) -> dict[str, Any]:
        """Extract inline Markdown links from text."""

        max_items = _positive_limit(limit, default=100)
        links = [
            {"label": match.group(1), "url": match.group(2)}
            for match in re.finditer(r"\[([^\]]+)\]\(([^)]+)\)", text)
        ]
        return {"links": links[:max_items], "truncated": len(links) > max_items}

    for func, name, description in (
        (data_json_parse, "standard.data.json_parse", "Parse JSON text and return the decoded value."),
        (
            data_json_validate,
            "standard.data.json_validate",
            "Validate JSON text against a small dependency-free JSON Schema subset.",
        ),
        (data_csv_inspect, "standard.data.csv_inspect", "Inspect CSV headers, sample rows, and rough shape."),
        (
            data_markdown_extract_links,
            "standard.data.markdown_extract_links",
            "Extract inline Markdown links from text.",
        ),
    ):
        specs.append(
            _register_callable(
                active_registry,
                func,
                name=name,
                description=description,
                category="data",
                scopes=("data:transform",),
                read_only=True,
                open_world=False,
            )
        )
    return specs


def _register_callable(
    registry: ToolRegistry,
    func: Any,
    *,
    name: str,
    description: str,
    category: str,
    scopes: tuple[str, ...],
    read_only: bool,
    open_world: bool,
    destructive: bool = False,
    requires_approval: bool = False,
    extra_metadata: Mapping[str, Any] | None = None,
) -> ToolSpec:
    metadata = {
        "toolanything_stdlib": True,
        "category": category,
        "scopes": list(scopes),
        "side_effect": not read_only,
        "risk_level": "medium" if not read_only else "low",
        "requires_approval": requires_approval,
        "cli": {
            "command_path": _cli_command_path(name),
            "summary": description,
            "arguments": {
                "root_id": {"path_like": False},
                "relative_path": {"path_like": False},
            },
        },
        "mcp_annotations": {
            "readOnlyHint": read_only,
            "destructiveHint": destructive,
            "idempotentHint": read_only,
            "openWorldHint": open_world,
        },
    }
    if extra_metadata:
        metadata.update(dict(extra_metadata))
    spec = ToolSpec.from_function(
        func,
        name=name,
        description=description,
        adapters=("openai", "mcp"),
        tags=("standard", category),
        metadata=metadata,
    )
    registry.register(spec)
    return spec


def _cli_command_path(tool_name: str) -> list[str]:
    parts = [part for part in tool_name.split(".") if part]
    return [part.replace("_", "-") for part in parts] or ["standard", "tool"]


def _fetch_url(
    url: str,
    *,
    options: StandardToolOptions,
    policy: DomainPolicy,
    max_bytes: int,
) -> dict[str, Any]:
    current_url = url
    for _ in range(6):
        validate_url(
            current_url,
            allow_private_network=options.allow_private_network,
            domain_policy=policy,
        )
        request = urllib.request.Request(
            current_url,
            headers={"User-Agent": options.web_user_agent, "Accept": "text/*, application/json, application/xml"},
            method="GET",
        )
        try:
            opener = urllib.request.build_opener(_NoRedirectHandler)
            with opener.open(request, timeout=options.web_timeout_sec) as response:
                raw = response.read(max_bytes + 1)
                content_type = response.headers.get("Content-Type", "")
                charset = response.headers.get_content_charset() or "utf-8"
                text = raw[:max_bytes].decode(charset, errors="replace")
                return {
                    "url": url,
                    "final_url": response.geturl(),
                    "status": response.status,
                    "content_type": content_type,
                    "encoding": charset,
                    "text": text,
                    "bytes_read": min(len(raw), max_bytes),
                    "truncated": len(raw) > max_bytes,
                }
        except urllib.error.HTTPError as exc:
            if exc.code in {301, 302, 303, 307, 308}:
                location = exc.headers.get("Location")
                if not location:
                    raise StandardToolError("redirect response is missing Location") from exc
                current_url = urllib.parse.urljoin(current_url, location)
                continue
            raw = exc.read(max_bytes + 1)
            text = raw[:max_bytes].decode("utf-8", errors="replace")
            return {
                "url": url,
                "final_url": exc.geturl(),
                "status": exc.code,
                "content_type": exc.headers.get("Content-Type", ""),
                "encoding": "utf-8",
                "text": text,
                "bytes_read": min(len(raw), max_bytes),
                "truncated": len(raw) > max_bytes,
            }
        except urllib.error.URLError as exc:
            raise StandardToolError(f"request failed: {exc.reason}") from exc

    raise StandardToolError("too many redirects")


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        return None


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []
        self._in_title = False
        self._title_parts: list[str] = []

    @property
    def title(self) -> str:
        return html.unescape(" ".join(part.strip() for part in self._title_parts if part.strip()))

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        if tag.lower() == "title":
            self._in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if not text:
            return
        if self._in_title:
            self._title_parts.append(text)
        else:
            self._parts.append(text)

    def text(self) -> str:
        return html.unescape("\n".join(self._parts))


class _HTMLLinkExtractor(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__()
        self.base_url = base_url
        self.links: list[dict[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        attributes = dict(attrs)
        href = attributes.get("href")
        if not href:
            return
        normalized = urllib.parse.urljoin(self.base_url, href)
        self.links.append({"url": normalized, "label": attributes.get("title") or ""})


def _normalize_search_results(raw_results: Any, limit: int) -> list[dict[str, Any]]:
    if isinstance(raw_results, dict) and isinstance(raw_results.get("results"), list):
        raw_items = raw_results["results"]
    elif isinstance(raw_results, list):
        raw_items = raw_results
    else:
        raise StandardToolError("search_provider must return a list or {'results': list}")

    normalized: list[dict[str, Any]] = []
    for item in raw_items[:limit]:
        if isinstance(item, str):
            normalized.append({"title": item, "url": "", "snippet": ""})
            continue
        if not isinstance(item, Mapping):
            continue
        normalized.append(
            {
                "title": item.get("title", ""),
                "url": item.get("url") or item.get("link", ""),
                "snippet": item.get("snippet") or item.get("summary", ""),
            }
        )
    return normalized


def _search_file_names(
    target: Path,
    *,
    root_path: Path,
    glob: str,
    query: str,
    limit: int,
) -> list[dict[str, Any]]:
    matches = []
    iterator = target.rglob(glob) if target.is_dir() else [target]
    for path in iterator:
        if _should_skip_path(path):
            continue
        if query.lower() in path.name.lower():
            matches.append(
                {
                    "relative_path": _relative_to_root(path, root_path),
                    "type": "directory" if path.is_dir() else "file",
                }
            )
        if len(matches) >= limit:
            break
    return matches


def _selected_root_id(roots: Mapping[str, Any], root_id: str) -> str:
    selected = root_id.strip() if root_id else next(iter(roots))
    if selected not in roots:
        raise StandardToolError(f"unknown root_id: {selected}")
    return selected


def _search_file_content(
    target: Path,
    *,
    root_path: Path,
    glob: str,
    query: str,
    limit: int,
    max_file_bytes: int,
) -> list[dict[str, Any]]:
    if not query:
        raise StandardToolError("query is required for content search")
    matches = []
    files = target.rglob(glob) if target.is_dir() else [target]
    for path in files:
        if _should_skip_path(path) or not path.is_file():
            continue
        try:
            ensure_text_file(path, max_file_bytes=max_file_bytes)
            text = path.read_text(encoding="utf-8", errors="replace")
            for line_no, line in enumerate(text.splitlines(), 1):
                if query.lower() in line.lower():
                    matches.append(
                        {
                            "relative_path": _relative_to_root(path, root_path),
                            "line": line_no,
                            "text": line[:500],
                        }
                    )
                    if len(matches) >= limit:
                        return matches
        except (OSError, UnicodeError, StandardToolError):
            continue
    return matches


def _should_skip_path(path: Path) -> bool:
    return any(part in DEFAULT_IGNORED_DIRS for part in path.parts)


def _relative_to_root(path: Path, root: str | Path) -> str:
    try:
        return str(path.resolve().relative_to(Path(root).resolve()))
    except ValueError:
        return str(path)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _positive_limit(value: int, *, default: int) -> int:
    if value <= 0:
        return default
    return value


def _validate_json_subset(value: Any, schema: Mapping[str, Any], path: str = "$") -> list[str]:
    errors: list[str] = []
    expected_type = schema.get("type")
    if expected_type and not _json_type_matches(value, expected_type):
        errors.append(f"{path}: expected {expected_type}, got {type(value).__name__}")
        return errors

    if isinstance(value, dict):
        for field in schema.get("required", []):
            if field not in value:
                errors.append(f"{path}.{field}: required")
        properties = schema.get("properties", {})
        if isinstance(properties, Mapping):
            for field, field_schema in properties.items():
                if field in value and isinstance(field_schema, Mapping):
                    errors.extend(_validate_json_subset(value[field], field_schema, f"{path}.{field}"))

    if isinstance(value, list) and isinstance(schema.get("items"), Mapping):
        item_schema = schema["items"]
        for index, item in enumerate(value):
            errors.extend(_validate_json_subset(item, item_schema, f"{path}[{index}]"))
    return errors


def _json_type_matches(value: Any, expected_type: Any) -> bool:
    if isinstance(expected_type, list):
        return any(_json_type_matches(value, item) for item in expected_type)
    if expected_type == "null":
        return value is None
    if expected_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    mapping = {
        "array": list,
        "boolean": bool,
        "object": dict,
        "string": str,
    }
    target = mapping.get(expected_type)
    return isinstance(value, target) if target else True
