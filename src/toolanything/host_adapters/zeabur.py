from __future__ import annotations

import os

from .base import HostAdapter, HostCapabilities, Transport, TransportDecision


class ZeaburHostAdapter(HostAdapter):
    """
    Host adapter for Zeabur PaaS.

    Known constraints:
    - Inbound SSE is blocked by the HTTP edge proxy
    - Long-lived HTTP connections are not supported
    - Outbound connections are allowed
    """

    name = "zeabur"

    @classmethod
    def detect(cls) -> bool:
        # Zeabur injects a set of environment variables.
        # We intentionally check multiple signals for robustness.
        return any(key.startswith("ZEABUR_") for key in os.environ)

    def capabilities(self) -> HostCapabilities:
        return HostCapabilities(
            inbound_sse=False,
            inbound_websocket=True,
            outbound_sse=True,
            long_lived_http=False,
        )

    def choose_transport(
        self,
        preferred: Transport = Transport.SSE,
    ) -> TransportDecision:
        caps = self.capabilities()

        if preferred == Transport.SSE:
            return TransportDecision(
                transport=Transport.RELAY,
                reason=(
                    "Inbound SSE is not supported on Zeabur HTTP services. "
                    "Falling back to relay mode using outbound SSE."
                ),
                warning=(
                    "This host does not support standard MCP SSE. "
                    "Deploy a dedicated SSE-capable host (e.g. Fly.io, VM) "
                    "if strict MCP compliance is required."
                ),
            )

        if preferred == Transport.WEBSOCKET and caps.supports(Transport.WEBSOCKET):
            return TransportDecision(
                transport=Transport.WEBSOCKET,
                reason="WebSocket is supported on Zeabur.",
            )

        if preferred == Transport.RELAY and caps.supports(Transport.RELAY):
            return TransportDecision(
                transport=Transport.RELAY,
                reason="Outbound connections are supported on Zeabur.",
            )

        return TransportDecision(
            transport=Transport.DISABLED,
            reason="No supported transport is available on this host.",
            warning="MCP server cannot be exposed on this environment.",
        )
