"""SQL connection provider abstraction."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import quote

from ..exceptions import ToolError


@dataclass(frozen=True)
class SqlConnectionConfig:
    """Connection reference configuration."""

    driver: str
    database: str
    uri: bool = False
    kwargs: dict[str, Any] | None = None


class SQLConnectionProvider(Protocol):
    """取得資料庫連線的抽象介面。"""

    def connect(
        self,
        connection_ref: str,
        *,
        read_only: bool,
        timeout_sec: float,
    ) -> Any:
        ...


class InMemorySQLConnectionProvider:
    """簡單的 connection_ref -> config provider。"""

    def __init__(self) -> None:
        self._configs: dict[str, SqlConnectionConfig] = {}

    def register_sqlite(
        self,
        connection_ref: str,
        *,
        database: str,
        uri: bool = False,
        **kwargs: Any,
    ) -> None:
        self._configs[connection_ref] = SqlConnectionConfig(
            driver="sqlite",
            database=database,
            uri=uri,
            kwargs=kwargs or None,
        )

    def connect(
        self,
        connection_ref: str,
        *,
        read_only: bool,
        timeout_sec: float,
    ) -> sqlite3.Connection:
        if connection_ref not in self._configs:
            raise ToolError(
                f"找不到 SQL connection_ref: {connection_ref}",
                error_type="sql_connection_error",
                data={"connection_ref": connection_ref},
            )

        config = self._configs[connection_ref]
        if config.driver != "sqlite":
            raise ToolError(
                f"目前尚未支援 SQL driver: {config.driver}",
                error_type="sql_connection_error",
                data={"connection_ref": connection_ref, "driver": config.driver},
            )

        connect_kwargs = dict(config.kwargs or {})
        database = config.database
        uri = config.uri

        if read_only:
            if not uri:
                database = Path(database).resolve().as_posix()
                database = f"file:{quote(database, safe='/:')}" + "?mode=ro"
                uri = True
            elif "mode=ro" not in database:
                separator = "&" if "?" in database else "?"
                database = f"{database}{separator}mode=ro"

        try:
            connection = sqlite3.connect(
                database,
                timeout=timeout_sec,
                uri=uri,
                check_same_thread=False,
                **connect_kwargs,
            )
        except sqlite3.Error as exc:
            raise ToolError(
                "資料庫連線失敗",
                error_type="sql_connection_error",
                data={"connection_ref": connection_ref, "message": str(exc)},
            ) from exc

        connection.row_factory = sqlite3.Row
        return connection


__all__ = ["SqlConnectionConfig", "SQLConnectionProvider", "InMemorySQLConnectionProvider"]
