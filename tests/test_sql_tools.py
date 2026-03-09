from __future__ import annotations

import sqlite3
import time
from pathlib import Path

import pytest

from toolanything.core import (
    InMemorySQLConnectionProvider,
    SqlSourceSpec,
    ToolManager,
    ToolRegistry,
    build_sql_input_schema,
    register_sql_tool,
)
from toolanything.exceptions import ToolError


def _prepare_db(path: Path) -> None:
    connection = sqlite3.connect(path)
    try:
        cursor = connection.cursor()
        cursor.execute("CREATE TABLE users(id INTEGER PRIMARY KEY, team TEXT, score INTEGER)")
        cursor.executemany(
            "INSERT INTO users(team, score) VALUES(?, ?)",
            [
                ("alpha", 10),
                ("alpha", 20),
                ("beta", 30),
                ("alpha", 40),
            ],
        )
        connection.commit()
    finally:
        connection.close()


def test_build_sql_input_schema_from_named_placeholders():
    source = SqlSourceSpec(
        name="analytics.top_scores",
        description="查詢分數",
        connection_ref="warehouse.main",
        query_template="SELECT id, score FROM users WHERE team = :team AND score >= :min_score",
        param_schemas={
            "team": {"type": "string"},
            "min_score": {"type": "integer"},
        },
    )

    assert build_sql_input_schema(source) == {
        "type": "object",
        "properties": {
            "team": {"type": "string"},
            "min_score": {"type": "integer"},
        },
        "required": ["team", "min_score"],
        "additionalProperties": False,
    }


@pytest.mark.asyncio
async def test_register_sql_tool_executes_successfully(tmp_path: Path):
    db_path = tmp_path / "scores.db"
    _prepare_db(db_path)

    provider = InMemorySQLConnectionProvider()
    provider.register_sqlite("warehouse.main", database=str(db_path))
    registry = ToolRegistry()
    register_sql_tool(
        registry,
        SqlSourceSpec(
            name="analytics.top_scores",
            description="查詢分數",
            connection_ref="warehouse.main",
            query_template=(
                "SELECT id, score FROM users WHERE team = :team AND score >= :min_score ORDER BY score"
            ),
            param_schemas={
                "team": {"type": "string"},
                "min_score": {"type": "integer"},
            },
            max_rows=10,
        ),
        connection_provider=provider,
    )

    result = await registry.invoke_tool_async(
        "analytics.top_scores",
        arguments={"team": "alpha", "min_score": 15},
    )

    assert result == {
        "columns": ["id", "score"],
        "rows": [{"id": 2, "score": 20}, {"id": 4, "score": 40}],
        "row_count": 2,
        "truncated": False,
    }
    with pytest.raises(TypeError):
        registry.get("analytics.top_scores")


@pytest.mark.asyncio
async def test_tool_manager_register_sql_tool(tmp_path: Path):
    db_path = tmp_path / "scores.db"
    _prepare_db(db_path)

    provider = InMemorySQLConnectionProvider()
    provider.register_sqlite("warehouse.main", database=str(db_path))
    manager = ToolManager(registry=ToolRegistry())
    manager.register_sql_tool(
        SqlSourceSpec(
            name="analytics.by_team",
            description="依團隊查詢",
            connection_ref="warehouse.main",
            query_template="SELECT id, team FROM users WHERE team = :team ORDER BY id",
            param_schemas={"team": {"type": "string"}},
        ),
        connection_provider=provider,
    )

    result = await manager.invoke("analytics.by_team", {"team": "beta"})
    assert result["rows"] == [{"id": 3, "team": "beta"}]


