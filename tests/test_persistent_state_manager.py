import asyncio

import pytest

from toolanything.state import PersistentStateManager


def test_persistent_state_manager_async_set_get():
    async def _run():
        manager = PersistentStateManager(backend="redis")

        await manager.set("user-a", "token", 123)
        await manager.set("user-b", "token", 456)

        user_a = await manager.get("user-a")
        user_b = await manager.get("user-b")

        assert user_a == {"token": 123}
        assert user_b == {"token": 456}

    asyncio.run(_run())


def test_persistent_state_manager_supports_file_backend(tmp_path):
    async def _run() -> None:
        storage_path = tmp_path / "state.json"
        manager = PersistentStateManager(backend="file", path=str(storage_path))

        await manager.set("user-a", "feature", True)

        # 重新初始化以驗證檔案有真正寫入
        reloaded = PersistentStateManager(backend="file", path=str(storage_path))
        state = await reloaded.get("user-a")

        assert state == {"feature": True}

    asyncio.run(_run())


def test_persistent_state_manager_clear_and_clear_all():
    async def _run() -> None:
        manager = PersistentStateManager(backend="database")

        await manager.set("user-a", "token", "aaa")
        await manager.clear("user-a")
        assert await manager.get("user-a") == {}

        await manager.set("user-a", "token", "aaa")
        await manager.set("user-b", "token", "bbb")
        await manager.clear_all()

        assert await manager.get("user-a") == {}
        assert await manager.get("user-b") == {}

    asyncio.run(_run())


def test_persistent_state_manager_unsupported_backend():
    with pytest.raises(ValueError):
        PersistentStateManager(backend="unsupported")

