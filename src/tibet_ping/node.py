"""
PingNode — main entry point for tibet-ping.

Ties all layers together: proto, nonce, airlock, vouch, topology, beacon.
"""

import secrets
from typing import Dict, List, Optional, Set

from .airlock import Airlock, AirlockRule
from .beacon import Beacon, BeaconHandler, BeaconResponse
from .handler import PingHandler
from .nonce import NonceTracker
from .proto import (
    PingDecision,
    PingPacket,
    PingResponse,
    PingType,
    Priority,
    RoutingMode,
)
from .topology import TopologyManager
from .vouch import Vouch, VouchRegistry


class PingNode:
    """
    A tibet-ping node.

    Can send pings, receive pings, broadcast beacons, vouch for devices,
    and manage topology (pods/stations).

    Usage::

        node = PingNode("jis:home:hub_living_room")
        node.set_trust("jis:home:sensor_temp", 0.9)

        # Send a ping
        packet = node.ping(
            target="jis:home:sensor_temp",
            intent="temperature.read",
            purpose="Periodic temperature check",
        )

        # Receive a ping (on the other end)
        response = other_node.receive(packet)
    """

    def __init__(
        self,
        device_did: str,
        nonce_window: int = 30,
        trust_groen: float = 0.7,
        trust_rood: float = 0.3,
    ) -> None:
        self.device_did = device_did

        # Components
        self.nonce_tracker = NonceTracker(window_seconds=nonce_window)
        self.vouch_registry = VouchRegistry()
        self.airlock = Airlock(
            trust_threshold_groen=trust_groen,
            trust_threshold_rood=trust_rood,
        )
        self.topology = TopologyManager()
        self.beacon_handler = BeaconHandler()
        self.handler = PingHandler(
            device_did=device_did,
            airlock=self.airlock,
            nonce_tracker=self.nonce_tracker,
            vouch_registry=self.vouch_registry,
        )

    # ── Sending ──────────────────────────────────────────────

    def ping(
        self,
        target: str,
        intent: str,
        purpose: str,
        ping_type: PingType = PingType.INTENT,
        priority: Priority = Priority.NORMAL,
        routing_mode: RoutingMode = RoutingMode.DIRECT,
        payload: Optional[dict] = None,
        pod_id: Optional[str] = None,
        station_id: Optional[str] = None,
    ) -> PingPacket:
        """Create a ping packet (proto layer — no transport)."""
        return PingPacket(
            packet_id=f"ping_{secrets.token_hex(8)}",
            source_did=self.device_did,
            target_did=target,
            ping_type=ping_type,
            priority=priority,
            routing_mode=routing_mode,
            intent=intent,
            purpose=purpose,
            payload=payload or {},
            pod_id=pod_id,
            station_id=station_id,
        )

    def heartbeat(
        self,
        target: str = "broadcast",
        status: Optional[dict] = None,
        pod_id: Optional[str] = None,
    ) -> PingPacket:
        """Create a heartbeat packet."""
        return self.ping(
            target=target,
            intent="heartbeat",
            purpose="Periodic keep-alive",
            ping_type=PingType.HEARTBEAT,
            priority=Priority.LAZY,
            routing_mode=RoutingMode.BROADCAST if target == "broadcast" else RoutingMode.DIRECT,
            payload={"status": status or {"alive": True}},
            pod_id=pod_id,
        )

    def discover(
        self,
        capabilities: Optional[List[str]] = None,
        pod_id: Optional[str] = None,
    ) -> PingPacket:
        """Create a discovery packet."""
        return self.ping(
            target="broadcast",
            intent="discover",
            purpose="Looking for devices with matching capabilities",
            ping_type=PingType.DISCOVER,
            priority=Priority.NORMAL,
            routing_mode=RoutingMode.BROADCAST,
            payload={"requested_capabilities": capabilities or []},
            pod_id=pod_id,
        )

    # ── Receiving ────────────────────────────────────────────

    def receive(self, packet: PingPacket) -> PingResponse:
        """Process an incoming ping packet through the full pipeline."""
        return self.handler.handle(packet)

    # ── Trust Management ─────────────────────────────────────

    def set_trust(self, did: str, trust: float) -> None:
        """Set trust for a known device."""
        self.handler.set_device_trust(did, trust)

    def vouch(
        self,
        vouched_dids: List[str],
        vouch_factor: float = 0.7,
        my_trust: float = 0.9,
        pod_id: Optional[str] = None,
        reason: str = "",
    ) -> Vouch:
        """
        Vouch for a group of devices.

        Trust of vouched devices = my_trust * vouch_factor.
        """
        vouch = Vouch(
            vouch_id=f"vouch_{secrets.token_hex(8)}",
            voucher_did=self.device_did,
            voucher_trust=my_trust,
            vouched_dids=vouched_dids,
            vouch_factor=vouch_factor,
            pod_id=pod_id,
            reason=reason,
        )
        self.vouch_registry.add_vouch(vouch)
        return vouch

    # ── Airlock Rules ────────────────────────────────────────

    def add_rule(self, rule: AirlockRule) -> None:
        """Add an airlock rule."""
        self.airlock.add_rule(rule)

    # ── Beacon (Bootstrap) ───────────────────────────────────

    def broadcast_beacon(
        self,
        capabilities: Optional[List[str]] = None,
        requested_pod: Optional[str] = None,
        device_type: str = "generic",
    ) -> Beacon:
        """Create a bootstrap beacon for this device."""
        return Beacon.create(
            source_did=self.device_did,
            capabilities=capabilities,
            requested_pod=requested_pod,
            device_type=device_type,
        )

    def handle_beacon(self, beacon: Beacon) -> BeaconResponse:
        """Handle an incoming beacon (as hub)."""
        return self.beacon_handler.handle_beacon(beacon, self.device_did)

    # ── Topology ─────────────────────────────────────────────

    def create_pod(
        self,
        pod_id: str,
        name: str,
        station_id: Optional[str] = None,
        capabilities: Optional[Set[str]] = None,
    ):
        """Create a pod with this device as hub."""
        return self.topology.create_pod(
            pod_id=pod_id,
            name=name,
            hub_did=self.device_did,
            station_id=station_id,
            capabilities=capabilities,
        )

    # ── Stats ────────────────────────────────────────────────

    def stats(self) -> dict:
        """Comprehensive node statistics."""
        return {
            "device_did": self.device_did,
            "nonce_tracked": self.nonce_tracker.tracked_count,
            "airlock": self.airlock.stats(),
            "vouching": self.vouch_registry.stats(),
            "topology": self.topology.stats(),
        }
