"""PeerTracker — connection tracking and liveness for IoT peers.

Tracks which devices we've heard from, their addresses, and when we last
saw them. Pure sync, no I/O.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class PeerRecord:
    """Record of a known peer."""

    device_did: str
    address: Tuple[str, int]  # (host, port)
    first_seen: float = field(default_factory=time.monotonic)
    last_seen: float = field(default_factory=time.monotonic)
    packet_count: int = 0

    @property
    def age(self) -> float:
        """Seconds since first seen."""
        return time.monotonic() - self.first_seen

    @property
    def idle(self) -> float:
        """Seconds since last activity."""
        return time.monotonic() - self.last_seen


class PeerTracker:
    """Track peer connections and liveness.

    Args:
        timeout: seconds of inactivity before a peer is considered stale.
    """

    def __init__(self, timeout: float = 90.0) -> None:
        self._timeout = timeout
        self._peers: Dict[str, PeerRecord] = {}

    @property
    def timeout(self) -> float:
        return self._timeout

    def record_activity(self, did: str, addr: Tuple[str, int]) -> PeerRecord:
        """Record activity from a peer. Updates address and timestamp."""
        now = time.monotonic()
        if did in self._peers:
            peer = self._peers[did]
            peer.address = addr
            peer.last_seen = now
            peer.packet_count += 1
        else:
            peer = PeerRecord(
                device_did=did,
                address=addr,
                first_seen=now,
                last_seen=now,
                packet_count=1,
            )
            self._peers[did] = peer
        return peer

    def get_address(self, did: str) -> Optional[Tuple[str, int]]:
        """Get last known address for a device. Returns None if stale or unknown."""
        peer = self._peers.get(did)
        if peer is None:
            return None
        if peer.idle > self._timeout:
            return None
        return peer.address

    def get_peer(self, did: str) -> Optional[PeerRecord]:
        """Get peer record if alive."""
        peer = self._peers.get(did)
        if peer is None or peer.idle > self._timeout:
            return None
        return peer

    def alive_peers(self) -> List[PeerRecord]:
        """List all peers that are still alive (not stale)."""
        now = time.monotonic()
        return [
            p
            for p in self._peers.values()
            if (now - p.last_seen) <= self._timeout
        ]

    def prune_stale(self) -> int:
        """Remove stale peers. Returns number of peers pruned."""
        now = time.monotonic()
        stale = [
            did
            for did, p in self._peers.items()
            if (now - p.last_seen) > self._timeout
        ]
        for did in stale:
            del self._peers[did]
        return len(stale)

    def __len__(self) -> int:
        return len(self._peers)

    def stats(self) -> dict:
        alive = self.alive_peers()
        return {
            "total_tracked": len(self._peers),
            "alive": len(alive),
            "stale": len(self._peers) - len(alive),
            "timeout": self._timeout,
        }
