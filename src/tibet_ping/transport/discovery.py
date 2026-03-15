"""NetworkDiscovery — LAN multicast beacon for device discovery.

Uses multicast group 224.0.71.50 on port 7151 for LAN-local discovery.
Delegates beacon handling to PingNode's BeaconHandler.
"""

from __future__ import annotations

import asyncio
import logging
import socket
import struct
from typing import Callable, Coroutine, Any, Optional, Tuple, Union

from tibet_ping import PingNode, PingPacket, PingResponse, Beacon, BeaconResponse

from .codec import PacketCodec
from .udp import Transport, DISCOVERY_PORT

logger = logging.getLogger(__name__)

MULTICAST_GROUP = "224.0.71.50"  # 71.50 = TIBET
MULTICAST_TTL = 2  # LAN only (max 1 router hop)

OnDiscoveredCallback = Callable[[str, Tuple[str, int], BeaconResponse], Coroutine[Any, Any, None]]


class NetworkDiscovery:
    """LAN multicast discovery for TIBET IoT nodes.

    Args:
        device_did: this node's DID.
        ping_node: PingNode for beacon handling.
        transport: Transport for sending/receiving.
        multicast_group: multicast group address.
        discovery_port: port for discovery multicast.
    """

    def __init__(
        self,
        device_did: str,
        ping_node: PingNode,
        transport: Transport,
        multicast_group: str = MULTICAST_GROUP,
        discovery_port: int = DISCOVERY_PORT,
    ) -> None:
        self._device_did = device_did
        self._ping_node = ping_node
        self._transport = transport
        self._multicast_group = multicast_group
        self._discovery_port = discovery_port
        self._callbacks: list[OnDiscoveredCallback] = []
        self._multicast_transport: Optional[asyncio.DatagramTransport] = None
        self._codec = PacketCodec()
        self._running = False

    @property
    def running(self) -> bool:
        return self._running

    async def start_listening(self) -> None:
        """Join multicast group and start listening for beacons."""
        if self._running:
            return

        loop = asyncio.get_running_loop()

        # Create multicast receiver socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if hasattr(socket, "SO_REUSEPORT"):
            try:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            except (AttributeError, OSError):
                pass

        sock.bind(("", self._discovery_port))

        # Join multicast group
        mreq = struct.pack(
            "4s4s",
            socket.inet_aton(self._multicast_group),
            socket.inet_aton("0.0.0.0"),
        )
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        sock.setblocking(False)

        self._multicast_transport, _ = await loop.create_datagram_endpoint(
            lambda: _DiscoveryProtocol(
                self._codec, self._device_did, self._on_beacon_received
            ),
            sock=sock,
        )
        self._running = True
        logger.info(
            "Discovery listening on %s:%d",
            self._multicast_group,
            self._discovery_port,
        )

    async def stop(self) -> None:
        """Stop listening for beacons."""
        if self._multicast_transport:
            self._multicast_transport.close()
            self._multicast_transport = None
        self._running = False

    async def broadcast_discover(
        self,
        capabilities: list[str] | None = None,
        device_type: str = "generic",
    ) -> Beacon:
        """Broadcast a DISCOVER beacon via multicast.

        Returns the beacon that was broadcast.
        """
        beacon = self._ping_node.broadcast_beacon(
            capabilities=capabilities,
            device_type=device_type,
        )
        # Encode the discover packet from PingNode
        discover_packet = self._ping_node.discover(
            capabilities=capabilities,
        )
        data = self._codec.encode_packet(discover_packet)

        # Send via multicast
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, MULTICAST_TTL)
        try:
            sock.sendto(data, (self._multicast_group, self._discovery_port))
        finally:
            sock.close()

        logger.debug("Broadcast discover beacon for %s", self._device_did)
        return beacon

    def on_discovered(self, callback: OnDiscoveredCallback) -> None:
        """Register callback for when a new peer is discovered."""
        self._callbacks.append(callback)

    def _on_beacon_received(
        self,
        packet: PingPacket,
        addr: Tuple[str, int],
    ) -> None:
        """Handle incoming beacon packet."""
        # Ignore own beacons
        if packet.source_did == self._device_did:
            return

        # Delegate to PingNode's beacon handler
        beacon = Beacon.create(
            source_did=packet.source_did,
            capabilities=packet.payload.get("capabilities", []),
            device_type=packet.payload.get("device_type", "generic"),
        )
        response = self._ping_node.handle_beacon(beacon)

        logger.info(
            "Beacon from %s at %s -> %s",
            packet.source_did,
            addr,
            response.decision,
        )

        # Notify callbacks
        for cb in self._callbacks:
            asyncio.ensure_future(cb(packet.source_did, addr, response))


class _DiscoveryProtocol(asyncio.DatagramProtocol):
    """Internal protocol for multicast discovery."""

    def __init__(
        self,
        codec: PacketCodec,
        own_did: str,
        on_beacon: Callable[[PingPacket, Tuple[str, int]], None],
    ) -> None:
        self._codec = codec
        self._own_did = own_did
        self._on_beacon = on_beacon

    def datagram_received(self, data: bytes, addr: Tuple[str, int]) -> None:
        try:
            decoded = self._codec.decode(data)
        except (ValueError, Exception):
            return  # Silent drop

        if isinstance(decoded, PingPacket):
            self._on_beacon(decoded, addr)
