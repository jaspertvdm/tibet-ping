"""MeshRelay — multi-hop forwarding with loop detection.

Handles relaying PingPackets through the mesh network. Pure sync, no I/O.
Only relays packets with RoutingMode.MESH.
"""

from __future__ import annotations

import copy
from collections import OrderedDict

from tibet_ping import PingPacket, RoutingMode


class MeshRelay:
    """Multi-hop packet relay with loop detection.

    Args:
        device_did: this node's DID (to detect self-addressed packets).
        max_hops: maximum hop count before dropping.
        seen_cache_size: max entries in seen-packets cache.
    """

    def __init__(
        self,
        device_did: str,
        max_hops: int = 5,
        seen_cache_size: int = 10_000,
    ) -> None:
        self._device_did = device_did
        self._max_hops = max_hops
        self._seen_cache_size = seen_cache_size
        self._seen: OrderedDict[str, None] = OrderedDict()
        self._relayed = 0
        self._dropped = 0

    def prepare_relay(self, packet: PingPacket) -> PingPacket | None:
        """Prepare a packet for relay forwarding.

        Returns a new PingPacket with incremented hop_count, or None if:
        - Routing mode is not MESH
        - Packet exceeds max hops
        - Packet was already seen (loop)

        The original packet is not modified.
        """
        if packet.routing_mode != RoutingMode.MESH:
            self._dropped += 1
            return None

        if packet.packet_id in self._seen:
            self._dropped += 1
            return None

        if packet.hop_count >= self._max_hops:
            self._dropped += 1
            return None

        self._mark_seen(packet.packet_id)

        relayed = copy.copy(packet)
        relayed.hop_count = packet.hop_count + 1
        self._relayed += 1
        return relayed

    def _mark_seen(self, packet_id: str) -> None:
        """Add packet_id to seen cache, evicting oldest half if full."""
        if len(self._seen) >= self._seen_cache_size:
            # Evict oldest half
            to_remove = self._seen_cache_size // 2
            for _ in range(to_remove):
                self._seen.popitem(last=False)
        self._seen[packet_id] = None

    def stats(self) -> dict:
        return {
            "device_did": self._device_did,
            "relayed": self._relayed,
            "dropped": self._dropped,
            "cache_size": len(self._seen),
            "max_hops": self._max_hops,
        }
