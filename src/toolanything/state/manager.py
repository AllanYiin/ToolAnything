"""多使用者狀態管理。"""
from __future__ import annotations

import asyncio
import json
import os
from typing import Any, Dict, Optional


class StateManager:
    def __init__(self) -> None:
        self._storage: Dict[str, Dict[str, Any]] = {}

    def get(self, user_id: str) -> Dict[str, Any]:
        if user_id not in self._storage:
            self._storage[user_id] = {}
        return self._storage[user_id]

    def set(self, user_id: str, key: str, value: Any) -> None:
        bucket = self.get(user_id)
        bucket[key] = value

    def clear(self, user_id: str) -> None:
        self._storage[user_id] = {}

    def clear_all(self) -> None:
        self._storage = {}


class BasePersistentBackend:
    async def get(self, user_id: str) -> Dict[str, Any]:  # pragma: no cover - interface
        raise NotImplementedError

    async def set(self, user_id: str, key: str, value: Any) -> Dict[str, Any]:  # pragma: no cover - interface
        raise NotImplementedError

    async def clear(self, user_id: str) -> None:  # pragma: no cover - interface
        raise NotImplementedError

    async def clear_all(self) -> None:  # pragma: no cover - interface
        raise NotImplementedError


class _DictBackend(BasePersistentBackend):
    """使用記憶體模擬的後端，作為 Redis/Database 的示意實作。"""

    def __init__(self) -> None:
        self._storage: Dict[str, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    async def get(self, user_id: str) -> Dict[str, Any]:
        async with self._lock:
            if user_id not in self._storage:
                self._storage[user_id] = {}
            return dict(self._storage[user_id])

    async def set(self, user_id: str, key: str, value: Any) -> Dict[str, Any]:
        async with self._lock:
            bucket = self._storage.setdefault(user_id, {})
            bucket[key] = value
            return dict(bucket)

    async def clear(self, user_id: str) -> None:
        async with self._lock:
            self._storage[user_id] = {}

    async def clear_all(self) -> None:
        async with self._lock:
            self._storage = {}


class RedisBackend(_DictBackend):
    """示意的 Redis 後端，使用 asyncio 友善的內存模擬。"""


class DatabaseBackend(_DictBackend):
    """示意的 Database 後端，使用 asyncio 友善的內存模擬。"""


class FileBackend(BasePersistentBackend):
    """透過檔案儲存狀態。"""

    def __init__(self, path: Optional[str] = None) -> None:
        self.path = path or ".toolanything_state.json"
        self._lock = asyncio.Lock()
        self._ensure_file_initialized()

    def _ensure_file_initialized(self) -> None:
        if not os.path.exists(self.path):
            with open(self.path, "w", encoding="utf-8") as fp:
                json.dump({}, fp)

    async def _read(self) -> Dict[str, Dict[str, Any]]:
        def _load() -> Dict[str, Dict[str, Any]]:
            with open(self.path, "r", encoding="utf-8") as fp:
                return json.load(fp)

        return await asyncio.to_thread(_load)

    async def _write(self, data: Dict[str, Dict[str, Any]]) -> None:
        def _dump() -> None:
            with open(self.path, "w", encoding="utf-8") as fp:
                json.dump(data, fp)

        await asyncio.to_thread(_dump)

    async def get(self, user_id: str) -> Dict[str, Any]:
        async with self._lock:
            data = await self._read()
            bucket = data.setdefault(user_id, {})
            await self._write(data)
            return dict(bucket)

    async def set(self, user_id: str, key: str, value: Any) -> Dict[str, Any]:
        async with self._lock:
            data = await self._read()
            bucket = data.setdefault(user_id, {})
            bucket[key] = value
            await self._write(data)
            return dict(bucket)

    async def clear(self, user_id: str) -> None:
        async with self._lock:
            data = await self._read()
            data[user_id] = {}
            await self._write(data)

    async def clear_all(self) -> None:
        async with self._lock:
            await self._write({})


class PersistentStateManager(StateManager):
    """支援多種後端且提供異步操作的狀態管理器。"""

    def __init__(self, backend: str = "redis", **backend_kwargs: Any) -> None:
        super().__init__()
        normalized = backend.lower()
        if normalized == "redis":
            self._backend: BasePersistentBackend = RedisBackend()
        elif normalized in {"db", "database"}:
            self._backend = DatabaseBackend()
        elif normalized == "file":
            self._backend = FileBackend(**backend_kwargs)
        else:
            raise ValueError(f"Unsupported backend: {backend}")

    async def get(self, user_id: str) -> Dict[str, Any]:
        return await self._backend.get(user_id)

    async def set(self, user_id: str, key: str, value: Any) -> Dict[str, Any]:
        return await self._backend.set(user_id, key, value)

    async def clear(self, user_id: str) -> None:
        await self._backend.clear(user_id)

    async def clear_all(self) -> None:
        await self._backend.clear_all()
