"""Tests for beacon.py — bootstrap discovery."""

from datetime import datetime, timezone, timedelta
from tibet_ping.beacon import Beacon, BeaconHandler, BeaconResponse


def test_beacon_create():
    b = Beacon.create(
        source_did="jis:new:sensor_1",
        capabilities=["temperature", "humidity"],
        device_type="sensor",
    )
    assert b.source_did == "jis:new:sensor_1"
    assert b.beacon_id.startswith("beacon_")
    assert "temperature" in b.capabilities


def test_beacon_fresh():
    b = Beacon.create(source_did="jis:new:s1")
    assert b.is_fresh() is True


def test_beacon_stale():
    b = Beacon.create(source_did="jis:new:s1")
    b.timestamp = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
    assert b.is_fresh(max_age_seconds=300) is False


def test_beacon_to_dict():
    b = Beacon.create(source_did="jis:s1", capabilities=["temp"])
    d = b.to_dict()
    assert d["source_did"] == "jis:s1"
    assert "temp" in d["capabilities"]


def test_handler_rejects_stale():
    handler = BeaconHandler()
    b = Beacon.create(source_did="jis:s1")
    b.timestamp = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()

    resp = handler.handle_beacon(b, "jis:hub")
    assert resp.decision == "rejected"


def test_handler_auto_vouch():
    handler = BeaconHandler(auto_vouch_rules=[
        {
            "name": "Kitchen sensors",
            "device_type": "sensor",
            "pod_id": "pod_kitchen",
        }
    ])
    b = Beacon.create(source_did="jis:s1", device_type="sensor")
    resp = handler.handle_beacon(b, "jis:hub")

    assert resp.decision == "auto_vouched"
    assert resp.assigned_pod == "pod_kitchen"
    assert resp.vouch_id is not None


def test_handler_auto_vouch_capabilities():
    handler = BeaconHandler(auto_vouch_rules=[
        {
            "name": "Temp sensors",
            "required_capabilities": ["temperature"],
            "pod_id": "pod_k",
        }
    ])
    # Matches
    b1 = Beacon.create(source_did="jis:s1", capabilities=["temperature", "humidity"])
    assert handler.handle_beacon(b1, "jis:hub").decision == "auto_vouched"

    # Doesn't match
    b2 = Beacon.create(source_did="jis:s2", capabilities=["motion"])
    assert handler.handle_beacon(b2, "jis:hub").decision == "hitl_pending"


def test_handler_auto_vouch_source_pattern():
    handler = BeaconHandler(auto_vouch_rules=[
        {
            "name": "Home devices",
            "source_pattern": r"jis:home:.*",
            "pod_id": "pod_home",
        }
    ])
    b1 = Beacon.create(source_did="jis:home:temp_1")
    assert handler.handle_beacon(b1, "jis:hub").decision == "auto_vouched"

    b2 = Beacon.create(source_did="jis:office:temp_1")
    assert handler.handle_beacon(b2, "jis:hub").decision == "hitl_pending"


def test_handler_hitl_callback():
    received = []
    handler = BeaconHandler(on_hitl_needed=lambda b: received.append(b))
    b = Beacon.create(source_did="jis:unknown:device")
    handler.handle_beacon(b, "jis:hub")

    assert len(received) == 1
    assert received[0].source_did == "jis:unknown:device"


def test_handler_no_rules_means_hitl():
    handler = BeaconHandler()
    b = Beacon.create(source_did="jis:s1")
    resp = handler.handle_beacon(b, "jis:hub")
    assert resp.decision == "hitl_pending"
