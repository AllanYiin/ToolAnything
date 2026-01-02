"""ToolAnything 主入口。"""

from toolanything.core import (
    FailureLogManager,
    PipelineDefinition,
    ToolDefinition,
    ToolRegistry,
    ToolSearchTool,
    ToolSpec,
    ToolManager,
    build_parameters_schema,
    build_search_tool,
    python_type_to_schema,
    ToolMetadata,
    normalize_metadata,
    BaseToolSelectionStrategy,
    RuleBasedStrategy,
    HybridStrategy,
)
from toolanything.pipeline.context import PipelineContext
from toolanything.decorators import pipeline, tool
from toolanything.exceptions import (
    AdapterError,
    RegistryError,
    SchemaValidationError,
    ToolAnythingError,
    ToolError,
    ToolNotFoundError,
)
from toolanything.state import StateManager

from toolanything.runtime import run, serve


from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .core import (
        BaseToolSelectionStrategy,
        FailureLogManager,
        HybridStrategy,
        PipelineDefinition,
        RuleBasedStrategy,
        ToolDefinition,
        ToolManager,
        ToolMetadata,
        ToolRegistry,
        ToolSearchTool,
        ToolSpec,
        build_parameters_schema,
        build_search_tool,
        normalize_metadata,
        python_type_to_schema,
    )
    from .decorators import pipeline, tool
    from .exceptions import (
        AdapterError,
        RegistryError,
        SchemaValidationError,
        ToolAnythingError,
        ToolError,
        ToolNotFoundError,
    )
    from .pipeline import PipelineContext
    from .runtime import run, serve
    from .state import StateManager

_CORE_EXPORTS = [
    "PipelineDefinition",
    "ToolDefinition",
    "FailureLogManager",
    "ToolSpec",
    "ToolRegistry",
    "ToolManager",
    "ToolSearchTool",
    "build_search_tool",
    "build_parameters_schema",
    "python_type_to_schema",
    "ToolMetadata",
    "normalize_metadata",
    "BaseToolSelectionStrategy",
    "RuleBasedStrategy",
    "HybridStrategy",
]
_EXCEPTION_EXPORTS = [
    "ToolAnythingError",
    "ToolNotFoundError",
    "SchemaValidationError",
    "RegistryError",
    "AdapterError",
    "ToolError",
]
_DECORATOR_EXPORTS = ["pipeline", "tool"]
_PIPELINE_EXPORTS = ["PipelineContext"]
_STATE_EXPORTS = ["StateManager"]
_RUNTIME_EXPORTS = ["run", "serve"]
_CORE_EXPORTS_SET = set(_CORE_EXPORTS)
_EXCEPTION_EXPORTS_SET = set(_EXCEPTION_EXPORTS)
_DECORATOR_EXPORTS_SET = set(_DECORATOR_EXPORTS)
_PIPELINE_EXPORTS_SET = set(_PIPELINE_EXPORTS)
_STATE_EXPORTS_SET = set(_STATE_EXPORTS)
_RUNTIME_EXPORTS_SET = set(_RUNTIME_EXPORTS)

__all__ = [
    *_CORE_EXPORTS,
    *_DECORATOR_EXPORTS,
    *_STATE_EXPORTS,
    *_PIPELINE_EXPORTS,
    *_RUNTIME_EXPORTS,
    *_EXCEPTION_EXPORTS,
]


def __getattr__(name: str):
    if name in _CORE_EXPORTS_SET:
        from . import core

        return getattr(core, name)
    if name in _EXCEPTION_EXPORTS_SET:
        from . import exceptions

        return getattr(exceptions, name)
    if name in _DECORATOR_EXPORTS_SET:
        from . import decorators

        return getattr(decorators, name)
    if name in _PIPELINE_EXPORTS_SET:
        from . import pipeline

        return getattr(pipeline, name)
    if name in _STATE_EXPORTS_SET:
        from . import state

        return getattr(state, name)
    if name in _RUNTIME_EXPORTS_SET:
        from . import runtime

        return getattr(runtime, name)
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
