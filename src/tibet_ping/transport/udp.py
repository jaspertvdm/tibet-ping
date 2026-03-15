"""Transport ABC and UDPTransport — async network I/O for TIBET.

Transport is the abstract base class. UDPTransport implements it using
asyncio DatagramProtocol for real UDP communication.
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine, Optional, Tuple, Union

from tibet_ping import PingPacket, PingResponse

from .codec import PacketCodec

logger = logging.getLogger(__name__)

# Default ports
DEFAULT_PORT = 7150
DISCOVERY_PORT = 7151

# Callback type: receives decoded packet/response + sender address
OnReceiveCallback = Callable[
    [Union[PingPacket, PingResponse], Tuple[str, int]],
    Coroutine[Any, Any, None],
]


@dataclass
class TransportConfig:
    """Configuration for transport layer."""

    bind_host: str = "0.0.0.0"
    bind_port: int = DEFAULT_PORT
    use_msgpack: bool = False
    broadcast: bool = True


class Transport(ABC):
    """Abstract transport for sending/receiving TIBET packets."""

    @abstractmethod
    async def start(self) -> None:
        """Start the transport (bind sockets, etc)."""

    @abstractmethod
    async def stop(self) -> None:
        """Stop the transport and release resources."""

    @abstractmethod
    async def send_packet(
        self, packet: PingPacket, addr: Tuple[str, int]
    ) -> None:
        """Send a PingPacket to a specific address."""

    @abstractmethod
    async def send_response(
        self, response: PingResponse, addr: Tuple[str, int]
    ) -> None:
        """Send a PingResponse to a specific address."""

    @abstractmethod
    async def broadcast(self, packet: PingPacket, port: int | None = None) -> None:
        """Broadcast a PingPacket to all listeners on the network."""

    @abstractmethod
    def on_receive(self, callback: OnReceiveCallback) -> None:
        """Register a callback for incoming packets/responses."""


class _UDPProtocol(asyncio.DatagramProtocol):
    """Internal asyncio DatagramProtocol handler."""

    def __init__(
        self,
        codec: PacketCodec,
        on_data: Callable[
            [Union[PingPacket, PingResponse], Tuple[str, int]], None
        ],
    ) -> None:
        self._codec = codec
        self._on_data = on_data
        self.transport: Optional[asyncio.DatagramTransport] = None

    def connection_made(self, transport: asyncio.DatagramTransport) -> None:  # type: ignore[override]
        self.transport = transport

    def datagram_received(self, data: bytes, addr: Tuple[str, int]) -> None:
        try:
            decoded = self._codec.decode(data)
        except (ValueError, Exception) as exc:
            # ROOD philosophy: malformed packets = silent drop
            logger.debug("Malformed packet from %s: %s", addr, exc)
            return
        self._on_data(decoded, addr)

    def error_received(self, exc: Exception) -> None:
        logger.warning("UDP error: %s", exc)

    def connection_lost(self, exc: Optional[Exception]) -> None:
        if exc:
            logger.warning("UDP connection lost: %s", exc)


class UDPTransport(Transport):
    """UDP transport using asyncio DatagramProtocol.

    Args:
        config: Transport configuration.
    """

    def __init__(self, config: TransportConfig | None = None) -> None:
        self._config = config or TransportConfig()
        self._codec = PacketCodec(use_msgpack=self._config.use_msgpack)
        self._protocol: Optional[_UDPProtocol] = None
        self._transport: Optional[asyncio.DatagramTransport] = None
        self._callbacks: list[OnReceiveCallback] = []
        self._running = False

    @property
    def running(self) -> bool:
        return self._running

    async def start(self) -> None:
        if self._running:
            return
        loop = asyncio.get_running_loop()
        self._transport, self._protocol = await loop.create_datagram_endpoint(
            lambda: _UDPProtocol(self._codec, self._dispatch_sync),
            local_addr=(self._config.bind_host, self._config.bind_port),
        )
        # Enable broadcast if configured
        if self._config.broadcast:
            sock = self._transport.get_extra_info("socket")
            if sock is not None:
                import socket

                sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self._running = True
        logger.info(
            "UDP transport started on %s:%d",
            self._config.bind_host,
            self._config.bind_port,
        )

    async def stop(self) -> None:
        if not self._running:
            return
        if self._transport:
            self._transport.close()
            self._transport = None
        self._protocol = None
        self._running = False
        logger.info("UDP transport stopped")

    async def send_packet(
        self, packet: PingPacket, addr: Tuple[str, int]
    ) -> None:
        if not self._transport:
            raise RuntimeError("Transport not started")
        data = self._codec.encode_packet(packet)
        self._transport.sendto(data, addr)

    async def send_response(
        self, response: PingResponse, addr: Tuple[str, int]
    ) -> None:
        if not self._transport:
            raise RuntimeError("Transport not started")
        data = self._codec.encode_response(response)
        self._transport.sendto(data, addr)

    async def broadcast(self, packet: PingPacket, port: int | None = None) -> None:
        if not self._transport:
            raise RuntimeError("Transport not started")
        target_port = port or self._config.bind_port
        data = self._codec.encode_packet(packet)
        self._transport.sendto(data, ("255.255.255.255", target_port))

    def on_receive(self, callback: OnReceiveCallback) -> None:
        self._callbacks.append(callback)

    def _dispatch_sync(
        self,
        decoded: Union[PingPacket, PingResponse],
        addr: Tuple[str, int],
    ) -> None:
        """Dispatch from sync protocol callback to async handlers."""
        for cb in self._callbacks:
            asyncio.ensure_future(cb(decoded, addr))
