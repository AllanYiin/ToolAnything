from __future__ import annotations

import asyncio
import json
import sqlite3
import tempfile
from pathlib import Path

from toolanything import InMemorySQLConnectionProvider, SqlSourceSpec, ToolManager


def _prepare_db(path: Path) -> None:
    connection = sqlite3.connect(path)
    try:
        connection.execute("CREATE TABLE users(id INTEGER PRIMARY KEY, team TEXT, score INTEGER)")
        connection.executemany(
            "INSERT INTO users(team, score) VALUES(?, ?)",
            [("alpha", 10), ("alpha", 20), ("beta", 30)],
        )
        connection.commit()
    finally:
        connection.close()


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "analytics.db"
        _prepare_db(db_path)

        provider = InMemorySQLConnectionProvider()
        provider.register_sqlite("warehouse.main", database=str(db_path))

        manager = ToolManager()
        manager.register_sql_tool(
            SqlSourceSpec(
                name="analytics.top_scores",
                description="示範 SQL source tool",
                connection_ref="warehouse.main",
                query_template=(
                    "SELECT id, score FROM users WHERE team = :team ORDER BY score DESC"
                ),
                param_schemas={"team": {"type": "string"}},
            ),
            connection_provider=provider,
        )

        result = asyncio.run(manager.invoke("analytics.top_scores", {"team": "alpha"}))
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
