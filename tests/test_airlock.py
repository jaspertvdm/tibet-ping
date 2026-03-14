"""Tests for airlock.py — trust-gated access control."""

from tibet_ping.airlock import Airlock, AirlockRule, AirlockZone, PendingPing
from tibet_ping.proto import PingDecision, PingPacket, PingType, Priority, RoutingMode


def _pkt(**kwargs):
    defaults = dict(
        packet_id="ping_001",
        source_did="jis:home:sensor",
        target_did="jis:home:hub",
        ping_type=PingType.INTENT,
        priority=Priority.NORMAL,
        routing_mode=RoutingMode.DIRECT,
        intent="temperature.read",
        purpose="Read temp",
    )
    defaults.update(kwargs)
    return PingPacket(**defaults)


def test_groen_zone_high_trust():
    airlock = Airlock(trust_threshold_groen=0.7, trust_threshold_rood=0.3)
    zone, rule = airlock.gate(_pkt(), sender_trust=0.9)
    assert zone == AirlockZone.GROEN
    assert rule is None


def test_rood_zone_low_trust():
    airlock = Airlock(trust_threshold_groen=0.7, trust_threshold_rood=0.3)
    zone, rule = airlock.gate(_pkt(), sender_trust=0.1)
    assert zone == AirlockZone.ROOD


def test_geel_zone_middle_trust():
    airlock = Airlock(trust_threshold_groen=0.7, trust_threshold_rood=0.3)
    zone, rule = airlock.gate(_pkt(), sender_trust=0.5)
    assert zone == AirlockZone.GEEL


def test_rule_override_trust():
    """Rule can force GROEN even for low-trust device."""
    airlock = Airlock(trust_threshold_groen=0.7, trust_threshold_rood=0.3)
    rule = AirlockRule(
        rule_id="r1", name="Allow all temperature reads",
        pattern={"intent": "temperature.*"},
        decision=PingDecision.ACCEPT,
        zone=AirlockZone.GROEN,
    )
    airlock.add_rule(rule)

    zone, matched = airlock.gate(_pkt(intent="temperature.read"), sender_trust=0.1)
    assert zone == AirlockZone.GROEN
    assert matched.name == "Allow all temperature reads"


def test_rule_force_hitl():
    """Rule can force GEEL for high-trust device."""
    airlock = Airlock()
    rule = AirlockRule(
        rule_id="r1", name="Door unlock needs HITL",
        pattern={"intent": "door.unlock"},
        decision=PingDecision.PENDING,
        zone=AirlockZone.GEEL,
    )
    airlock.add_rule(rule)

    zone, _ = airlock.gate(_pkt(intent="door.unlock"), sender_trust=0.95)
    assert zone == AirlockZone.GEEL


def test_rule_priority_ordering():
    """Higher priority rules are checked first."""
    airlock = Airlock()
    airlock.add_rule(AirlockRule(
        rule_id="r_low", name="Low",
        pattern={"intent": "temperature.*"},
        decision=PingDecision.REJECT, zone=AirlockZone.ROOD,
        priority=10,
    ))
    airlock.add_rule(AirlockRule(
        rule_id="r_high", name="High",
        pattern={"intent": "temperature.*"},
        decision=PingDecision.ACCEPT, zone=AirlockZone.GROEN,
        priority=90,
    ))

    zone, matched = airlock.gate(_pkt(intent="temperature.read"), sender_trust=0.5)
    assert zone == AirlockZone.GROEN
    assert matched.name == "High"


def test_process_groen_returns_accept():
    airlock = Airlock()
    decision = airlock.process(_pkt(), sender_trust=0.9)
    assert decision == PingDecision.ACCEPT


def test_process_rood_returns_reject():
    airlock = Airlock()
    decision = airlock.process(_pkt(), sender_trust=0.1)
    assert decision == PingDecision.REJECT


def test_process_geel_adds_to_pending():
    airlock = Airlock()
    pkt = _pkt(packet_id="pending_001")
    decision = airlock.process(pkt, sender_trust=0.5)
    assert decision == PingDecision.PENDING
    assert "pending_001" in airlock.pending


def test_hitl_callback():
    received = []
    airlock = Airlock(on_hitl_needed=lambda p: received.append(p))
    pkt = _pkt(packet_id="hitl_001")
    airlock.process(pkt, sender_trust=0.5)
    assert len(received) == 1
    assert received[0].packet.packet_id == "hitl_001"


def test_approve_pending():
    airlock = Airlock()
    airlock.process(_pkt(packet_id="p1"), sender_trust=0.5)
    assert airlock.approve_pending("p1") is True
    assert "p1" not in airlock.pending
    assert airlock.approve_pending("p1") is False  # Already gone


def test_reject_pending():
    airlock = Airlock()
    airlock.process(_pkt(packet_id="p1"), sender_trust=0.5)
    assert airlock.reject_pending("p1") is True
    assert "p1" not in airlock.pending


def test_source_did_glob():
    airlock = Airlock()
    airlock.add_rule(AirlockRule(
        rule_id="r1", name="Home devices",
        pattern={"source_did": "jis:home:*"},
        decision=PingDecision.ACCEPT, zone=AirlockZone.GROEN,
    ))
    zone, _ = airlock.gate(_pkt(source_did="jis:home:sensor_x"), sender_trust=0.0)
    assert zone == AirlockZone.GROEN

    zone, _ = airlock.gate(_pkt(source_did="jis:office:sensor_x"), sender_trust=0.0)
    assert zone == AirlockZone.ROOD  # Not matched, trust 0 → ROOD


def test_stats():
    airlock = Airlock()
    airlock.add_rule(AirlockRule(
        rule_id="r1", name="Test",
        pattern={"intent": "*"}, decision=PingDecision.ACCEPT,
        zone=AirlockZone.GROEN,
    ))
    stats = airlock.stats()
    assert stats["rules"] == 1
    assert stats["pending_count"] == 0
