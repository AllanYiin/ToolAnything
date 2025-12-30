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

from toolanything.exceptions import ToolError


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


class MCPJSONRPCProtocolCore(MCPProtocolCore):
    """Concrete MCP JSON-RPC protocol core implementation."""

    _JSONRPC_VERSION = "2.0"

    _ERROR_METHOD_NOT_FOUND = -32601
    _ERROR_INTERNAL = -32603
    _ERROR_TOOL = -32001


    def handle(
        self,
        request: MCPRequest,
        *,
        context: MCPRequestContext,
        deps: MCPProtocolDependencies,
    ) -> Optional[MCPResponse]:
        method = request.get("method")
        request_id = request.get("id")

        if method == "initialize":
            return self._build_result(request_id, deps.capabilities.get_capabilities())

        if method == "notifications/initialized":
            return None

        if method == "tools/list":
            return self._build_result(request_id, {"tools": list(deps.tools.list_tools())})

        if method == "tools/call":
            return self._handle_tool_call(request, context=context, deps=deps)

        return self._handle_method_not_found(request_id)

    def _handle_tool_call(
        self,
        request: MCPRequest,
        *,
        context: MCPRequestContext,
        deps: MCPProtocolDependencies,
    ) -> Optional[MCPResponse]:
        request_id = request.get("id")
        params = request.get("params", {}) or {}
        name = params.get("name")
        arguments: Dict[str, Any] = params.get("arguments", {}) or {}

        try:
            invocation = deps.invoker.call_tool(name, arguments, context=context)

            if request_id is None:
                return None

            return self._build_result(
                request_id,
                {
                    "content": invocation["content"],
                    "meta": invocation["meta"],
                    "arguments": invocation.get("arguments", {}),
                    "audit": invocation.get("audit", {}),
                },
                extra={"raw_result": invocation.get("raw_result")},
            )
        except ToolError as exc:

            if request_id is None:
                return None
            masked_args = self._mask_arguments(arguments, deps=deps)
            audit_log = self._audit_call(name, arguments, context=context, deps=deps)
            return self._build_error(
                request_id,
                self._ERROR_TOOL,

                exc.error_type,
                data={
                    "message": str(exc),
                    "details": exc.data,

                    "arguments": masked_args,
                    "audit": audit_log,
                },
            )
        except Exception:
            if request_id is None:
                return None
            masked_args = self._mask_arguments(arguments, deps=deps)
            audit_log = self._audit_call(name, arguments, context=context, deps=deps)
            return self._build_error(
                request_id,
                self._ERROR_INTERNAL,
                "internal_error",
                data={
                    "arguments": masked_args,
                    "audit": audit_log,

                },
            )

    def _handle_method_not_found(self, request_id: str | int | None) -> Optional[MCPResponse]:
        if request_id is None:
            return None

        return self._build_error(request_id, self._ERROR_METHOD_NOT_FOUND, "method_not_found")


    def _build_result(
        self,
        request_id: str | int | None,
        result: Dict[str, Any],
        *,
        extra: Optional[Dict[str, Any]] = None,
    ) -> MCPResponse:
        payload: MCPResponse = {
            "jsonrpc": self._JSONRPC_VERSION,
            "id": request_id,
            "result": result,
        }
        if extra:
            payload.update(extra)
        return payload

    def _build_error(
        self,
        request_id: str | int | None,
        code: int,
        message: str,
        *,
        data: Optional[Dict[str, Any]] = None,
    ) -> MCPResponse:
        payload: MCPResponse = {
            "jsonrpc": self._JSONRPC_VERSION,
            "id": request_id,
            "error": {"code": code, "message": message},
        }
        if data is not None:
            payload["error"]["data"] = data
        return payload


    def _mask_arguments(
        self,
        arguments: Dict[str, Any],
        *,
        deps: MCPProtocolDependencies,
    ) -> Dict[str, Any]:
        masker = getattr(deps.invoker, "_mask", None)
        if callable(masker):
            return masker(arguments)
        return dict(arguments)

    def _audit_call(
        self,
        name: Optional[str],
        arguments: Dict[str, Any],
        *,
        context: MCPRequestContext,
        deps: MCPProtocolDependencies,
    ) -> Dict[str, Any]:
        auditor = getattr(deps.invoker, "_audit", None)
        if callable(auditor):
            return auditor(name or "", arguments, context.user_id or "default")
        return {}

