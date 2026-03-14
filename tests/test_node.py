"""
End-to-end tests for PingNode.

Scenario:
    Node A (hub, trust 0.9) and Node B (hubby)
    A vouches for B
    B sends HEARTBEAT → A receives, GROEN zone
    Unknown Node C sends INTENT → GEEL zone (pending)
    Replay of B's packet → ROOD (nonce already seen)
    New Node D sends Beacon → BeaconHandler auto-vouches
"""

from tibet_ping import (
    PingNode,
    PingDecision,
    PingType,
    AirlockRule,
    AirlockZone,
)


def test_basic_ping_accepted():
    """Known + trusted device gets GROEN."""
    hub = PingNode("jis:home:hub")
    sensor = PingNode("jis:home:sensor")

    hub.set_trust("jis:home:sensor", 0.9)

    packet = sensor.ping(
        target="jis:home:hub",
        intent="temperature.report",
        purpose="Periodic temp reading",
        payload={"celsius": 21.5},
    )
    response = hub.receive(packet)

    assert response.decision == PingDecision.ACCEPT
    assert response.airlock_zone == "GROEN"
    assert response.trust_score == 0.9


def test_unknown_device_rejected():
    """Unknown device with 0 trust gets ROOD (silent drop)."""
    hub = PingNode("jis:home:hub")
    stranger = PingNode("jis:evil:hacker")

    packet = stranger.ping(
        target="jis:home:hub",
        intent="door.unlock",
        purpose="Let me in",
    )
    response = hub.receive(packet)

    assert response.decision == PingDecision.REJECT
    assert response.airlock_zone == "ROOD"


def test_medium_trust_pending():
    """Device with medium trust goes to GEEL (pending)."""
    hub = PingNode("jis:home:hub")
    hub.set_trust("jis:neighbor:device", 0.5)

    neighbor = PingNode("jis:neighbor:device")
    packet = neighbor.ping(
        target="jis:home:hub",
        intent="status.check",
        purpose="Checking if home system is online",
    )
    response = hub.receive(packet)

    assert response.decision == PingDecision.PENDING
    assert response.airlock_zone == "GEEL"
    assert packet.packet_id in hub.airlock.pending


def test_replay_attack_blocked():
    """Same packet sent twice → second is ROOD (replay)."""
    hub = PingNode("jis:home:hub")
    hub.set_trust("jis:home:sensor", 0.9)
    sensor = PingNode("jis:home:sensor")

    packet = sensor.ping(
        target="jis:home:hub",
        intent="temperature.read",
        purpose="Read temp",
    )

    # First ping: accepted
    resp1 = hub.receive(packet)
    assert resp1.decision == PingDecision.ACCEPT

    # Replay: rejected
    resp2 = hub.receive(packet)
    assert resp2.decision == PingDecision.REJECT
    assert resp2.payload.get("reason") == "replay_detected"


def test_vouching_flow():
    """Hub vouches for sensors → vouched sensor gets trust."""
    hub = PingNode("jis:home:hub")

    # Hub vouches for 3 sensors
    vouch = hub.vouch(
        vouched_dids=["jis:home:s1", "jis:home:s2", "jis:home:s3"],
        my_trust=0.9,
        vouch_factor=0.8,
        reason="My kitchen sensors",
    )
    assert abs(vouch.computed_trust - 0.72) < 0.001

    # s1 sends ping → hub should accept (0.72 > 0.7 threshold)
    s1 = PingNode("jis:home:s1")
    packet = s1.ping(
        target="jis:home:hub",
        intent="humidity.report",
        purpose="Humidity reading",
    )
    response = hub.receive(packet)

    assert response.decision == PingDecision.ACCEPT
    assert response.airlock_zone == "GROEN"
    assert abs(response.trust_score - 0.72) < 0.001


def test_beacon_bootstrap():
    """New device broadcasts beacon, hub auto-vouches."""
    hub = PingNode("jis:home:hub")
    hub.beacon_handler.auto_vouch_rules = [
        {
            "name": "Kitchen sensors",
            "device_type": "sensor",
            "pod_id": "pod_kitchen",
        }
    ]

    new_device = PingNode("jis:new:temp_sensor")
    beacon = new_device.broadcast_beacon(
        capabilities=["temperature"],
        device_type="sensor",
        requested_pod="pod_kitchen",
    )

    response = hub.handle_beacon(beacon)
    assert response.decision == "auto_vouched"
    assert response.assigned_pod == "pod_kitchen"


def test_beacon_hitl_escalation():
    """Unknown device type → HITL."""
    hub = PingNode("jis:home:hub")
    hitl_queue = []
    hub.beacon_handler.on_hitl_needed = lambda b: hitl_queue.append(b)

    unknown = PingNode("jis:unknown:device")
    beacon = unknown.broadcast_beacon(
        capabilities=["unknown_cap"],
        device_type="mystery",
    )

    response = hub.handle_beacon(beacon)
    assert response.decision == "hitl_pending"
    assert len(hitl_queue) == 1


def test_airlock_rule_override():
    """Rules can override trust-based decisions."""
    hub = PingNode("jis:home:hub")
    hub.add_rule(AirlockRule(
        rule_id="r1",
        name="All home temp reads are OK",
        pattern={"source_did": "jis:home:*", "intent": "temperature.*"},
        decision=PingDecision.ACCEPT,
        zone=AirlockZone.GROEN,
    ))

    # Even with 0 trust, rule allows it
    sensor = PingNode("jis:home:new_sensor")
    packet = sensor.ping(
        target="jis:home:hub",
        intent="temperature.read",
        purpose="I'm new but I'm from home",
    )
    response = hub.receive(packet)
    assert response.decision == PingDecision.ACCEPT
    assert response.applied_rule == "All home temp reads are OK"


def test_heartbeat():
    hub = PingNode("jis:home:hub")
    sensor = PingNode("jis:home:sensor")
    hub.set_trust("jis:home:sensor", 0.8)

    packet = sensor.heartbeat(
        target="jis:home:hub",
        status={"battery": 85, "uptime_hours": 720},
    )
    assert packet.ping_type == PingType.HEARTBEAT

    response = hub.receive(packet)
    assert response.decision == PingDecision.ACCEPT


def test_discover():
    hub = PingNode("jis:home:hub")
    packet = hub.discover(capabilities=["temperature", "humidity"])
    assert packet.ping_type == PingType.DISCOVER
    assert packet.target_did == "broadcast"
    assert packet.payload["requested_capabilities"] == ["temperature", "humidity"]


def test_topology_via_node():
    hub = PingNode("jis:home:hub")
    pod = hub.create_pod("pod_kitchen", "Kitchen", capabilities={"temperature"})
    assert pod.hub_did == "jis:home:hub"
    assert pod.pod_id == "pod_kitchen"


def test_stats():
    hub = PingNode("jis:home:hub")
    hub.set_trust("jis:s1", 0.9)
    hub.vouch(["jis:s2"], my_trust=0.9)

    stats = hub.stats()
    assert stats["device_did"] == "jis:home:hub"
    assert stats["vouching"]["total_vouches"] == 1
