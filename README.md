# tibet-ping

**Intent-based discovery and communication protocol with TIBET provenance.**

[![PyPI](https://img.shields.io/pypi/v/tibet-ping)](https://pypi.org/project/tibet-ping/)

ICMP ping is dumb: "are you there?" → "yes". No identity, no intent, no trust.

tibet-ping replaces this with a TIBET token as handshake. Every ping carries identity (JIS), intent, context, and purpose. Responses are trust-gated through Airlock zones.

## How It Fits Together

```
tibet-core          tibet-ping           tibet-iot
(provenance)        (protocol)           (transport)
 Token, Chain  ───►  PingPacket    ───►  UDP, multicast
 Store, HMAC        Airlock, Trust       LAN discovery
 NetworkBridge      Vouching, Beacon     Mesh relay
```

- **tibet-core** stores every action as an immutable token
- **tibet-ping** defines the protocol — packets, trust zones, vouching (this package)
- **tibet-iot** sends them over the wire — UDP, multicast discovery, mesh relay

## Install

```bash
pip install tibet-ping
```

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

Three-zone trust model. No configuration needed — just set trust scores.

| Zone | Trust | Action |
|------|-------|--------|
| **GROEN** | >= 0.7 | Auto-allow |
| **GEEL** | 0.3 - 0.7 | Pending (rules or HITL) |
| **ROOD** | < 0.3 | Silent drop |

ROOD doesn't reject — it stays silent. Unknown devices get no signal at all.

## Features

### PingPacket
TIBET-backed ping with identity, intent, context, purpose. Every field maps to TIBET provenance:

| Packet field | TIBET dimension |
|-------------|----------------|
| `intent`, `purpose`, `payload` | ERIN (content) |
| `source_did`, `target_did` | ERAAN (references) |
| `routing_mode`, `hop_count`, `pod_id` | EROMHEEN (context) |
| `purpose` | ERACHTER (intent) |

### NonceTracker
Replay protection with 30-second time window. Same nonce twice → rejected.

### Vouching (HITL Scaling)

Trust 1 device manually, let it vouch for 50 more:

```python
# Hub vouches for 50 sensors at once
hub.vouch(
    vouched_dids=["jis:home:s1", "jis:home:s2", ...],
    my_trust=0.9,
    vouch_factor=0.7,  # Vouched trust = 0.9 * 0.7 = 0.63 (GEEL)
)
```

### Beacon Bootstrap

New device joins network without pre-shared secrets:

```python
# New device broadcasts beacon (no secrets!)
beacon = new_device.broadcast_beacon(
    capabilities=["temperature"],
    device_type="sensor",
)

# Hub auto-vouches or escalates to HITL
response = hub.handle_beacon(beacon)
```

### Topology

Network modeling with roles:

| Role | Description |
|------|-------------|
| **Hub** | Central node, high trust |
| **Hubby** | Backup hub, fails over |
| **Pod** | Logical group of devices |
| **Station** | Edge device, leaf node |

## CLI

```bash
# Ping a device
tibet-ping jis:home:sensor --intent temperature.read

# Short alias
tping jis:home:sensor --intent temperature.read
```

## Sending Over the Network

tibet-ping is the protocol layer — it creates packets but doesn't send them. For actual UDP transport, LAN discovery, and mesh relay, use **tibet-iot**:

```bash
pip install tibet-iot
```

```python
from tibet_iot import IoTNode

async def main():
    node = IoTNode("jis:home:hub")
    node.set_trust("jis:home:sensor", 0.9)
    await node.start()

    # Send a real ping over UDP
    response = await node.send_ping(
        target="jis:home:sensor",
        addr=("192.168.1.42", 7150),
        intent="temperature.read",
    )
    await node.stop()
```

## Recording Provenance

Every ping can become an immutable audit token via **tibet-core** NetworkBridge:

```python
from tibet_core import Provider, NetworkBridge

tibet = Provider(actor="jis:home:hub")
bridge = NetworkBridge(tibet)

# PingPacket → Token (automatic provenance mapping)
token = bridge.record_ping(packet, response)
assert token.verify()
```

## License

MIT — Humotica

## Links

- [tibet-core](https://pypi.org/project/tibet-core/) — Provenance engine (tokens, chains, stores)
- [tibet-iot](https://pypi.org/project/tibet-iot/) — UDP transport, LAN discovery, mesh relay
- [tibet-overlay](https://pypi.org/project/tibet-overlay/) — Encrypted mesh networking
- [Humotica](https://humotica.com)
- [IETF TIBET Draft](https://datatracker.ietf.org/doc/draft-vandemeent-tibet-provenance/)
- [IETF JIS Draft](https://datatracker.ietf.org/doc/draft-vandemeent-jis-identity/)
