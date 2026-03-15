"""tibet-ping transport layer — UDP, LAN discovery, mesh relay.

Merged from tibet-iot into tibet-ping v0.2.0.
Protocol and transport are one package now.

Usage::

    import asyncio
    from tibet_ping.transport import IoTNode, TransportConfig

    async def main():
        node = IoTNode("jis:home:hub")
        node.set_trust("jis:home:sensor", 0.9)
        await node.start()

        response = await node.send_ping(
            target="jis:home:sensor",
            addr=("192.168.1.42", 7150),
            intent="temperature.read",
            purpose="Check room temperature",
        )

        if response:
            print(response.decision)  # PingDecision.ACCEPT

        await node.stop()

    asyncio.run(main())
"""

from .codec import PacketCodec, FrameFlags, MAGIC, VERSION, HEADER_SIZE
from .peers import PeerTracker, PeerRecord
from .relay import MeshRelay
from .udp import (
    Transport,
    UDPTransport,
    TransportConfig,
    DEFAULT_PORT,
    DISCOVERY_PORT,
)
from .discovery import NetworkDiscovery, MULTICAST_GROUP, MULTICAST_TTL
from .iot_node import IoTNode

__all__ = [
    # Node (main entry point)
    "IoTNode",
    # Transport
    "Transport",
    "UDPTransport",
    "TransportConfig",
    "DEFAULT_PORT",
    "DISCOVERY_PORT",
    # Codec
    "PacketCodec",
    "FrameFlags",
    "MAGIC",
    "VERSION",
    "HEADER_SIZE",
    # Peers
    "PeerTracker",
    "PeerRecord",
    # Relay
    "MeshRelay",
    # Discovery
    "NetworkDiscovery",
    "MULTICAST_GROUP",
    "MULTICAST_TTL",
]
