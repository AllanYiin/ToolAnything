"""Tool selection: 用 constraints 篩選工具的跨平台範例。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from examples.tool_selection.constraints_search import main


if __name__ == "__main__":
    main()
