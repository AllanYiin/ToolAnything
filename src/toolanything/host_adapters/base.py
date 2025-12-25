from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class Transport(Enum):
    """
    Logical transport types supported by ToolAnything.
    These are semantic transports, not protocol implementations.
    """

    SSE = "sse"
    WEBSOCKET = "websocket"
    RELAY = "relay"
    DISABLED = "disabled"


@dataclass(frozen=True)
class HostCapabilities:
    """
    Describes what the current host environment is capable of.
    This is intentionally explicit rather than implicit.
    """

    inbound_sse: bool
    inbound_websocket: bool
    outbound_sse: bool
    long_lived_http: bool

    def supports(self, transport: Transport) -> bool:
        if transport == Transport.SSE:
            return self.inbound_sse and self.long_lived_http
        if transport == Transport.WEBSOCKET:
            return self.inbound_websocket
        if transport == Transport.RELAY:
            return self.outbound_sse
        return False


@dataclass(frozen=True)
class TransportDecision:
    """
    Result of transport selection.
    """

    transport: Transport
    reason: str
    warning: Optional[str] = None


class HostAdapter(ABC):
    """
    Base class for all host capability adapters.

    A HostAdapter is responsible for:
    1. Detecting whether it applies to the current environment
    2. Declaring host capabilities
    3. Deciding how ToolAnything should expose MCP
    """

    name: str = "unknown"

    @classmethod
    @abstractmethod
    def detect(cls) -> bool:
        """
        Return True if this adapter applies to the current runtime environment.
        Must be fast and side-effect free.
        """
        raise NotImplementedError

    @abstractmethod
    def capabilities(self) -> HostCapabilities:
        """
        Return the capability matrix of this host.
        """
        raise NotImplementedError

    @abstractmethod
    def choose_transport(
        self,
        preferred: Transport = Transport.SSE,
    ) -> TransportDecision:
        """
        Decide which transport ToolAnything should use, given a preferred transport.
        """
        raise NotImplementedError
