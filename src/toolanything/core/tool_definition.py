from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class ToolArgument:
    name: str
    type: Any
    required: bool
    default: Any | None
    description: str | None = None


@dataclass
class ToolDefinition:
    name: str
    path: str
    description: str | None
    args: list[ToolArgument]
    return_type: Any | None
    func: Callable[..., Any]
    input_schema: dict | None
    output_schema: dict | None
    version: str = "1.0.0"
    lifecycle: str = "active"
    group: str | None = None
    annotations: dict = field(default_factory=dict)
    extra: dict = field(default_factory=dict)

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return self.func(*args, **kwargs)
