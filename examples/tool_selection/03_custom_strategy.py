"""Tool selection: 自訂策略並注入 ToolSearchTool。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from examples.tool_selection.custom_strategy import (
    CheapestFirstStrategy,
    build_registry,
    main,
)


if __name__ == "__main__":
    main()
