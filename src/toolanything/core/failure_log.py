"""失敗次數紀錄與衰減計算管理器。"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, Optional


class FailureLogManager:
    """紀錄工具失敗次數並計算排序用的衰減分數。"""

    def __init__(self, path: str | Path | None = None, *, decay_base: float = 0.9, max_recent: int = 20) -> None:
        self.path = Path(path) if path else None
        self.decay_base = decay_base
        self.max_recent = max_recent
        self._records: Dict[str, Dict[str, Any]] = {}

        if self.path and self.path.exists():
            self._load()

    def _load(self) -> None:
        content = self.path.read_text(encoding="utf-8") if self.path else ""
        if not content:
            return
        self._records = json.loads(content)

    def _save(self) -> None:
        if not self.path:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._records, ensure_ascii=False, indent=2), encoding="utf-8")

    def record_failure(self, tool_name: str, *, timestamp: Optional[float] = None) -> None:
        """記錄一次失敗，並更新相關統計資訊。"""

        now = timestamp if timestamp is not None else time.time()
        record = self._records.setdefault(tool_name, {"count": 0, "last_failed": 0.0, "recent": []})
        record["count"] += 1
        record["last_failed"] = now
        record["recent"].append(now)
        if len(record["recent"]) > self.max_recent:
            record["recent"] = record["recent"][-self.max_recent :]
        self._save()

    def get_record(self, tool_name: str) -> Dict[str, Any] | None:
        """取得指定工具的統計資料。"""

        return self._records.get(tool_name)

    def failure_score(self, tool_name: str, *, now: Optional[float] = None) -> float:
        """計算排序用的衰減失敗分數，未有紀錄時回傳 0。"""

        record = self._records.get(tool_name)
        if not record:
            return 0.0

        current = now if now is not None else time.time()
        decay_factor = self.decay_base ** max(current - record["last_failed"], 0)
        return float(record["count"]) * decay_factor

    def reset(self) -> None:
        """清除所有紀錄。"""

        self._records.clear()
        self._save()
