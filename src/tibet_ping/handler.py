"""
Ping processing engine.

Integrates nonce tracking, airlock gating, vouching, and TIBET provenance.
tibet-overlay is optional — falls back to internal trust dict.
"""

import secrets
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from .airlock import Airlock, AirlockZone
from .nonce import NonceTracker
from .proto import PingDecision, PingPacket, PingResponse
from .vouch import VouchRegistry

# Optional tibet-core integration
try:
    from tibet_core import Provider, MemoryStore
    HAS_TIBET_CORE = True
except ImportError:
    HAS_TIBET_CORE = False


class PingHandler:
    """
    Process incoming ping packets.

    Pipeline:
        1. Replay check (nonce)
        2. Trust lookup (overlay or internal + vouching)
        3. Airlock gating (GROEN/GEEL/ROOD)
        4. TIBET audit token (if tibet-core available)
        5. Response
    """

    def __init__(
        self,
        device_did: str,
        airlock: Airlock,
        nonce_tracker: NonceTracker,
        vouch_registry: VouchRegistry,
        known_devices: Optional[Dict[str, float]] = None,
        tibet_actor: Optional[str] = None,
    ) -> None:
        self.device_did = device_did
        self.airlock = airlock
        self.nonce_tracker = nonce_tracker
        self.vouch_registry = vouch_registry
        self._known_devices: Dict[str, float] = known_devices or {}

        # TIBET provenance (optional)
        self._tibet = None
        if HAS_TIBET_CORE:
            self._tibet = Provider(
                actor=tibet_actor or device_did,
                store=MemoryStore(),
            )

    def set_device_trust(self, did: str, trust: float) -> None:
        """Manually set trust for a known device."""
        self._known_devices[did] = max(0.0, min(1.0, trust))

    def handle(self, packet: PingPacket) -> PingResponse:
        """
        Process an incoming ping packet.

        Returns PingResponse with decision.
        """
        start = datetime.now(timezone.utc)

        # 1. Replay protection
        if self.nonce_tracker.is_replay(packet.nonce, packet.timestamp):
            return self._make_response(
                packet, PingDecision.REJECT, "ROOD",
                trust=0.0, reason="replay_detected",
            )

        # 2. Get sender trust
        trust, fira = self._get_sender_trust(packet.source_did)

        # 3. Airlock gating
        decision = self.airlock.process(packet, trust)
        zone, rule = self.airlock.gate(packet, trust)

        # 4. TIBET audit token
        token_id = None
        if self._tibet:
            token = self._tibet.create(
                action="ping_received",
                erin=packet.to_tibet_erin(),
                eraan=[packet.tibet_token_id] if packet.tibet_token_id else [],
                eromheen={
                    **packet.to_tibet_eromheen(),
                    "handler_did": self.device_did,
                    "sender_trust": trust,
                    "decision": decision.value,
                },
                erachter=packet.purpose,
            )
            token_id = token.token_id

        # 5. Build response
        end = datetime.now(timezone.utc)
        rtt_ms = (end - start).total_seconds() * 1000

        return PingResponse(
            response_id=f"resp_{secrets.token_hex(8)}",
            in_response_to=packet.packet_id,
            responder_did=self.device_did,
            decision=decision,
            trust_score=trust,
            fira_breakdown=fira,
            tibet_token_id=token_id,
            airlock_zone=zone.value,
            applied_rule=rule.name if rule else None,
            rtt_ms=rtt_ms,
        )

    def _get_sender_trust(self, source_did: str) -> tuple:
        """
        Get trust score for sender.

        Priority:
            1. Internal known_devices dict
            2. Vouch registry (trust delegation)
            3. Unknown → 0.0
        """
        # Direct trust
        if source_did in self._known_devices:
            trust = self._known_devices[source_did]
            return (trust, {"score": trust, "source": "known"})

        # Vouched trust
        vouched = self.vouch_registry.get_trust_for_device(source_did)
        if vouched is not None:
            vouches = self.vouch_registry.get_vouches_for_device(source_did)
            return (vouched, {
                "score": vouched,
                "source": "vouched",
                "vouch_count": len(vouches),
            })

        # Unknown
        return (0.0, {"score": 0.0, "source": "unknown"})

    def _make_response(
        self,
        packet: PingPacket,
        decision: PingDecision,
        zone: str,
        trust: float = 0.0,
        reason: str = "",
    ) -> PingResponse:
        """Quick helper for simple responses."""
        return PingResponse(
            response_id=f"resp_{secrets.token_hex(8)}",
            in_response_to=packet.packet_id,
            responder_did=self.device_did,
            decision=decision,
            airlock_zone=zone,
            trust_score=trust,
            payload={"reason": reason} if reason else {},
        )
