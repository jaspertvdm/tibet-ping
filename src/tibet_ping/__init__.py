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

__version__ = "0.1.3"

__all__ = [
    # Node (main entry point)
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
]
