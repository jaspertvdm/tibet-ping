"""Tests for vouch.py — trust delegation."""

from datetime import datetime, timezone, timedelta
from tibet_ping.vouch import Vouch, VouchRegistry


def test_computed_trust():
    v = Vouch(
        vouch_id="v1",
        voucher_did="jis:hub",
        voucher_trust=0.9,
        vouched_dids=["jis:s1", "jis:s2"],
        vouch_factor=0.7,
    )
    assert abs(v.computed_trust - 0.63) < 0.001


def test_vouch_not_expired():
    v = Vouch(
        vouch_id="v1", voucher_did="jis:hub",
        voucher_trust=0.9, vouched_dids=["jis:s1"],
    )
    assert v.is_expired() is False


def test_vouch_expired():
    past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    v = Vouch(
        vouch_id="v1", voucher_did="jis:hub",
        voucher_trust=0.9, vouched_dids=["jis:s1"],
        expires_at=past,
    )
    assert v.is_expired() is True


def test_vouch_future_not_expired():
    future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    v = Vouch(
        vouch_id="v1", voucher_did="jis:hub",
        voucher_trust=0.9, vouched_dids=["jis:s1"],
        expires_at=future,
    )
    assert v.is_expired() is False


def test_registry_add_and_lookup():
    reg = VouchRegistry()
    v = Vouch(
        vouch_id="v1", voucher_did="jis:hub",
        voucher_trust=0.9, vouched_dids=["jis:s1", "jis:s2"],
        vouch_factor=0.7,
    )
    reg.add_vouch(v)

    trust = reg.get_trust_for_device("jis:s1")
    assert trust is not None
    assert abs(trust - 0.63) < 0.001

    trust2 = reg.get_trust_for_device("jis:s2")
    assert trust2 is not None


def test_registry_unknown_device():
    reg = VouchRegistry()
    assert reg.get_trust_for_device("jis:unknown") is None


def test_registry_highest_trust_wins():
    reg = VouchRegistry()
    reg.add_vouch(Vouch(
        vouch_id="v1", voucher_did="jis:hub_a",
        voucher_trust=0.6, vouched_dids=["jis:s1"],
        vouch_factor=0.5,
    ))
    reg.add_vouch(Vouch(
        vouch_id="v2", voucher_did="jis:hub_b",
        voucher_trust=0.9, vouched_dids=["jis:s1"],
        vouch_factor=0.8,
    ))

    trust = reg.get_trust_for_device("jis:s1")
    # v2 gives higher trust: 0.9 * 0.8 = 0.72 vs v1: 0.6 * 0.5 = 0.30
    assert abs(trust - 0.72) < 0.001


def test_revoke_vouch():
    reg = VouchRegistry()
    reg.add_vouch(Vouch(
        vouch_id="v1", voucher_did="jis:hub",
        voucher_trust=0.9, vouched_dids=["jis:s1"],
    ))
    assert reg.get_trust_for_device("jis:s1") is not None

    assert reg.revoke_vouch("v1") is True
    assert reg.get_trust_for_device("jis:s1") is None
    assert reg.revoke_vouch("v1") is False  # Already revoked


def test_stats():
    reg = VouchRegistry()
    reg.add_vouch(Vouch(
        vouch_id="v1", voucher_did="jis:hub",
        voucher_trust=0.9, vouched_dids=["jis:s1", "jis:s2"],
    ))
    stats = reg.stats()
    assert stats["total_vouches"] == 1
    assert stats["active_vouches"] == 1
    assert stats["vouched_devices"] == 2


def test_to_dict():
    v = Vouch(
        vouch_id="v1", voucher_did="jis:hub",
        voucher_trust=0.9, vouched_dids=["jis:s1"],
        vouch_factor=0.7, reason="Test",
    )
    d = v.to_dict()
    assert d["vouch_id"] == "v1"
    assert abs(d["computed_trust"] - 0.63) < 0.001
