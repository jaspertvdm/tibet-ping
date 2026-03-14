"""
tibet-ping protocol layer.

Core packet structures for intent-based discovery and communication.
Every ping is a TIBET token carrying identity, intent, context, and purpose.
"""

import json
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class PingType(Enum):
    """Intent type for ping packets."""
    DISCOVER = "discover"      # Who's there? What can you do?
    INTENT = "intent"          # I want something from you
    HEARTBEAT = "heartbeat"    # I'm alive, here's my status
    RELAY = "relay"            # Forward this through mesh


class Priority(Enum):
    """Packet priority levels."""
    URGENT = 3    # Emergency stop, safety critical
    NORMAL = 2    # Standard operations
    LAZY = 1      # Batch at next heartbeat cycle


class RoutingMode(Enum):
    """How packet should be routed."""
    DIRECT = "direct"          # Point-to-point
    MESH = "mesh"              # Multi-hop through network
    BROADCAST = "broadcast"    # All nodes in pod/station


class PingDecision(Enum):
    """Airlock decision for incoming ping."""
    ACCEPT = "accept"      # GROEN zone — auto-allow
    PENDING = "pending"    # GEEL zone — needs review/HITL
    REJECT = "reject"      # ROOD zone — silent drop


@dataclass
class PingPacket:
    """
    TIBET-based ping packet carrying identity, intent, and context.

    Maps to TIBET provenance:
        ERIN:     packet content (source, target, intent, payload)
        ERAAN:    related tokens (vouching chain, previous pings)
        EROMHEEN: context (pod, station, network state)
        ERACHTER: purpose (human-readable why)
    """
    # Core identity
    packet_id: str
    source_did: str                     # Sender JIS DID
    target_did: str                     # Receiver JIS DID or "broadcast"

    # Intent & routing
    ping_type: PingType
    priority: Priority
    routing_mode: RoutingMode
    intent: str                         # e.g. "temperature.read", "door.unlock"
    purpose: str                        # Human-readable ERACHTER

    # Payload
    payload: Dict[str, Any] = field(default_factory=dict)

    # Context (EROMHEEN)
    pod_id: Optional[str] = None
    station_id: Optional[str] = None
    hop_count: int = 0
    max_hops: int = 5

    # Replay protection
    nonce: str = field(default_factory=lambda: secrets.token_hex(16))
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    # TIBET provenance link
    tibet_token_id: Optional[str] = None

    # Vouching
    vouched_by: Optional[str] = None
    vouch_signature: Optional[str] = None

    # Integrity (Ed25519 signature of canonical payload)
    signature: str = ""

    def to_tibet_erin(self) -> Dict[str, Any]:
        """Map to TIBET ERIN — what's IN the packet."""
        return {
            "packet_id": self.packet_id,
            "source_did": self.source_did,
            "target_did": self.target_did,
            "ping_type": self.ping_type.value,
            "intent": self.intent,
            "payload": self.payload,
        }

    def to_tibet_eromheen(self) -> Dict[str, Any]:
        """Map to TIBET EROMHEEN — context around it."""
        return {
            "pod_id": self.pod_id,
            "station_id": self.station_id,
            "hop_count": self.hop_count,
            "routing_mode": self.routing_mode.value,
            "priority": self.priority.value,
            "timestamp": self.timestamp,
        }

    def signature_payload(self) -> str:
        """Canonical representation for signing (deterministic JSON)."""
        data = {
            "packet_id": self.packet_id,
            "source_did": self.source_did,
            "target_did": self.target_did,
            "ping_type": self.ping_type.value,
            "intent": self.intent,
            "nonce": self.nonce,
            "timestamp": self.timestamp,
            "payload": self.payload,
        }
        return json.dumps(data, sort_keys=True, separators=(",", ":"))

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict for transport."""
        return {
            "packet_id": self.packet_id,
            "source_did": self.source_did,
            "target_did": self.target_did,
            "ping_type": self.ping_type.value,
            "priority": self.priority.value,
            "routing_mode": self.routing_mode.value,
            "intent": self.intent,
            "purpose": self.purpose,
            "payload": self.payload,
            "pod_id": self.pod_id,
            "station_id": self.station_id,
            "hop_count": self.hop_count,
            "max_hops": self.max_hops,
            "nonce": self.nonce,
            "timestamp": self.timestamp,
            "tibet_token_id": self.tibet_token_id,
            "vouched_by": self.vouched_by,
            "vouch_signature": self.vouch_signature,
            "signature": self.signature,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PingPacket":
        """Deserialize from dict."""
        return cls(
            packet_id=data["packet_id"],
            source_did=data["source_did"],
            target_did=data["target_did"],
            ping_type=PingType(data["ping_type"]),
            priority=Priority(data["priority"]),
            routing_mode=RoutingMode(data["routing_mode"]),
            intent=data["intent"],
            purpose=data["purpose"],
            payload=data.get("payload", {}),
            pod_id=data.get("pod_id"),
            station_id=data.get("station_id"),
            hop_count=data.get("hop_count", 0),
            max_hops=data.get("max_hops", 5),
            nonce=data.get("nonce", ""),
            timestamp=data.get("timestamp", ""),
            tibet_token_id=data.get("tibet_token_id"),
            vouched_by=data.get("vouched_by"),
            vouch_signature=data.get("vouch_signature"),
            signature=data.get("signature", ""),
        )


@dataclass
class PingResponse:
    """Response to a ping packet."""
    response_id: str
    in_response_to: str                 # Original packet_id
    responder_did: str
    decision: PingDecision

    # Response data
    payload: Dict[str, Any] = field(default_factory=dict)
    capabilities: List[str] = field(default_factory=list)
    trust_score: float = 0.0
    fira_breakdown: Dict[str, float] = field(default_factory=dict)

    # TIBET provenance
    tibet_token_id: Optional[str] = None

    # Timing
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    rtt_ms: Optional[float] = None

    # Airlock info
    airlock_zone: str = "ROOD"
    applied_rule: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict."""
        return {
            "response_id": self.response_id,
            "in_response_to": self.in_response_to,
            "responder_did": self.responder_did,
            "decision": self.decision.value,
            "payload": self.payload,
            "capabilities": self.capabilities,
            "trust_score": self.trust_score,
            "fira_breakdown": self.fira_breakdown,
            "tibet_token_id": self.tibet_token_id,
            "timestamp": self.timestamp,
            "rtt_ms": self.rtt_ms,
            "airlock_zone": self.airlock_zone,
            "applied_rule": self.applied_rule,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PingResponse":
        """Deserialize from dict."""
        return cls(
            response_id=data["response_id"],
            in_response_to=data["in_response_to"],
            responder_did=data["responder_did"],
            decision=PingDecision(data["decision"]),
            payload=data.get("payload", {}),
            capabilities=data.get("capabilities", []),
            trust_score=data.get("trust_score", 0.0),
            fira_breakdown=data.get("fira_breakdown", {}),
            tibet_token_id=data.get("tibet_token_id"),
            timestamp=data.get("timestamp", ""),
            rtt_ms=data.get("rtt_ms"),
            airlock_zone=data.get("airlock_zone", "ROOD"),
            applied_rule=data.get("applied_rule"),
        )
