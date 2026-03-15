"""Tests for MeshRelay — multi-hop forwarding and loop detection."""

from __future__ import annotations

import pytest
from tibet_ping import PingNode, RoutingMode

from tibet_ping.transport.relay import MeshRelay


@pytest.fixture
def relay() -> MeshRelay:
    return MeshRelay("jis:test:relay", max_hops=5)


@pytest.fixture
def mesh_packet():
    node = PingNode("jis:test:sender")
    return node.ping(
        target="jis:test:receiver",
        intent="data.forward",
        purpose="Mesh relay test",
        routing_mode=RoutingMode.MESH,
    )


@pytest.fixture
def direct_packet():
    node = PingNode("jis:test:sender")
    return node.ping(
        target="jis:test:receiver",
        intent="data.read",
        purpose="Direct test",
        routing_mode=RoutingMode.DIRECT,
    )


class TestPrepareRelay:
    def test_increments_hop_count(self, relay: MeshRelay, mesh_packet) -> None:
        original_hops = mesh_packet.hop_count
        relayed = relay.prepare_relay(mesh_packet)
        assert relayed is not None
        assert relayed.hop_count == original_hops + 1

    def test_does_not_modify_original(self, relay: MeshRelay, mesh_packet) -> None:
        original_hops = mesh_packet.hop_count
        relay.prepare_relay(mesh_packet)
        assert mesh_packet.hop_count == original_hops

    def test_rejects_non_mesh(self, relay: MeshRelay, direct_packet) -> None:
        result = relay.prepare_relay(direct_packet)
        assert result is None

    def test_max_hops_exceeded(self, relay: MeshRelay, mesh_packet) -> None:
        mesh_packet.hop_count = 5
        result = relay.prepare_relay(mesh_packet)
        assert result is None

    def test_duplicate_detection(self, relay: MeshRelay, mesh_packet) -> None:
        first = relay.prepare_relay(mesh_packet)
        assert first is not None
        second = relay.prepare_relay(mesh_packet)
        assert second is None


class TestCacheEviction:
    def test_evicts_oldest_half(self) -> None:
        relay = MeshRelay("jis:test:relay", seen_cache_size=10)
        node = PingNode("jis:test:sender")

        for i in range(10):
            packet = node.ping(
                target="jis:test:receiver",
                intent=f"data.{i}",
                purpose="Cache test",
                routing_mode=RoutingMode.MESH,
            )
            relay.prepare_relay(packet)

        assert len(relay._seen) == 10

        packet = node.ping(
            target="jis:test:receiver",
            intent="data.overflow",
            purpose="Cache overflow",
            routing_mode=RoutingMode.MESH,
        )
        relay.prepare_relay(packet)
        assert len(relay._seen) == 6


class TestStats:
    def test_initial_stats(self, relay: MeshRelay) -> None:
        stats = relay.stats()
        assert stats["relayed"] == 0
        assert stats["dropped"] == 0
        assert stats["cache_size"] == 0

    def test_relayed_count(self, relay: MeshRelay, mesh_packet) -> None:
        relay.prepare_relay(mesh_packet)
        stats = relay.stats()
        assert stats["relayed"] == 1

    def test_dropped_count(self, relay: MeshRelay, direct_packet) -> None:
        relay.prepare_relay(direct_packet)
        stats = relay.stats()
        assert stats["dropped"] == 1
