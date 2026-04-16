"""Runtime tool execution policy hooks."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from .models import ToolSpec
from .runtime_types import ExecutionContext


class ToolPolicyError(PermissionError):
    """Raised when a runtime policy blocks a tool invocation."""


@dataclass(frozen=True)
class ToolPolicyDecision:
    allowed: bool
    reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class ToolExecutionPolicy(Protocol):
    def before_tool_call(
        self,
        tool: ToolSpec,
        arguments: dict[str, Any],
        context: ExecutionContext,
    ) -> ToolPolicyDecision:
        """Return whether a tool call is allowed before invocation."""


class AllowAllToolPolicy:
    def before_tool_call(
        self,
        tool: ToolSpec,
        arguments: dict[str, Any],
        context: ExecutionContext,
    ) -> ToolPolicyDecision:
        del tool, arguments, context
        return ToolPolicyDecision(allowed=True, reason="allow_all")


@dataclass
class MetadataToolPolicy:
    """Simple metadata-driven runtime policy.

    This policy is intentionally small: it enforces scopes and approval flags
    exposed in ToolSpec.metadata without imposing a specific approval backend.
    """

    allowed_scopes: set[str] | None = None
    approved_tools: set[str] = field(default_factory=set)
    allow_requires_approval: bool = False
    block_side_effects: bool = False

    def before_tool_call(
        self,
        tool: ToolSpec,
        arguments: dict[str, Any],
        context: ExecutionContext,
    ) -> ToolPolicyDecision:
        del arguments, context
        metadata = tool.metadata or {}
        scopes = set(str(scope) for scope in metadata.get("scopes", []))
        if self.allowed_scopes is not None and not scopes.issubset(self.allowed_scopes):
            missing = sorted(scopes.difference(self.allowed_scopes))
            return ToolPolicyDecision(False, f"tool scopes are not allowed: {missing}")

        if self.block_side_effects and bool(metadata.get("side_effect", False)):
            return ToolPolicyDecision(False, "side-effecting tools are blocked")

        if bool(metadata.get("requires_approval", False)):
            if not self.allow_requires_approval and tool.name not in self.approved_tools:
                return ToolPolicyDecision(False, "tool requires approval")

        return ToolPolicyDecision(True, "metadata_policy_allow")


def enforce_tool_policy(
    policy: ToolExecutionPolicy | None,
    tool: ToolSpec,
    arguments: dict[str, Any],
    context: ExecutionContext,
) -> ToolPolicyDecision:
    if policy is None:
        return ToolPolicyDecision(True, "no_policy")
    decision = policy.before_tool_call(tool, arguments, context)
    if not decision.allowed:
        raise ToolPolicyError(decision.reason or f"tool blocked by policy: {tool.name}")
    return decision
