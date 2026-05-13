"""
tibet-ping: Intent-Based Discovery & Communication Protocol.

ICMP ping is dumb: "are you there?" → "yes". No identity, no intent, no trust.
tibet-ping replaces this with a TIBET token as handshake.

Every ping carries:
    Identity  — JIS DID (who are you)
    Intent    — what do you want
    Context   — pod, station, network
    Purpose   — why are you pinging

Responses are trust-gated through Airlock (GROEN/GEEL/ROOD).

Usage::

    from tibet_ping import PingNode

    # Create a node
    hub = PingNode("jis:home:hub")
    sensor = PingNode("jis:home:sensor_temp")

    # Hub trusts sensor
    hub.set_trust("jis:home:sensor_temp", 0.9)

    # Sensor pings hub
    packet = sensor.ping(
        target="jis:home:hub",
        intent="temperature.report",
        purpose="Periodic temperature reading",
        payload={"celsius": 21.5},
    )

    # Hub receives and processes
    response = hub.receive(packet)
    print(response.decision)    # PingDecision.ACCEPT
    print(response.airlock_zone)  # "GROEN"
"""

from .proto import PingPacket, PingResponse, PingType, Priority, RoutingMode, PingDecision
from .nonce import NonceTracker
from .airlock import Airlock, AirlockRule, AirlockZone, PendingPing
from .vouch import Vouch, VouchRegistry
from .topology import TopologyManager, Pod, Station, NodeRole
from .beacon import Beacon, BeaconHandler, BeaconResponse
from .handler import PingHandler
from .node import PingNode

__version__ = "0.3.2"

# Transport layer (merged from tibet-iot in v0.2.0)
from .transport import (
    IoTNode,
    Transport,
    UDPTransport,
    TransportConfig,
    DEFAULT_PORT,
    DISCOVERY_PORT,
    PacketCodec,
    FrameFlags,
    PeerTracker,
    PeerRecord,
    MeshRelay,
    NetworkDiscovery,
    MULTICAST_GROUP,
    MULTICAST_TTL,
)

__all__ = [
    # Node (main entry point — protocol)
    "PingNode",
    # Proto
    "PingPacket",
    "PingResponse",
    "PingType",
    "Priority",
    "RoutingMode",
    "PingDecision",
    # Nonce
    "NonceTracker",
    # Airlock
    "Airlock",
    "AirlockRule",
    "AirlockZone",
    "PendingPing",
    # Vouch
    "Vouch",
    "VouchRegistry",
    # Topology
    "TopologyManager",
    "Pod",
    "Station",
    "NodeRole",
    # Beacon
    "Beacon",
    "BeaconHandler",
    "BeaconResponse",
    # Handler
    "PingHandler",
    # Transport (merged from tibet-iot)
    "IoTNode",
    "Transport",
    "UDPTransport",
    "TransportConfig",
    "DEFAULT_PORT",
    "DISCOVERY_PORT",
    "PacketCodec",
    "FrameFlags",
    "PeerTracker",
    "PeerRecord",
    "MeshRelay",
    "NetworkDiscovery",
    "MULTICAST_GROUP",
    "MULTICAST_TTL",
]
