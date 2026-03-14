"""
Bootstrap beacon for new devices (airgapped, local-only).

Solves the chicken-and-egg problem: new device knows nobody.
Beacon broadcasts on local network. Hub can auto-vouch or escalate to HITL.

NO secrets in beacons — assume adversarial broadcast medium.
"""

import re
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional


@dataclass
class Beacon:
    """
    Bootstrap beacon broadcast by a new device.

    Contains only public information:
    - JIS DID
    - Capabilities
    - Requested pod
    - Public key HASH (not the key itself!)
    """
    beacon_id: str
    source_did: str
    capabilities: List[str] = field(default_factory=list)
    requested_pod: Optional[str] = None
    device_type: str = "generic"  # sensor, actuator, gateway, controller
    public_key_hash: str = ""
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def is_fresh(self, max_age_seconds: int = 300) -> bool:
        """Check if beacon is recent enough (default 5 minutes)."""
        now = datetime.now(timezone.utc)
        try:
            ts = self.timestamp.replace("Z", "+00:00")
            beacon_time = datetime.fromisoformat(ts)
            if beacon_time.tzinfo is None:
                beacon_time = beacon_time.replace(tzinfo=timezone.utc)
            age = (now - beacon_time).total_seconds()
            return age <= max_age_seconds
        except (ValueError, OSError):
            return False

    def to_dict(self) -> dict:
        return {
            "beacon_id": self.beacon_id,
            "source_did": self.source_did,
            "capabilities": self.capabilities,
            "requested_pod": self.requested_pod,
            "device_type": self.device_type,
            "public_key_hash": self.public_key_hash,
            "timestamp": self.timestamp,
        }

    @classmethod
    def create(
        cls,
        source_did: str,
        capabilities: Optional[List[str]] = None,
        requested_pod: Optional[str] = None,
        device_type: str = "generic",
        public_key_hash: str = "",
    ) -> "Beacon":
        """Factory method with auto-generated beacon_id."""
        return cls(
            beacon_id=f"beacon_{secrets.token_hex(8)}",
            source_did=source_did,
            capabilities=capabilities or [],
            requested_pod=requested_pod,
            device_type=device_type,
            public_key_hash=public_key_hash,
        )


@dataclass
class BeaconResponse:
    """Hub response to a beacon."""
    response_id: str
    in_response_to: str  # beacon_id
    hub_did: str
    decision: str  # "auto_vouched", "hitl_pending", "rejected"
    vouch_id: Optional[str] = None
    assigned_pod: Optional[str] = None
    message: str = ""
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class BeaconHandler:
    """
    Handle beacon broadcasts for bootstrapping.

    auto_vouch_rules: list of dicts with matching conditions.
    Each rule can match on: device_type, required_capabilities, source_pattern.
    If matched, the beacon is auto-vouched into the specified pod.
    """

    def __init__(
        self,
        auto_vouch_rules: Optional[List[dict]] = None,
        on_hitl_needed: Optional[Callable[["Beacon"], None]] = None,
    ) -> None:
        self.auto_vouch_rules = auto_vouch_rules or []
        self.on_hitl_needed = on_hitl_needed
        self._recent: Dict[str, Beacon] = {}

    def handle_beacon(self, beacon: Beacon, hub_did: str) -> BeaconResponse:
        """
        Process an incoming beacon.

        1. Check freshness
        2. Try auto-vouch rules
        3. Escalate to HITL if no rule matches
        """
        resp_id = f"resp_{beacon.beacon_id}"

        if not beacon.is_fresh():
            return BeaconResponse(
                response_id=resp_id,
                in_response_to=beacon.beacon_id,
                hub_did=hub_did,
                decision="rejected",
                message="Beacon too old",
            )

        # Track recent beacons
        self._recent[beacon.beacon_id] = beacon

        # Try auto-vouch rules
        for rule in self.auto_vouch_rules:
            if self._matches_rule(beacon, rule):
                vouch_id = f"vouch_{secrets.token_hex(8)}"
                return BeaconResponse(
                    response_id=resp_id,
                    in_response_to=beacon.beacon_id,
                    hub_did=hub_did,
                    decision="auto_vouched",
                    vouch_id=vouch_id,
                    assigned_pod=rule.get("pod_id"),
                    message=f"Auto-vouched via rule: {rule.get('name', 'unnamed')}",
                )

        # No rule matched → HITL
        if self.on_hitl_needed:
            self.on_hitl_needed(beacon)

        return BeaconResponse(
            response_id=resp_id,
            in_response_to=beacon.beacon_id,
            hub_did=hub_did,
            decision="hitl_pending",
            message="Awaiting HITL approval",
        )

    @staticmethod
    def _matches_rule(beacon: Beacon, rule: dict) -> bool:
        """Check if beacon matches an auto-vouch rule."""
        if "device_type" in rule:
            if beacon.device_type != rule["device_type"]:
                return False

        if "required_capabilities" in rule:
            required = set(rule["required_capabilities"])
            if not required.issubset(set(beacon.capabilities)):
                return False

        if "source_pattern" in rule:
            if not re.match(rule["source_pattern"], beacon.source_did):
                return False

        return True
