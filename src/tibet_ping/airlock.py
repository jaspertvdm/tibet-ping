"""
Trust-gated access control for incoming pings.

Three zones:
    GROEN — Known + trusted → auto-allow
    GEEL  — Unknown → pending (rules or HITL)
    ROOD  — Untrusted → silent drop (no info leak)
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional, Tuple

from .proto import PingDecision, PingPacket


class AirlockZone(Enum):
    """Three-zone trust model."""
    GROEN = "GROEN"
    GEEL = "GEEL"
    ROOD = "ROOD"


@dataclass
class AirlockRule:
    """
    Pattern-based auto-decision rule.

    Patterns support simple glob: "*" matches everything,
    "prefix*" matches start, "*suffix" matches end.

    Examples:
        {"source_did": "jis:home:*", "intent": "temperature.*"} → GROEN
        {"intent": "door.unlock"} → GEEL (force HITL)
    """
    rule_id: str
    name: str
    pattern: Dict[str, str]
    decision: PingDecision
    zone: AirlockZone
    priority: int = 50  # Higher = checked first

    def matches(self, packet: PingPacket, sender_trust: float) -> bool:
        """Check if packet matches this rule's pattern."""
        for key, pattern in self.pattern.items():
            if key == "source_did":
                if not _glob_match(packet.source_did, pattern):
                    return False
            elif key == "intent":
                if not _glob_match(packet.intent, pattern):
                    return False
            elif key == "pod_id":
                if packet.pod_id != pattern:
                    return False
            elif key == "ping_type":
                if packet.ping_type.value != pattern:
                    return False
            elif key == "min_trust":
                if sender_trust < float(pattern):
                    return False
        return True


def _glob_match(value: str, pattern: str) -> bool:
    """Simple glob: *, prefix*, *suffix, exact."""
    if pattern == "*":
        return True
    if pattern.startswith("*") and pattern.endswith("*") and len(pattern) > 2:
        return pattern[1:-1] in value
    if pattern.endswith("*"):
        return value.startswith(pattern[:-1])
    if pattern.startswith("*"):
        return value.endswith(pattern[1:])
    return value == pattern


@dataclass
class PendingPing:
    """Ping awaiting HITL decision."""
    packet: PingPacket
    sender_trust: float
    reason: str


class Airlock:
    """
    Trust-gated access control.

    Rules are checked first (highest priority wins).
    Then trust thresholds determine zone.
    GEEL pings go to pending queue and trigger on_hitl_needed callback.
    """

    def __init__(
        self,
        trust_threshold_groen: float = 0.7,
        trust_threshold_rood: float = 0.3,
        on_hitl_needed: Optional[Callable[[PendingPing], None]] = None,
    ) -> None:
        self.trust_threshold_groen = trust_threshold_groen
        self.trust_threshold_rood = trust_threshold_rood
        self.on_hitl_needed = on_hitl_needed
        self._rules: List[AirlockRule] = []
        self.pending: Dict[str, PendingPing] = {}

    def add_rule(self, rule: AirlockRule) -> None:
        """Add a rule (auto-sorted by priority, highest first)."""
        self._rules.append(rule)
        self._rules.sort(key=lambda r: r.priority, reverse=True)

    @property
    def rules(self) -> List[AirlockRule]:
        return list(self._rules)

    def gate(
        self, packet: PingPacket, sender_trust: float
    ) -> Tuple[AirlockZone, Optional[AirlockRule]]:
        """
        Determine zone for a packet.
        Returns (zone, matched_rule_or_None).
        """
        # Rules first
        for rule in self._rules:
            if rule.matches(packet, sender_trust):
                return (rule.zone, rule)

        # Trust thresholds
        if sender_trust >= self.trust_threshold_groen:
            return (AirlockZone.GROEN, None)
        if sender_trust < self.trust_threshold_rood:
            return (AirlockZone.ROOD, None)

        return (AirlockZone.GEEL, None)

    def process(self, packet: PingPacket, sender_trust: float) -> PingDecision:
        """
        Full processing: gate → decision → pending queue if GEEL.
        """
        zone, rule = self.gate(packet, sender_trust)

        if zone == AirlockZone.GROEN:
            return PingDecision.ACCEPT
        if zone == AirlockZone.ROOD:
            return PingDecision.REJECT

        # GEEL: add to pending
        pending = PendingPing(
            packet=packet,
            sender_trust=sender_trust,
            reason=f"Trust {sender_trust:.2f} in GEEL zone"
            + (f" (rule: {rule.name})" if rule else ""),
        )
        self.pending[packet.packet_id] = pending

        if self.on_hitl_needed:
            self.on_hitl_needed(pending)

        return PingDecision.PENDING

    def approve_pending(self, packet_id: str) -> bool:
        """HITL approves a pending ping."""
        return self.pending.pop(packet_id, None) is not None

    def reject_pending(self, packet_id: str) -> bool:
        """HITL rejects a pending ping."""
        return self.pending.pop(packet_id, None) is not None

    def stats(self) -> dict:
        return {
            "rules": len(self._rules),
            "pending_count": len(self.pending),
            "thresholds": {
                "groen": self.trust_threshold_groen,
                "rood": self.trust_threshold_rood,
            },
        }
