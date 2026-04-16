"""Root-scoped filesystem standard tools."""
from __future__ import annotations

import difflib
import hashlib
import json
import shutil
import subprocess
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from toolanything.core import ToolRegistry, ToolSpec

from .options import StandardToolOptions
from .registration import positive_limit, register_callable
from .safety import StandardToolError, ensure_text_file, resolve_under_root


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

        selected_root_id = selected_root_id_or_default(roots, root_id)
        target = resolve_under_root(roots, root_id, relative_path)
        if not target.exists():
            raise StandardToolError("path does not exist")
        if not target.is_dir():
            raise StandardToolError("path is not a directory")
        max_items = positive_limit(limit, default=200)
        entries = []
        root_path = roots[selected_root_id].path
        for child in sorted(target.iterdir(), key=lambda item: item.name.lower()):
            stat = child.stat()
            entries.append(
                {
                    "name": child.name,
                    "relative_path": relative_to_root(child, root_path),
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

        selected_root_id = selected_root_id_or_default(roots, root_id)
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
            payload["sha256"] = sha256_file(target)
        return payload

    def fs_read_text(
        root_id: str = "workspace",
        relative_path: str = ".",
        encoding: str = "utf-8",
        start_line: int = 1,
        max_lines: int = 200,
    ) -> dict[str, Any]:
        """Read a UTF-compatible text file under a configured root with size and line limits."""

        selected_root_id = selected_root_id_or_default(roots, root_id)
        target = resolve_under_root(roots, root_id, relative_path)
        if not target.exists() or not target.is_file():
            raise StandardToolError("path is not a file")
        ensure_text_file(target, max_file_bytes=active_options.max_file_bytes)
        raw = target.read_text(encoding=encoding)
        lines = raw.splitlines()
        start = max(start_line, 1) - 1
        count = positive_limit(max_lines, default=200)
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
            "sha256": sha256_file(target),
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

        selected_root_id = selected_root_id_or_default(roots, root_id)
        target = resolve_under_root(roots, root_id, relative_path)
        if not target.exists():
            raise StandardToolError("path does not exist")
        max_items = min(positive_limit(limit, default=100), active_options.max_search_results)
        if mode == "files":
            matches = search_file_names(
                target,
                root_path=Path(roots[selected_root_id].path),
                glob=glob,
                query=query,
                limit=max_items,
                ignored_dirs=set(active_options.ignored_dirs),
                max_scanned_files=active_options.max_scanned_files,
            )
        elif mode == "content":
            matches = search_file_content(
                target,
                root_path=Path(roots[selected_root_id].path),
                glob=glob,
                query=query,
                limit=max_items,
                max_file_bytes=active_options.max_file_bytes,
                ignored_dirs=set(active_options.ignored_dirs),
                max_scanned_files=active_options.max_scanned_files,
                timeout_sec=active_options.fs_search_timeout_sec,
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
            register_callable(
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

        selected_root_id = selected_root_id_or_default(roots, root_id)
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
            "sha256": sha256_file(target),
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
        selected_root_id = selected_root_id_or_default(roots, root_id)
        target = resolve_under_root(roots, root_id, relative_path, require_writable=True)
        if not target.exists() or not target.is_file():
            raise StandardToolError("target file does not exist")
        ensure_text_file(target, max_file_bytes=active_options.max_file_bytes)
        current_sha = sha256_file(target)
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
            "sha256": sha256_file(target),
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

        selected_root_id = selected_root_id_or_default(roots, root_id)
        target = resolve_under_root(roots, root_id, relative_path, require_writable=True)
        if not target.exists() or not target.is_file():
            raise StandardToolError("target file does not exist")
        ensure_text_file(target, max_file_bytes=active_options.max_file_bytes)
        current_sha = sha256_file(target)
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
            payload["sha256"] = sha256_file(target)
            payload["patched"] = True
        return payload

    def fs_apply_unified_patch(
        root_id: str = "workspace",
        relative_path: str = "",
        patch: str = "",
        expected_sha256: str = "",
        dry_run: bool = True,
        encoding: str = "utf-8",
    ) -> dict[str, Any]:
        """Preview or apply a single-file unified diff; applying requires expected sha256."""

        selected_root_id = selected_root_id_or_default(roots, root_id)
        target = resolve_under_root(roots, root_id, relative_path, require_writable=True)
        if not target.exists() or not target.is_file():
            raise StandardToolError("target file does not exist")
        ensure_text_file(target, max_file_bytes=active_options.max_file_bytes)
        current_sha = sha256_file(target)
        if not dry_run and current_sha != expected_sha256:
            raise StandardToolError("applying a patch requires a matching expected_sha256")
        current = target.read_text(encoding=encoding)
        updated = apply_unified_patch_to_text(current, patch)
        preview = "\n".join(
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
            "diff": preview,
            "previous_sha256": current_sha,
        }
        if not dry_run:
            target.write_text(updated, encoding=encoding)
            payload["sha256"] = sha256_file(target)
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
        (
            fs_apply_unified_patch,
            "standard.fs.apply_unified_patch",
            "Preview or apply a single-file unified diff under a writable configured root.",
            True,
        ),
    )
    for func, name, description, destructive in write_specs:
        specs.append(
            register_callable(
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
                cli_arguments={
                    "content": {"input_mode": "text_or_file"},
                    "patch": {"input_mode": "text_or_file"},
                },
            )
        )
    return specs


def search_file_names(
    target: Path,
    *,
    root_path: Path,
    glob: str,
    query: str,
    limit: int,
    ignored_dirs: set[str] | None = None,
    max_scanned_files: int = 10_000,
) -> list[dict[str, Any]]:
    matches = []
    iterator = target.rglob(glob) if target.is_dir() else [target]
    scanned = 0
    ignored = ignored_dirs if ignored_dirs is not None else DEFAULT_IGNORED_DIRS
    for path in iterator:
        if should_skip_path(path, ignored_dirs=ignored):
            continue
        scanned += 1
        if scanned > max_scanned_files:
            break
        if query.lower() in path.name.lower():
            matches.append(
                {
                    "relative_path": relative_to_root(path, root_path),
                    "type": "directory" if path.is_dir() else "file",
                }
            )
        if len(matches) >= limit:
            break
    return matches


def selected_root_id_or_default(roots: Mapping[str, Any], root_id: str) -> str:
    selected = root_id.strip() if root_id else next(iter(roots))
    if selected not in roots:
        raise StandardToolError(f"unknown root_id: {selected}")
    return selected


def search_file_content(
    target: Path,
    *,
    root_path: Path,
    glob: str,
    query: str,
    limit: int,
    max_file_bytes: int,
    ignored_dirs: set[str] | None = None,
    max_scanned_files: int = 10_000,
    timeout_sec: float = 10.0,
) -> list[dict[str, Any]]:
    if not query:
        raise StandardToolError("query is required for content search")
    rg_matches = search_file_content_with_rg(
        target,
        root_path=root_path,
        glob=glob,
        query=query,
        limit=limit,
        ignored_dirs=ignored_dirs if ignored_dirs is not None else DEFAULT_IGNORED_DIRS,
        max_file_bytes=max_file_bytes,
        timeout_sec=timeout_sec,
    )
    if rg_matches is not None:
        return rg_matches

    matches = []
    files = target.rglob(glob) if target.is_dir() else [target]
    scanned = 0
    ignored = ignored_dirs if ignored_dirs is not None else DEFAULT_IGNORED_DIRS
    for path in files:
        if should_skip_path(path, ignored_dirs=ignored) or not path.is_file():
            continue
        scanned += 1
        if scanned > max_scanned_files:
            break
        try:
            ensure_text_file(path, max_file_bytes=max_file_bytes)
            text = path.read_text(encoding="utf-8", errors="replace")
            for line_no, line in enumerate(text.splitlines(), 1):
                if query.lower() in line.lower():
                    matches.append(
                        {
                            "relative_path": relative_to_root(path, root_path),
                            "line": line_no,
                            "text": line[:500],
                        }
                    )
                    if len(matches) >= limit:
                        return matches
        except (OSError, UnicodeError, StandardToolError):
            continue
    return matches


def search_file_content_with_rg(
    target: Path,
    *,
    root_path: Path,
    glob: str,
    query: str,
    limit: int,
    ignored_dirs: set[str] | frozenset[str],
    max_file_bytes: int,
    timeout_sec: float,
) -> list[dict[str, Any]] | None:
    rg = shutil.which("rg")
    if not rg:
        return None
    command = [
        rg,
        "--json",
        "--ignore-case",
        "--fixed-strings",
        "--glob",
        glob,
        "--max-filesize",
        str(max_file_bytes),
    ]
    for ignored_dir in sorted(ignored_dirs):
        command.extend(["--glob", f"!{ignored_dir}/**"])
        command.extend(["--glob", f"!**/{ignored_dir}/**"])
    command.extend([query, str(target)])
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_sec,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode not in (0, 1):
        return None

    matches: list[dict[str, Any]] = []
    for line in completed.stdout.splitlines():
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if item.get("type") != "match":
            continue
        data = item.get("data", {})
        path_text = data.get("path", {}).get("text")
        line_text = data.get("lines", {}).get("text", "").rstrip("\r\n")
        line_number = data.get("line_number")
        if not path_text or line_number is None:
            continue
        matches.append(
            {
                "relative_path": relative_to_root(Path(path_text), root_path),
                "line": line_number,
                "text": line_text[:500],
                "engine": "rg",
            }
        )
        if len(matches) >= limit:
            break
    return matches


def apply_unified_patch_to_text(current: str, patch: str) -> str:
    current_lines = current.splitlines()
    patch_lines = [line.rstrip("\r") for line in patch.splitlines()]
    output: list[str] = []
    current_index = 0
    saw_hunk = False
    patch_index = 0

    while patch_index < len(patch_lines):
        line = patch_lines[patch_index]
        if not line.startswith("@@"):
            patch_index += 1
            continue

        saw_hunk = True
        old_start = parse_unified_hunk_old_start(line)
        hunk_start_index = old_start - 1
        if hunk_start_index < current_index:
            raise StandardToolError("unified patch hunks overlap or are out of order")
        output.extend(current_lines[current_index:hunk_start_index])
        current_index = hunk_start_index
        patch_index += 1

        while patch_index < len(patch_lines) and not patch_lines[patch_index].startswith("@@"):
            hunk_line = patch_lines[patch_index]
            if hunk_line.startswith("\\"):
                patch_index += 1
                continue
            if not hunk_line:
                raise StandardToolError("invalid unified patch line")
            marker = hunk_line[0]
            text = hunk_line[1:]
            if marker == " ":
                assert_current_line(current_lines, current_index, text)
                output.append(text)
                current_index += 1
            elif marker == "-":
                assert_current_line(current_lines, current_index, text)
                current_index += 1
            elif marker == "+":
                output.append(text)
            else:
                raise StandardToolError("invalid unified patch marker")
            patch_index += 1

    if not saw_hunk:
        raise StandardToolError("unified patch must contain at least one hunk")
    output.extend(current_lines[current_index:])
    suffix = "\n" if current.endswith("\n") else ""
    return "\n".join(output) + suffix


def parse_unified_hunk_old_start(header: str) -> int:
    parts = header.split()
    if len(parts) < 2 or not parts[1].startswith("-"):
        raise StandardToolError("invalid unified patch hunk header")
    old_range = parts[1][1:]
    old_start = old_range.split(",", 1)[0]
    try:
        return int(old_start)
    except ValueError as exc:
        raise StandardToolError("invalid unified patch old range") from exc


def assert_current_line(lines: list[str], index: int, expected: str) -> None:
    if index >= len(lines) or lines[index] != expected:
        raise StandardToolError("unified patch context does not match target file")


def should_skip_path(path: Path, *, ignored_dirs: set[str] | frozenset[str] | None = None) -> bool:
    ignored_dirs = ignored_dirs if ignored_dirs is not None else DEFAULT_IGNORED_DIRS
    return any(part in ignored_dirs for part in path.parts)


def relative_to_root(path: Path, root: str | Path) -> str:
    try:
        return str(path.resolve().relative_to(Path(root).resolve()))
    except ValueError:
        return str(path)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
