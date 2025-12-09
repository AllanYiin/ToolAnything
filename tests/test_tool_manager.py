from toolanything.core.registry import ToolRegistry
from toolanything.core.tool_manager import ToolManager


def test_tool_manager_uses_lazy_global_registry():
    # 確保尚未初始化全域 Registry。
    ToolRegistry._global_instance = None  # type: ignore[attr-defined]

    manager = ToolManager()

    assert ToolRegistry._global_instance is not None  # type: ignore[attr-defined]
    assert manager.registry is ToolRegistry.global_instance()

    # 清理避免影響其他測試。
    ToolRegistry._global_instance = None  # type: ignore[attr-defined]
