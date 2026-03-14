"""Tests for nonce.py — replay protection."""

import time
from datetime import datetime, timezone, timedelta

from tibet_ping.nonce import NonceTracker


def test_first_nonce_is_not_replay():
    tracker = NonceTracker(window_seconds=30)
    now = datetime.now(timezone.utc).isoformat()
    assert tracker.is_replay("nonce_001", now) is False


def test_same_nonce_is_replay():
    tracker = NonceTracker(window_seconds=30)
    now = datetime.now(timezone.utc).isoformat()
    tracker.is_replay("nonce_002", now)
    assert tracker.is_replay("nonce_002", now) is True


def test_different_nonces_not_replay():
    tracker = NonceTracker(window_seconds=30)
    now = datetime.now(timezone.utc).isoformat()
    assert tracker.is_replay("nonce_a", now) is False
    assert tracker.is_replay("nonce_b", now) is False


def test_old_timestamp_is_replay():
    tracker = NonceTracker(window_seconds=30)
    old = (datetime.now(timezone.utc) - timedelta(seconds=60)).isoformat()
    assert tracker.is_replay("nonce_old", old) is True


def test_future_timestamp_within_skew():
    tracker = NonceTracker(window_seconds=30, clock_skew_seconds=5)
    future = (datetime.now(timezone.utc) + timedelta(seconds=3)).isoformat()
    assert tracker.is_replay("nonce_future_ok", future) is False


def test_future_timestamp_beyond_skew():
    tracker = NonceTracker(window_seconds=30, clock_skew_seconds=5)
    far_future = (datetime.now(timezone.utc) + timedelta(seconds=10)).isoformat()
    assert tracker.is_replay("nonce_future_bad", far_future) is True


def test_invalid_timestamp():
    tracker = NonceTracker(window_seconds=30)
    assert tracker.is_replay("nonce_bad", "not-a-timestamp") is True


def test_tracked_count():
    tracker = NonceTracker(window_seconds=30)
    now = datetime.now(timezone.utc).isoformat()
    tracker.is_replay("a", now)
    tracker.is_replay("b", now)
    tracker.is_replay("c", now)
    assert tracker.tracked_count == 3


def test_clear():
    tracker = NonceTracker(window_seconds=30)
    now = datetime.now(timezone.utc).isoformat()
    tracker.is_replay("x", now)
    assert tracker.tracked_count == 1
    tracker.clear()
    assert tracker.tracked_count == 0
    # After clear, same nonce should be accepted again
    assert tracker.is_replay("x", now) is False


def test_z_suffix_timestamp():
    """ISO timestamps with Z suffix should work."""
    tracker = NonceTracker(window_seconds=30)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    assert tracker.is_replay("nonce_z", now) is False
