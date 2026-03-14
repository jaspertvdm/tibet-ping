"""Tests for proto.py — PingPacket, PingResponse, enums."""

from tibet_ping.proto import (
    PingDecision,
    PingPacket,
    PingResponse,
    PingType,
    Priority,
    RoutingMode,
)


def _make_packet(**kwargs):
    defaults = dict(
        packet_id="ping_test001",
        source_did="jis:home:sensor_a",
        target_did="jis:home:hub",
        ping_type=PingType.INTENT,
        priority=Priority.NORMAL,
        routing_mode=RoutingMode.DIRECT,
        intent="temperature.read",
        purpose="Read temperature",
    )
    defaults.update(kwargs)
    return PingPacket(**defaults)


def test_packet_creation():
    pkt = _make_packet()
    assert pkt.source_did == "jis:home:sensor_a"
    assert pkt.ping_type == PingType.INTENT
    assert pkt.priority == Priority.NORMAL
    assert pkt.hop_count == 0
    assert pkt.max_hops == 5
    assert len(pkt.nonce) == 32  # 16 bytes hex


def test_packet_serialization_roundtrip():
    pkt = _make_packet(payload={"celsius": 21.5}, pod_id="kitchen")
    d = pkt.to_dict()
    restored = PingPacket.from_dict(d)

    assert restored.packet_id == pkt.packet_id
    assert restored.source_did == pkt.source_did
    assert restored.ping_type == PingType.INTENT
    assert restored.priority == Priority.NORMAL
    assert restored.routing_mode == RoutingMode.DIRECT
    assert restored.payload == {"celsius": 21.5}
    assert restored.pod_id == "kitchen"


def test_tibet_erin_mapping():
    pkt = _make_packet(payload={"key": "val"})
    erin = pkt.to_tibet_erin()
    assert erin["source_did"] == "jis:home:sensor_a"
    assert erin["intent"] == "temperature.read"
    assert erin["payload"] == {"key": "val"}


def test_tibet_eromheen_mapping():
    pkt = _make_packet(pod_id="kitchen", station_id="home")
    eromheen = pkt.to_tibet_eromheen()
    assert eromheen["pod_id"] == "kitchen"
    assert eromheen["station_id"] == "home"
    assert eromheen["routing_mode"] == "direct"


def test_signature_payload_deterministic():
    pkt = _make_packet()
    p1 = pkt.signature_payload()
    p2 = pkt.signature_payload()
    assert p1 == p2
    assert '"packet_id"' in p1


def test_response_creation():
    resp = PingResponse(
        response_id="resp_001",
        in_response_to="ping_test001",
        responder_did="jis:home:hub",
        decision=PingDecision.ACCEPT,
        trust_score=0.85,
        airlock_zone="GROEN",
    )
    assert resp.decision == PingDecision.ACCEPT
    assert resp.airlock_zone == "GROEN"


def test_response_serialization_roundtrip():
    resp = PingResponse(
        response_id="resp_001",
        in_response_to="ping_001",
        responder_did="jis:home:hub",
        decision=PingDecision.PENDING,
        trust_score=0.5,
    )
    d = resp.to_dict()
    restored = PingResponse.from_dict(d)
    assert restored.decision == PingDecision.PENDING
    assert restored.trust_score == 0.5


def test_enum_values():
    assert PingType.DISCOVER.value == "discover"
    assert PingType.HEARTBEAT.value == "heartbeat"
    assert PingType.RELAY.value == "relay"
    assert Priority.URGENT.value == 3
    assert Priority.LAZY.value == 1
    assert RoutingMode.MESH.value == "mesh"
    assert PingDecision.REJECT.value == "reject"
