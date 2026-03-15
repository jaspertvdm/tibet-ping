# tibet-ping

**Intent-based device communication with built-in UDP transport.**

[![PyPI](https://img.shields.io/pypi/v/tibet-ping)](https://pypi.org/project/tibet-ping/)
[![Python](https://img.shields.io/pypi/pyversions/tibet-ping)](https://pypi.org/project/tibet-ping/)
[![License](https://img.shields.io/pypi/l/tibet-ping)](https://pypi.org/project/tibet-ping/)

ICMP ping is dumb: "are you there?" → "yes". No identity, no intent, no trust.

tibet-ping replaces this with a full protocol stack. Every ping carries identity (JIS), intent, context, and purpose. Responses are trust-gated through Airlock zones. Transport is built-in — UDP, LAN discovery, mesh relay. One `pip install`, two machines talking.

## Install

```bash
pip install tibet-ping
```

Optional: msgpack for smaller wire frames (JSON is default):
```bash
pip install tibet-ping[msgpack]
```

> **Upgrading from tibet-iot?** The transport layer is now part of tibet-ping.
> `pip install tibet-ping>=0.2.0 && pip uninstall tibet-iot`

## Two Machines Talking (60 seconds)

### Machine A — Hub (receiver)

```python
# hub.py
import asyncio
from tibet_ping.transport import IoTNode

async def main():
    hub = IoTNode("jis:office:hub")
    hub.set_trust("jis:office:sensor", 0.9)  # Trust the sensor

    await hub.start()
    print(f"Hub listening on :7150")

    # Keep running until Ctrl+C
    try:
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        pass
    finally:
        await hub.stop()

asyncio.run(main())
```

### Machine B — Sensor (sender)

```python
# sensor.py
import asyncio
from tibet_ping.transport import IoTNode

async def main():
    sensor = IoTNode("jis:office:sensor")
    await sensor.start()

    response = await sensor.send_ping(
        target="jis:office:hub",
        addr=("192.168.1.10", 7150),  # Hub's IP
        intent="temperature.report",
        purpose="Periodic reading",
        payload={"celsius": 21.5},
    )

    if response:
        print(f"Decision: {response.decision.value}")  # accept
        print(f"Zone:     {response.airlock_zone}")     # GROEN
        print(f"Trust:    {response.trust_score}")       # 0.9
    else:
        print("No response (ROOD — silent drop)")

    await sensor.stop()

asyncio.run(main())
```

Run `python hub.py` on machine A, then `python sensor.py` on machine B. The sensor sends a TIBET-backed ping, the hub checks trust, and responds through the Airlock.

### Or use the CLI

```bash
# Machine A — listen
tibet-ping listen --did jis:office:hub

# Machine B — send
tibet-ping send jis:office:hub 192.168.1.10:7150 temperature.report
```

## What Happens on the Wire

```
Sensor                          Hub
  │                              │
  │  PingPacket (UDP :7150)      │
  │  ┌─────────────────────┐    │
  │  │ source: jis:sensor   │    │
  │  │ target: jis:hub      │    │
  │  │ intent: temp.report  │    │
  │  │ nonce: a3f8c...      │────►  1. Decode packet
  │  │ payload: {celsius:21}│    │   2. Check nonce (replay?)
  │  └─────────────────────┘    │   3. Lookup trust score
  │                              │   4. Airlock gate → GROEN
  │  PingResponse (UDP)          │
  │  ┌─────────────────────┐    │
  │  │ decision: ACCEPT     │◄───│   5. Send response
  │  │ zone: GROEN          │    │
  │  │ trust: 0.9           │    │
  │  └─────────────────────┘    │
  │                              │
```

Wire format: 8-byte header (`TP` magic + version + flags + length) + JSON payload. With `[msgpack]` extra: binary msgpack for ~40% smaller frames.

## Airlock Zones

Three-zone trust model. No configuration needed — just set trust scores.

| Zone | Trust | What happens |
|------|-------|--------------|
| **GROEN** | >= 0.7 | Accept — response sent back |
| **GEEL** | 0.3 – 0.7 | Pending — rules or HITL decides |
| **ROOD** | < 0.3 | Silent drop — no response, no signal |

ROOD doesn't reject — it stays silent. Unknown devices get nothing. No error, no hint they were heard. This is by design.

## LAN Discovery

Find devices on the local network without knowing IPs:

```python
from tibet_ping.transport import IoTNode

async def main():
    node = IoTNode("jis:office:hub")

    async def on_found(did, addr, response):
        print(f"Found {did} at {addr[0]}:{addr[1]}")

    node.discovery.on_discovered(on_found)
    await node.start()

    # Broadcast discovery beacon
    await node.discovery.broadcast_discover()

    await asyncio.sleep(5)  # Listen for responses
    await node.stop()
```

Discovery uses multicast group `224.0.71.50:7151`. Devices respond with their DID and capabilities.

```bash
# CLI
tibet-ping discover --timeout 10
```

## Mesh Relay

Packets with `routing_mode=MESH` are automatically forwarded through intermediate nodes:

```python
from tibet_ping import PingNode, RoutingMode

node = PingNode("jis:sensor")
packet = node.ping(
    target="jis:gateway",
    intent="data.forward",
    purpose="Multi-hop delivery",
    routing_mode=RoutingMode.MESH,
)
```

Relay features:
- **Hop counting** — `max_hops` prevents infinite forwarding (default: 10)
- **Loop detection** — seen-packet cache drops duplicates
- **Cache eviction** — oldest half evicted when cache is full

## Protocol Layer (without transport)

You can also use tibet-ping as a pure protocol library — create packets, check trust, process responses — without any network I/O:

```python
from tibet_ping import PingNode, PingDecision

hub = PingNode("jis:home:hub")
sensor = PingNode("jis:home:sensor")

hub.set_trust("jis:home:sensor", 0.9)

# Create packet (no network)
packet = sensor.ping(
    target="jis:home:hub",
    intent="temperature.report",
    purpose="Reading",
    payload={"celsius": 21.5},
)

# Process locally (no network)
response = hub.receive(packet)
assert response.decision == PingDecision.ACCEPT
assert response.airlock_zone == "GROEN"
```

This is useful for testing, simulation, or embedding the trust protocol in your own transport.

## Vouching (Scale Trust)

Trust 1 device manually, let it vouch for 50:

```python
hub.vouch(
    vouched_dids=["jis:home:s1", "jis:home:s2", ...],
    my_trust=0.9,
    vouch_factor=0.7,  # Vouched trust = 0.9 * 0.7 = 0.63 (GEEL)
)
```

## Beacon Bootstrap

New device joins network without pre-shared secrets:

```python
# New device broadcasts beacon
beacon = new_device.broadcast_beacon(
    capabilities=["temperature", "humidity"],
    device_type="sensor",
)

# Hub handles with auto-vouch rules or HITL escalation
response = hub.handle_beacon(beacon)
```

## TIBET Provenance Mapping

Every packet field maps to a TIBET dimension:

| Packet field | TIBET dimension | Meaning |
|-------------|----------------|---------|
| `intent`, `purpose`, `payload` | **ERIN** | What's in the action |
| `source_did`, `target_did` | **ERAAN** | Who's involved |
| `routing_mode`, `hop_count`, `pod_id` | **EROMHEEN** | Context around it |
| `purpose` | **ERACHTER** | Why this action |

Record provenance with tibet-core's NetworkBridge:

```python
from tibet_core import Provider, NetworkBridge

bridge = NetworkBridge(Provider(actor="jis:home:hub"))
token = bridge.record_ping(packet, response)  # Immutable audit token
```

## Topology

Network modeling with roles:

| Role | Description |
|------|-------------|
| **Hub** | Central node, high trust |
| **Hubby** | Backup hub, failover |
| **Pod** | Logical group of devices |
| **Station** | Edge device, leaf node |

## CLI Reference

```bash
# Protocol (no network)
tibet-ping jis:home:hub              # Create packet (proto only)
tibet-ping demo                       # Run trust demo
tibet-ping 88.33.294.66              # Easter egg

# Transport (real network)
tibet-ping listen [--port 7150] [--did jis:iot:node]
tibet-ping send <did> <host:port> <intent> [--purpose "..."]
tibet-ping discover [--port 7150] [--timeout 5]
tibet-ping net-demo                   # Two-node localhost demo
```

## Architecture

```
tibet-ping v0.2.0
├── Protocol layer (sync)
│   ├── PingNode          — create packets, process responses
│   ├── PingPacket        — identity, intent, nonce, payload
│   ├── Airlock           — three-zone trust gate
│   ├── NonceTracker      — replay protection
│   ├── VouchRegistry     — delegated trust
│   ├── BeaconHandler     — new device onboarding
│   └── Topology          — pod/hub/station modeling
│
└── Transport layer (async)
    ├── IoTNode           — main entry point (composes all below)
    ├── UDPTransport      — async UDP via DatagramProtocol
    ├── PacketCodec       — wire format (8-byte header + JSON/msgpack)
    ├── PeerTracker       — connection tracking, liveness
    ├── MeshRelay         — multi-hop forwarding, loop detection
    └── NetworkDiscovery  — multicast LAN discovery (224.0.71.50)
```

## How It Fits in the Ecosystem

```
tibet-core             tibet-ping              tibet-cortex
(provenance)           (protocol + transport)  (vector search)
 Token, Chain    ───►   PingPacket, Airlock     Airlock chunks
 Store, HMAC            IoTNode, UDP            JIS-gated search
 NetworkBridge          Discovery, Relay        Encrypted memory
```

- **[tibet-core](https://pypi.org/project/tibet-core/)** — Immutable provenance tokens
- **[tibet-ping](https://pypi.org/project/tibet-ping/)** — Protocol + transport (this package)
- **[tibet-cortex](https://pypi.org/project/tibet-cortex/)** — Vector search with Airlock
- **[tibet-overlay](https://pypi.org/project/tibet-overlay/)** — Encrypted mesh networking

## License

MIT — [Humotica](https://humotica.com)

## Links

- [PyPI](https://pypi.org/project/tibet-ping/)
- [GitHub](https://github.com/Humotica/tibet-ping)
- [IETF TIBET Draft](https://datatracker.ietf.org/doc/draft-vandemeent-tibet-provenance/)
- [IETF JIS Draft](https://datatracker.ietf.org/doc/draft-vandemeent-jis-identity/)
