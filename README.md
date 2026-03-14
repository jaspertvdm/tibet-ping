# tibet-ping

**Intent-based discovery and communication protocol with TIBET provenance.**

ICMP ping is dumb: "are you there?" → "yes". No identity, no intent, no trust.

tibet-ping replaces this with a TIBET token as handshake. Every ping carries identity (JIS), intent, context, and purpose. Responses are trust-gated through Airlock zones.

## Features

- **PingPacket** — TIBET-backed ping with identity, intent, context, purpose
- **NonceTracker** — Replay protection (30-second time window)
- **Airlock** — Trust-gated access (GROEN/GEEL/ROOD zones) with rules engine
- **Vouching** — Trust delegation for device groups (solves HITL scaling)
- **Topology** — Hub/Hubby/Pod/Station network modeling
- **Beacon** — Airgapped bootstrap for new devices (chicken-and-egg solved)

## Quick Start

```python
from tibet_ping import PingNode, PingDecision

# Create nodes
hub = PingNode("jis:home:hub")
sensor = PingNode("jis:home:sensor_temp")

# Hub trusts sensor
hub.set_trust("jis:home:sensor_temp", 0.9)

# Sensor pings hub
packet = sensor.ping(
    target="jis:home:hub",
    intent="temperature.report",
    purpose="Periodic temperature reading",
    payload={"celsius": 21.5},
)

# Hub receives and processes
response = hub.receive(packet)
assert response.decision == PingDecision.ACCEPT
assert response.airlock_zone == "GROEN"
```

## Airlock Zones

| Zone | Trust | Action |
|------|-------|--------|
| **GROEN** | >= 0.7 | Auto-allow |
| **GEEL** | 0.3 - 0.7 | Pending (rules or HITL) |
| **ROOD** | < 0.3 | Silent drop |

## Vouching (HITL Scaling)

```python
# Hub vouches for 50 sensors at once
hub.vouch(
    vouched_dids=["jis:home:s1", "jis:home:s2", ...],
    my_trust=0.9,
    vouch_factor=0.7,  # Vouched trust = 0.9 * 0.7 = 0.63
)
```

## Beacon Bootstrap

```python
# New device broadcasts beacon (no secrets!)
beacon = new_device.broadcast_beacon(
    capabilities=["temperature"],
    device_type="sensor",
)

# Hub auto-vouches or escalates to HITL
response = hub.handle_beacon(beacon)
```

## License

MIT — Humotica AI Lab 2025-2026
