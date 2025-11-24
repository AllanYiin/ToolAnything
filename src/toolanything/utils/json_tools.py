from __future__ import annotations

import json
from typing import Any


def to_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


def from_json(raw: str) -> Any:
    return json.loads(raw)
