"""
Trust delegation via vouching.

A trusted device can vouch for a group of devices.
Solves HITL scaling: one ACK covers 50 IoT sensors.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional


@dataclass
class Vouch:
    """
    Trust vouching record.

    A trusted hub vouches for a group of devices.
    Vouched trust = voucher_trust * vouch_factor.
    Example: 0.9 * 0.7 = 0.63
    """
    vouch_id: str
    voucher_did: str
    voucher_trust: float
    vouched_dids: List[str]
    vouch_factor: float = 0.7

    pod_id: Optional[str] = None
    reason: str = ""
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    expires_at: Optional[str] = None
    tibet_token_id: Optional[str] = None
    signature: str = ""

    @property
    def computed_trust(self) -> float:
        """Trust score inherited by vouched devices."""
        return self.voucher_trust * self.vouch_factor

    def is_expired(self) -> bool:
        """Check if vouch has expired."""
        if not self.expires_at:
            return False
        now = datetime.now(timezone.utc)
        try:
            ts = self.expires_at.replace("Z", "+00:00")
            expiry = datetime.fromisoformat(ts)
            if expiry.tzinfo is None:
                expiry = expiry.replace(tzinfo=timezone.utc)
            return now > expiry
        except (ValueError, OSError):
            return True  # Unparseable = expired

    def to_dict(self) -> dict:
        return {
            "vouch_id": self.vouch_id,
            "voucher_did": self.voucher_did,
            "voucher_trust": self.voucher_trust,
            "vouched_dids": self.vouched_dids,
            "vouch_factor": self.vouch_factor,
            "computed_trust": self.computed_trust,
            "pod_id": self.pod_id,
            "reason": self.reason,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "tibet_token_id": self.tibet_token_id,
        }


class VouchRegistry:
    """
    Track vouching relationships.

    Returns the highest active vouch trust for a device.
    Supports vouch revocation (e.g. if voucher is compromised).
    """

    def __init__(self) -> None:
        self._vouches: Dict[str, Vouch] = {}
        self._by_vouched: Dict[str, List[str]] = {}  # did → [vouch_id, ...]

    def add_vouch(self, vouch: Vouch) -> None:
        """Register a new vouch."""
        self._vouches[vouch.vouch_id] = vouch
        for did in vouch.vouched_dids:
            if did not in self._by_vouched:
                self._by_vouched[did] = []
            self._by_vouched[did].append(vouch.vouch_id)

    def get_trust_for_device(self, did: str) -> Optional[float]:
        """
        Get vouched trust for a device.
        Returns highest trust from all active vouches, or None if no vouches.
        """
        vouch_ids = self._by_vouched.get(did)
        if not vouch_ids:
            return None

        max_trust = 0.0
        for vid in vouch_ids:
            vouch = self._vouches.get(vid)
            if vouch and not vouch.is_expired():
                max_trust = max(max_trust, vouch.computed_trust)

        return max_trust if max_trust > 0 else None

    def get_vouches_for_device(self, did: str) -> List[Vouch]:
        """Get all active vouches covering a device."""
        vouch_ids = self._by_vouched.get(did, [])
        return [
            self._vouches[vid]
            for vid in vouch_ids
            if vid in self._vouches and not self._vouches[vid].is_expired()
        ]

    def revoke_vouch(self, vouch_id: str) -> bool:
        """Revoke a vouch. Returns True if found and revoked."""
        vouch = self._vouches.pop(vouch_id, None)
        if not vouch:
            return False
        for did in vouch.vouched_dids:
            if did in self._by_vouched:
                ids = self._by_vouched[did]
                if vouch_id in ids:
                    ids.remove(vouch_id)
                if not ids:
                    del self._by_vouched[did]
        return True

    def stats(self) -> dict:
        active = sum(1 for v in self._vouches.values() if not v.is_expired())
        return {
            "total_vouches": len(self._vouches),
            "active_vouches": active,
            "vouched_devices": len(self._by_vouched),
        }
