"""Tests for PeerTracker — connection tracking and liveness."""

from __future__ import annotations

import time

import pytest

from tibet_ping.transport.peers import PeerTracker, PeerRecord


class TestRecordActivity:
    def test_new_peer(self) -> None:
        tracker = PeerTracker()
        peer = tracker.record_activity("jis:test:a", ("192.168.1.1", 7150))
        assert peer.device_did == "jis:test:a"
        assert peer.address == ("192.168.1.1", 7150)
        assert peer.packet_count == 1

    def test_update_peer(self) -> None:
        tracker = PeerTracker()
        tracker.record_activity("jis:test:a", ("192.168.1.1", 7150))
        peer = tracker.record_activity("jis:test:a", ("192.168.1.2", 7150))
        assert peer.address == ("192.168.1.2", 7150)
        assert peer.packet_count == 2

    def test_multiple_peers(self) -> None:
        tracker = PeerTracker()
        tracker.record_activity("jis:test:a", ("192.168.1.1", 7150))
        tracker.record_activity("jis:test:b", ("192.168.1.2", 7150))
        assert len(tracker) == 2


class TestGetAddress:
    def test_known_peer(self) -> None:
        tracker = PeerTracker()
        tracker.record_activity("jis:test:a", ("192.168.1.1", 7150))
        assert tracker.get_address("jis:test:a") == ("192.168.1.1", 7150)

    def test_unknown_peer(self) -> None:
        tracker = PeerTracker()
        assert tracker.get_address("jis:test:unknown") is None

    def test_stale_peer(self) -> None:
        tracker = PeerTracker(timeout=1.0)
        tracker.record_activity("jis:test:a", ("192.168.1.1", 7150))
        tracker._peers["jis:test:a"].last_seen = time.monotonic() - 2.0
        assert tracker.get_address("jis:test:a") is None


class TestAlivePeers:
    def test_all_alive(self) -> None:
        tracker = PeerTracker()
        tracker.record_activity("jis:test:a", ("192.168.1.1", 7150))
        tracker.record_activity("jis:test:b", ("192.168.1.2", 7150))
        alive = tracker.alive_peers()
        assert len(alive) == 2

    def test_mixed_alive_stale(self) -> None:
        tracker = PeerTracker(timeout=1.0)
        tracker.record_activity("jis:test:a", ("192.168.1.1", 7150))
        tracker.record_activity("jis:test:b", ("192.168.1.2", 7150))
        tracker._peers["jis:test:a"].last_seen = time.monotonic() - 2.0
        alive = tracker.alive_peers()
        assert len(alive) == 1
        assert alive[0].device_did == "jis:test:b"


class TestPruneStale:
    def test_prune_removes_stale(self) -> None:
        tracker = PeerTracker(timeout=1.0)
        tracker.record_activity("jis:test:a", ("192.168.1.1", 7150))
        tracker.record_activity("jis:test:b", ("192.168.1.2", 7150))
        tracker._peers["jis:test:a"].last_seen = time.monotonic() - 2.0
        pruned = tracker.prune_stale()
        assert pruned == 1
        assert len(tracker) == 1

    def test_prune_nothing(self) -> None:
        tracker = PeerTracker()
        tracker.record_activity("jis:test:a", ("192.168.1.1", 7150))
        pruned = tracker.prune_stale()
        assert pruned == 0


class TestStats:
    def test_stats(self) -> None:
        tracker = PeerTracker(timeout=60.0)
        tracker.record_activity("jis:test:a", ("192.168.1.1", 7150))
        stats = tracker.stats()
        assert stats["total_tracked"] == 1
        assert stats["alive"] == 1
        assert stats["stale"] == 0
        assert stats["timeout"] == 60.0
