"""Standard tool bundle facade.

Concrete tool families live in dedicated modules:
- data.py
- filesystem.py
- web.py
"""
from __future__ import annotations

from toolanything.core import ToolRegistry, ToolSpec

from .data import register_data_tools
from .filesystem import register_filesystem_readonly_tools, register_filesystem_write_tools
from .options import StandardToolOptions
from .web import register_web_readonly_tools


def register_standard_tools(
    registry: ToolRegistry | None = None,
    options: StandardToolOptions | None = None,
) -> list[ToolSpec]:
    """Register the recommended standard tool bundle."""

    active_registry = registry or ToolRegistry.global_instance()
    active_options = options or StandardToolOptions()
    specs: list[ToolSpec] = []
    specs.extend(register_web_readonly_tools(active_registry, active_options))
    specs.extend(register_filesystem_readonly_tools(active_registry, active_options))
    if active_options.include_write_tools:
        specs.extend(register_filesystem_write_tools(active_registry, active_options))
    specs.extend(register_data_tools(active_registry, active_options))
    return specs


__all__ = [
    "register_data_tools",
    "register_filesystem_readonly_tools",
    "register_filesystem_write_tools",
    "register_standard_tools",
    "register_web_readonly_tools",
]
