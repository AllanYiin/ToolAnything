from __future__ import annotations

import asyncio
import json
from pathlib import Path

from toolanything import InMemorySQLConnectionProvider, SqlSourceSpec, ToolManager


ASSET_DB_PATH = Path(__file__).resolve().parent / "assets" / "analytics.sqlite"


def main() -> None:
    if not ASSET_DB_PATH.exists():
        raise FileNotFoundError(f"找不到範例資料庫：{ASSET_DB_PATH}")

    provider = InMemorySQLConnectionProvider()
    provider.register_sqlite("warehouse.main", database=str(ASSET_DB_PATH))

    manager = ToolManager()
    manager.register_sql_tool(
        SqlSourceSpec(
            name="analytics.top_scores",
            description="示範 SQL source tool",
            connection_ref="warehouse.main",
            query_template=(
                "SELECT id, team, score FROM users WHERE team = :team ORDER BY score DESC"
            ),
            param_schemas={"team": {"type": "string"}},
        ),
        connection_provider=provider,
    )

    result = asyncio.run(manager.invoke("analytics.top_scores", {"team": "alpha"}))
    payload = {
        "example": "SQLite source tool",
        "database": str(ASSET_DB_PATH),
        "query_team": "alpha",
        "result": result,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
