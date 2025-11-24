from toolanything.state import StateManager


def test_state_manager_is_isolated_per_user():
    manager = StateManager()
    manager.set("u1", "key", 1)
    manager.set("u2", "key", 2)
    assert manager.get("u1")["key"] == 1
    assert manager.get("u2")["key"] == 2


def test_state_manager_clear():
    manager = StateManager()
    manager.set("u1", "key", 10)
    manager.clear("u1")
    assert manager.get("u1") == {}
