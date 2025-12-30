"""MCP JSON-RPC protocol core interface.

This module defines the single authoritative interface for MCP JSON-RPC handling.

Protocol Core should handle these MCP methods:
- initialize
- notifications/initialized
- tools/list
- tools/call
- unknown method fallback (method_not_found)

External injection responsibilities (from server/transport):
- Capability/server metadata (protocol version, server info, dependencies)
- Tool schema listing
- Tool invocation execution
- Security/audit masking and logging (if needed)
- User/session context (user_id, state/session identifiers)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, Literal, Mapping, Optional, Protocol, Sequence, TypedDict


MCPMethod = Literal[
    "initialize",
    "notifications/initialized",
    "tools/list",
    "tools/call",
]


class MCPRequest(TypedDict, total=False):
    """Parsed MCP JSON-RPC request payload.

    The transport layer must provide a fully parsed dict that matches JSON-RPC 2.0
    envelope semantics (jsonrpc/id/method/params).
    """

    jsonrpc: str
    id: str | int | None
    method: MCPMethod | str
    params: Dict[str, Any]


class MCPResponse(TypedDict, total=False):
    """MCP JSON-RPC response payload.

    The Protocol Core returns a pure JSON-serializable dict representing either a
    result or error response (or None for notifications).
    """

    jsonrpc: str
    id: str | int | None
    result: Dict[str, Any]
    error: Dict[str, Any]


class MCPToolSchema(TypedDict, total=False):
    """Tool schema entry used by tools/list and adapter exports."""

    name: str
    description: str
    input_schema: Dict[str, Any]


class MCPToolCallParams(TypedDict, total=False):
    """Parameters for tools/call requests."""

    name: str
    arguments: Dict[str, Any]


class MCPInvocationResult(TypedDict, total=False):
    """Normalized tool invocation result returned by injected tool executor."""

    content: Sequence[Dict[str, Any]]
    meta: Dict[str, Any]
    arguments: Dict[str, Any]
    audit: Dict[str, Any]


class MCPErrorPayload(TypedDict, total=False):
    """Standardized error payload returned by Protocol Core."""

    code: int
    message: str
    data: Dict[str, Any]


@dataclass(frozen=True)
class MCPRequestContext:
    """Injected, transport-provided context.

    This carries request-scoped metadata such as user/session identity or any
    transport-specific identifiers that should not be derived inside Protocol Core.
    """

    user_id: Optional[str] = None
    session_id: Optional[str] = None
    transport: Optional[str] = None


class MCPCapabilitiesProvider(Protocol):
    """Provides MCP capabilities and server metadata for initialize."""

    def get_capabilities(self) -> Dict[str, Any]:
        """Return MCP capabilities, server info, and dependencies."""


class MCPToolSchemaProvider(Protocol):
    """Provides tool schemas for tools/list."""

    def list_tools(self) -> Sequence[MCPToolSchema]:
        """Return tool schemas matching MCP input_schema format."""


class MCPToolInvoker(Protocol):
    """Executes tools for tools/call."""

    def call_tool(
        self,
        name: str,
        arguments: Mapping[str, Any],
        *,
        context: MCPRequestContext,
    ) -> MCPInvocationResult:
        """Execute a tool and return a normalized MCP invocation result."""


class MCPProtocolDependencies(Protocol):
    """Aggregated dependencies injected from transport/server.

    This abstraction prevents direct access to ToolRegistry or transport details.
    """

    capabilities: MCPCapabilitiesProvider
    tools: MCPToolSchemaProvider
    invoker: MCPToolInvoker


class MCPProtocolCore(Protocol):
    """MCP JSON-RPC Protocol Core interface.

    The Protocol Core must implement MCP JSON-RPC handling for initialize,
    notifications/initialized, tools/list, tools/call, and unknown methods.
    """

    def handle(
        self,
        request: MCPRequest,
        *,
        context: MCPRequestContext,
        deps: MCPProtocolDependencies,
    ) -> Optional[MCPResponse]:
        """Handle a single MCP JSON-RPC request and return a response payload.

        Returns None for notification-style requests that require no response.
        """
