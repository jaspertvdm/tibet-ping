"""
Replay protection via time-windowed nonce tracking.

Window: 30 seconds (configurable).
After window expires, nonces are garbage collected.
"""

import time
from datetime import datetime, timezone
from threading import Lock
from typing import Dict


class NonceTracker:
    """
    Track seen nonces within a time window to prevent replay attacks.

    A ping packet contains a random nonce and a timestamp.
    If we see the same nonce within the window, it's a replay.
    If the timestamp is too old or too far in the future, it's suspicious.
    """

    def __init__(self, window_seconds: int = 30, clock_skew_seconds: int = 5):
        """
        Args:
            window_seconds: How long to remember nonces (default 30s).
            clock_skew_seconds: Tolerance for clock differences (default 5s).
        """
        self.window_seconds = window_seconds
        self.clock_skew_seconds = clock_skew_seconds

        # {nonce: monotonic_time_seen}
        self._seen: Dict[str, float] = {}
        self._lock = Lock()
        self._last_cleanup = time.monotonic()

    def is_replay(self, nonce: str, timestamp_str: str) -> bool:
        """
        Check if nonce+timestamp indicates a replay attack.

        Returns True (replay) if:
        - Nonce was seen before within the window
        - Timestamp is older than window_seconds
        - Timestamp is more than clock_skew_seconds in the future
        - Timestamp is unparseable
        """
        now_mono = time.monotonic()
        now_real = time.time()

        # Parse timestamp
        try:
            ts = timestamp_str.replace("Z", "+00:00")
            pkt_time = datetime.fromisoformat(ts)
            if pkt_time.tzinfo is None:
                pkt_time = pkt_time.replace(tzinfo=timezone.utc)
            pkt_epoch = pkt_time.timestamp()
        except (ValueError, OSError):
            return True  # Unparseable = suspicious

        # Check time bounds
        age = now_real - pkt_epoch
        if age > self.window_seconds:
            return True  # Too old
        if age < -self.clock_skew_seconds:
            return True  # Too far in future

        with self._lock:
            # Periodic cleanup
            if now_mono - self._last_cleanup > self.window_seconds:
                self._cleanup(now_mono)

            # Check if nonce already seen
            if nonce in self._seen:
                return True  # REPLAY!

            # Record nonce
            self._seen[nonce] = now_mono
            return False

    def _cleanup(self, now_mono: float) -> None:
        """Remove expired nonces (older than window)."""
        cutoff = now_mono - self.window_seconds
        expired = [n for n, t in self._seen.items() if t < cutoff]
        for n in expired:
            del self._seen[n]
        self._last_cleanup = now_mono

    @property
    def tracked_count(self) -> int:
        """Number of nonces currently tracked."""
        with self._lock:
            return len(self._seen)

    def clear(self) -> None:
        """Clear all tracked nonces (for testing)."""
        with self._lock:
            self._seen.clear()