@pytest.mark.asyncio
async def test_sql_tool_blocks_write_queries_even_with_parameters(tmp_path: Path):
    db_path = tmp_path / "scores.db"
    _prepare_db(db_path)

    provider = InMemorySQLConnectionProvider()
    provider.register_sqlite("warehouse.main", database=str(db_path))
    registry = ToolRegistry()
    register_sql_tool(
        registry,
        SqlSourceSpec(
            name="analytics.bad_update",
            description="不允許寫入",
            connection_ref="warehouse.main",
            query_template="UPDATE users SET score = :score WHERE id = :id",
            param_schemas={"score": {"type": "integer"}, "id": {"type": "integer"}},
            read_only=True,
        ),
        connection_provider=provider,
    )

    with pytest.raises(ToolError) as exc_info:
        await registry.invoke_tool_async("analytics.bad_update", arguments={"score": 99, "id": 1})

    assert exc_info.value.to_dict()["type"] == "sql_read_only_violation"


@pytest.mark.asyncio
async def test_sql_tool_truncates_large_result_sets(tmp_path: Path):
    db_path = tmp_path / "scores.db"
    _prepare_db(db_path)

    provider = InMemorySQLConnectionProvider()
    provider.register_sqlite("warehouse.main", database=str(db_path))
    registry = ToolRegistry()
    register_sql_tool(
        registry,
        SqlSourceSpec(
            name="analytics.all_users",
            description="查詢全部",
            connection_ref="warehouse.main",
            query_template="SELECT id, team FROM users ORDER BY id",
            max_rows=2,
        ),
        connection_provider=provider,
    )

    result = await registry.invoke_tool_async("analytics.all_users")
    assert result == {
        "columns": ["id", "team"],
        "rows": [{"id": 1, "team": "alpha"}, {"id": 2, "team": "alpha"}],
        "row_count": 2,
        "truncated": True,
    }


@pytest.mark.asyncio
async def test_sql_tool_maps_connection_errors():
    provider = InMemorySQLConnectionProvider()
    registry = ToolRegistry()
    register_sql_tool(
        registry,
        SqlSourceSpec(
            name="analytics.missing_connection",
            description="缺少連線",
            connection_ref="warehouse.missing",
            query_template="SELECT 1 AS ok",
        ),
        connection_provider=provider,
    )

    with pytest.raises(ToolError) as exc_info:
        await registry.invoke_tool_async("analytics.missing_connection")

    assert exc_info.value.to_dict()["type"] == "sql_connection_error"


@pytest.mark.asyncio
async def test_sql_tool_maps_timeout(tmp_path: Path):
    db_path = tmp_path / "scores.db"
    connection = sqlite3.connect(db_path)
    try:
        connection.create_function("sleep_ms", 1, lambda ms: (time.sleep(ms / 1000), ms)[1])
        connection.execute("CREATE TABLE delays(id INTEGER PRIMARY KEY)")
        connection.executemany("INSERT INTO delays(id) VALUES(?)", [(1,), (2,), (3,)])
        connection.commit()
    finally:
        connection.close()

    class SleepyProvider(InMemorySQLConnectionProvider):
        def connect(self, connection_ref: str, *, read_only: bool, timeout_sec: float):
            connection = super().connect(
                connection_ref,
                read_only=read_only,
                timeout_sec=timeout_sec,
            )
            connection.create_function("sleep_ms", 1, lambda ms: (time.sleep(ms / 1000), ms)[1])
            return connection

    provider = SleepyProvider()
    provider.register_sqlite("warehouse.main", database=str(db_path))
    registry = ToolRegistry()
    register_sql_tool(
        registry,
        SqlSourceSpec(
            name="analytics.slow_query",
            description="慢查詢",
            connection_ref="warehouse.main",
            query_template="SELECT sleep_ms(:delay_ms) AS waited FROM delays",
            param_schemas={"delay_ms": {"type": "integer"}},
            timeout_sec=0.05,
        ),
        connection_provider=provider,
    )

    with pytest.raises(ToolError) as exc_info:
        await registry.invoke_tool_async("analytics.slow_query", arguments={"delay_ms": 100})

    assert exc_info.value.to_dict()["type"] == "sql_timeout"
