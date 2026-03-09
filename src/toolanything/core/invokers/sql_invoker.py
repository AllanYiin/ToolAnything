"""SQL source invoker."""
from __future__ import annotations

import asyncio
import re
import sqlite3
import time
from typing import Any, Mapping

from ...exceptions import ToolError
from ..runtime_types import ExecutionContext, InvocationResult, StreamEmitter
from ..source_specs import SqlSourceSpec
from ..sql_connections import InMemorySQLConnectionProvider, SQLConnectionProvider

_NAMED_PARAM_PATTERN = re.compile(r"(?<!:):([A-Za-z_][A-Za-z0-9_]*)")
_WRITE_PREFIX_PATTERN = re.compile(
    r"^\s*(INSERT|UPDATE|DELETE|REPLACE|CREATE|DROP|ALTER|TRUNCATE|VACUUM|ATTACH|DETACH|PRAGMA|BEGIN|COMMIT|ROLLBACK)\b",
    re.IGNORECASE,
)


def extract_sql_params(query_template: str) -> tuple[str, ...]:
    seen: list[str] = []
    for match in _NAMED_PARAM_PATTERN.findall(query_template):
        if match not in seen:
            seen.append(match)
    return tuple(seen)


class SqlInvoker:
    """用 parameterized query 執行 read-safe SQL 工具。"""

    def __init__(
        self,
        source: SqlSourceSpec,
        *,
        connection_provider: SQLConnectionProvider | None = None,
    ) -> None:
        self.source = source
        self.connection_provider = connection_provider or InMemorySQLConnectionProvider()

    def _validate_query(self) -> None:
        normalized = self.source.query_template.strip().rstrip(";")
        if ";" in normalized:
            raise ToolError(
                "query_template 不允許多重 SQL statements",
                error_type="sql_validation_error",
                data={"reason": "multiple_statements"},
            )

        if self.source.read_only and _WRITE_PREFIX_PATTERN.search(self.source.query_template):
            raise ToolError(
                "read_only SQL tool 不允許寫入或 DDL 指令",
                error_type="sql_read_only_violation",
                data={"query_template": self.source.query_template},
            )

    def _build_params(self, arguments: Mapping[str, Any]) -> dict[str, Any]:
        params = {}
        for name in extract_sql_params(self.source.query_template):
            if name not in arguments:
                raise ToolError(
                    f"缺少必要 SQL 參數: {name}",
                    error_type="validation_error",
                    data={"location": "sql", "field": name},
                )
            params[name] = arguments[name]
        return params

    def _run_query(self, params: Mapping[str, Any]) -> dict[str, Any]:
        self._validate_query()
        connection = self.connection_provider.connect(
            self.source.connection_ref,
            read_only=self.source.read_only,
            timeout_sec=self.source.timeout_sec,
        )
        deadline = time.monotonic() + self.source.timeout_sec

        try:
            if isinstance(connection, sqlite3.Connection):
                connection.set_progress_handler(
                    lambda: 1 if time.monotonic() >= deadline else 0,
                    1000,
                )

            cursor = connection.execute(self.source.query_template, params)
            rows = cursor.fetchmany(self.source.max_rows + 1)
            columns = [item[0] for item in (cursor.description or [])]
            truncated = len(rows) > self.source.max_rows
            limited_rows = rows[: self.source.max_rows]
            serialized_rows = [dict(row) for row in limited_rows]
            return {
                "columns": columns,
                "rows": serialized_rows,
                "row_count": len(serialized_rows),
                "truncated": truncated,
            }
        except sqlite3.OperationalError as exc:
            if "interrupted" in str(exc).lower():
                raise ToolError(
                    "SQL 查詢逾時",
                    error_type="sql_timeout",
                    data={"timeout_sec": self.source.timeout_sec},
                ) from exc
            raise ToolError(
                "SQL 執行失敗",
                error_type="sql_execution_error",
                data={"message": str(exc)},
            ) from exc
        except sqlite3.Error as exc:
            raise ToolError(
                "SQL 執行失敗",
                error_type="sql_execution_error",
                data={"message": str(exc)},
            ) from exc
        finally:
            if isinstance(connection, sqlite3.Connection):
                connection.set_progress_handler(None, 0)
            connection.close()

    async def invoke(
        self,
        input: Mapping[str, Any] | None,
        context: ExecutionContext,
        stream: StreamEmitter | None = None,
        *,
        inject_context: bool = False,
        context_arg: str = "context",
    ) -> InvocationResult:
        del context, stream, inject_context, context_arg
        params = self._build_params(dict(input or {}))
        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(self._run_query, params),
                timeout=self.source.timeout_sec,
            )
        except asyncio.TimeoutError as exc:
            raise ToolError(
                "SQL 查詢逾時",
                error_type="sql_timeout",
                data={"timeout_sec": self.source.timeout_sec},
            ) from exc
        return InvocationResult(output=result)


__all__ = ["SqlInvoker", "extract_sql_params"]
