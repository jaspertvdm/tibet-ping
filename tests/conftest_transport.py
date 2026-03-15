"""Test fixtures and MockTransport for transport tests.

MockTransport implements the Transport ABC with in-memory queues.
create_linked_pair() connects two MockTransports for bidirectional testing.
"""

from __future__ import annotations

import asyncio
from typing import Tuple, Union

import pytest

from tibet_ping import PingPacket, PingResponse
from tibet_ping.transport import PacketCodec, Transport
from tibet_ping.transport.udp import OnReceiveCallback


class MockTransport(Transport):
    """In-memory transport for testing. No real sockets."""

    def __init__(self, own_addr: Tuple[str, int] = ("127.0.0.1", 7150)) -> None:
        self._own_addr = own_addr
        self._codec = PacketCodec()
        self._callbacks: list[OnReceiveCallback] = []
        self._running = False
        self._peer: MockTransport | None = None
        self._sent: list[Tuple[bytes, Tuple[str, int]]] = []
        self._broadcast_sent: list[bytes] = []

    @property
    def running(self) -> bool:
        return self._running

    @property
    def own_addr(self) -> Tuple[str, int]:
        return self._own_addr

    @property
    def sent_raw(self) -> list[Tuple[bytes, Tuple[str, int]]]:
        """Raw bytes sent (for inspection)."""
        return self._sent

    @property
    def broadcast_raw(self) -> list[bytes]:
        """Raw broadcast bytes sent."""
        return self._broadcast_sent

    @staticmethod
    def create_linked_pair(
        addr_a: Tuple[str, int] = ("127.0.0.1", 7150),
        addr_b: Tuple[str, int] = ("127.0.0.1", 7151),
    ) -> Tuple["MockTransport", "MockTransport"]:
        """Create two MockTransports linked for bidirectional communication."""
        a = MockTransport(own_addr=addr_a)
        b = MockTransport(own_addr=addr_b)
        a._peer = b
        b._peer = a
        return a, b

    async def start(self) -> None:
        self._running = True

    async def stop(self) -> None:
        self._running = False

    async def send_packet(
        self, packet: PingPacket, addr: Tuple[str, int]
    ) -> None:
        data = self._codec.encode_packet(packet)
        self._sent.append((data, addr))
        # Deliver to linked peer if it matches
        if self._peer and self._peer._running:
            decoded = self._codec.decode(data)
            await self._peer._deliver(decoded, self._own_addr)

    async def send_response(
        self, response: PingResponse, addr: Tuple[str, int]
    ) -> None:
        data = self._codec.encode_response(response)
        self._sent.append((data, addr))
        # Deliver to linked peer
        if self._peer and self._peer._running:
            decoded = self._codec.decode(data)
            await self._peer._deliver(decoded, self._own_addr)

    async def broadcast(self, packet: PingPacket, port: int | None = None) -> None:
        data = self._codec.encode_packet(packet)
        self._broadcast_sent.append(data)
        # Also deliver to peer
        if self._peer and self._peer._running:
            decoded = self._codec.decode(data)
            await self._peer._deliver(decoded, self._own_addr)

    def on_receive(self, callback: OnReceiveCallback) -> None:
        self._callbacks.append(callback)

    async def _deliver(
        self,
        decoded: Union[PingPacket, PingResponse],
        from_addr: Tuple[str, int],
    ) -> None:
        """Deliver a decoded packet to registered callbacks."""
        for cb in self._callbacks:
            await cb(decoded, from_addr)
