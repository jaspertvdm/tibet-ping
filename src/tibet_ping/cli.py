"""
tibet-ping CLI — protocol + transport in one tool.

Usage:
    tibet-ping <target>                 Ping a JIS DID (proto only)
    tibet-ping <ip-address>             Legacy ping (easter egg)
    tibet-ping demo                     Run proto demo
    tibet-ping listen [--port] [--did]  Start node, listen for pings
    tibet-ping send <did> <addr> <intent>   Send ping over UDP
    tibet-ping discover [--port] [--did]    Broadcast LAN discovery
    tibet-ping net-demo                 Run two-node transport demo
"""

import sys
import time
import random
import re

from . import __version__
from .node import PingNode
from .proto import PingType, PingDecision


# ── Easter Egg ───────────────────────────────────────────────

LIONEL_RICHIE_IPS = [
    "88.33.294.66",   # Not even a valid IP. Legend.
    "127.0.0.1",
    "0.0.0.0",
]

LEGACY_PAYLOADS = [
    '"Hello, is it me you\'re looking for?"',
    '"I\'ve been alone with you inside my mind"',
    '"You\'re once, twice, three times a lady"',
    '"Oh what a feeling, when we\'re dancing on the ceiling"',
    '"All night long (All night)"',
    '"Cause I wonder where you route, and I wonder what you do"',
    '"Are you somewhere feeling lonely, is someone pinging you?"',
    '"Tell me how to sync the state, for I haven\'t got a clue"',
    '"But let me start by saying... DROP PACKET. Who are you?"',
]

LEGACY_WARNINGS = [
    "Warning: Legacy ping rejected by TIBET-verify.",
    "Warning: No JIS identity. No intent. No trust. Just vibes.",
    "Warning: This packet has zero provenance. The CISO is crying.",
    "Warning: ICMP has no ERACHTER. Why are you even pinging?",
    "Warning: Nonce missing. Replay attack trivial. Lionel approves.",
]


def _is_ip_address(target: str) -> bool:
    """Check if target looks like an IP address (even invalid ones)."""
    return bool(re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', target))


def _easter_egg_legacy_ping(target: str) -> None:
    """Fake ICMP ping output with Lionel Richie wisdom."""
    print(f"PING {target} ({target}): 56 data bytes")

    for seq in range(4):
        time.sleep(0.3 + random.random() * 0.4)
        ttl = random.choice([52, 54, 56, 58, 60, 62, 64])
        ms = round(8 + random.random() * 30, 1)
        payload = random.choice(LEGACY_PAYLOADS)
        print(f"76 bytes from {target}: icmp_seq={seq} ttl={ttl} time={ms} ms")
        print(f'  Payload: {payload}')

    print()
    print(random.choice(LEGACY_WARNINGS))
    print("Upgrade to cryptographically verified intent:")
    print("  pip install tibet-ping")
    print("  https://pypi.org/project/tibet-ping/")
    print()
    print("  from tibet_ping import PingNode")
    print('  node = PingNode("jis:your:device")')
    print('  node.ping("jis:target:device", intent="hello", purpose="Actually useful")')


# ── Proto-only commands ──────────────────────────────────────

def _cmd_ping(target: str) -> None:
    """Ping a JIS DID (proto layer — creates packet, no transport)."""
    node = PingNode("jis:cli:local")
    pkt = node.ping(
        target=target,
        intent="discover",
        purpose="CLI ping",
    )
    print(f"TIBET-PING {target}")
    print(f"  Packet:  {pkt.packet_id}")
    print(f"  Intent:  {pkt.intent}")
    print(f"  Nonce:   {pkt.nonce[:16]}...")
    print(f"  Type:    {pkt.ping_type.value}")
    print()
    print("Use 'tibet-ping send' to send over UDP transport.")


def _cmd_demo() -> None:
    """Run the proto-level demo scenario."""
    from .airlock import AirlockRule, AirlockZone

    print("=" * 60)
    print(f"  tibet-ping v{__version__} — Protocol Demo")
    print("=" * 60)
    print()

    hub = PingNode("jis:home:hub")
    sensor = PingNode("jis:home:sensor_temp")
    stranger = PingNode("jis:evil:lockpicker")

    hub.set_trust("jis:home:sensor_temp", 0.9)

    # Test 1: Trusted
    pkt = sensor.ping("jis:home:hub", "temperature.report", "Reading", payload={"celsius": 21.5})
    resp = hub.receive(pkt)
    print(f"[1] Trusted sensor -> hub:  {resp.decision.value} ({resp.airlock_zone})")

    # Test 2: Stranger
    pkt = stranger.ping("jis:home:hub", "door.unlock", "Let me in")
    resp = hub.receive(pkt)
    print(f"[2] Stranger -> hub:        {resp.decision.value} ({resp.airlock_zone})")

    # Test 3: Replay
    pkt = sensor.ping("jis:home:hub", "temp.read", "Again")
    hub.receive(pkt)
    resp = hub.receive(pkt)
    print(f"[3] Replay attack:          {resp.decision.value} ({resp.payload.get('reason', '')})")

    # Test 4: Vouch
    hub.vouch(["jis:home:s1"], my_trust=0.9, vouch_factor=0.8)
    s1 = PingNode("jis:home:s1")
    pkt = s1.ping("jis:home:hub", "smoke.alert", "Smoke!")
    resp = hub.receive(pkt)
    print(f"[4] Vouched device -> hub:  {resp.decision.value} (trust: {resp.trust_score:.2f})")

    # Test 5: Beacon
    hub.beacon_handler.auto_vouch_rules = [{"name": "Sensors", "device_type": "sensor"}]
    new = PingNode("jis:home:new")
    b = new.broadcast_beacon(device_type="sensor")
    br = hub.handle_beacon(b)
    print(f"[5] Beacon auto-vouch:      {br.decision}")

    print()
    print("All systems nominal. No Lionel Richies were harmed.")


# ── Transport commands ───────────────────────────────────────

def _cmd_listen(args) -> None:
    """Start node, listen for incoming pings over UDP."""
    import asyncio
    from .transport.udp import TransportConfig, DEFAULT_PORT
    from .transport.iot_node import IoTNode

    port = getattr(args, 'port', DEFAULT_PORT)
    did = getattr(args, 'did', 'jis:iot:node')

    async def _run():
        config = TransportConfig(bind_port=port)
        node = IoTNode(did, config=config)
        await node.start()
        print(f"Listening on :{port} as {did}")
        print("Press Ctrl+C to stop")
        try:
            await asyncio.Event().wait()
        except (KeyboardInterrupt, asyncio.CancelledError):
            pass
        finally:
            await node.stop()

    asyncio.run(_run())


def _cmd_send(args) -> None:
    """Send a ping to a target over UDP."""
    import asyncio
    from .transport.udp import TransportConfig
    from .transport.iot_node import IoTNode

    host, port_str = args.addr.rsplit(":", 1)
    target_addr = (host, int(port_str))

    async def _run():
        config = TransportConfig(bind_port=args.port)
        node = IoTNode(args.my_did, config=config)
        await node.start()

        print(f"Sending ping to {args.did} at {args.addr}")
        print(f"  intent: {args.intent}")
        print(f"  purpose: {args.purpose}")

        try:
            response = await node.send_ping(
                target=args.did,
                addr=target_addr,
                intent=args.intent,
                purpose=args.purpose,
            )
            if response:
                print(f"\nResponse: {response.decision.value}")
                print(f"  zone: {response.airlock_zone}")
                print(f"  trust: {response.trust_score}")
                if response.payload:
                    print(f"  payload: {response.payload}")
            else:
                print("\nNo response (timeout)")
        finally:
            await node.stop()

    asyncio.run(_run())


def _cmd_discover(args) -> None:
    """Broadcast LAN discovery."""
    import asyncio
    from .transport.udp import TransportConfig, DEFAULT_PORT
    from .transport.iot_node import IoTNode

    port = getattr(args, 'port', DEFAULT_PORT)
    did = getattr(args, 'did', 'jis:iot:node')
    timeout = getattr(args, 'timeout', 5.0)

    async def _run():
        config = TransportConfig(bind_port=port)
        node = IoTNode(did, config=config)

        discovered: list[str] = []

        async def on_found(did_found: str, addr: tuple, resp: object) -> None:
            discovered.append(f"{did_found} at {addr[0]}:{addr[1]}")
            print(f"  Found: {did_found} at {addr[0]}:{addr[1]}")

        node.discovery.on_discovered(on_found)
        await node.start()

        print(f"Broadcasting discovery as {did}...")
        await node.discovery.broadcast_discover()

        print(f"Listening for {timeout}s...")
        await asyncio.sleep(timeout)

        await node.stop()
        print(f"\nDiscovered {len(discovered)} peer(s)")

    asyncio.run(_run())


def _cmd_net_demo() -> None:
    """Demo: two nodes on localhost, ping back and forth over UDP."""
    import asyncio
    from .transport.udp import TransportConfig
    from .transport.iot_node import IoTNode

    async def _run():
        print("=" * 60)
        print(f"  tibet-ping v{__version__} — Transport Demo")
        print("=" * 60)
        print()

        config_a = TransportConfig(bind_port=17150)
        config_b = TransportConfig(bind_port=17151)

        node_a = IoTNode("jis:demo:hub", config=config_a, heartbeat_interval=300, discovery_interval=300)
        node_b = IoTNode("jis:demo:sensor", config=config_b, heartbeat_interval=300, discovery_interval=300)

        node_a.set_trust("jis:demo:sensor", 0.9)

        await node_a.start()
        await node_b.start()

        print(f"Node A (hub):    {node_a.device_did} on :17150")
        print(f"Node B (sensor): {node_b.device_did} on :17151")
        print()

        # Sensor pings hub
        print("1. Sensor -> Hub: temperature.report")
        response = await node_b.send_ping(
            target="jis:demo:hub",
            addr=("127.0.0.1", 17150),
            intent="temperature.report",
            purpose="Demo temperature reading",
            payload={"celsius": 21.5},
        )

        if response:
            print(f"   Response: {response.decision.value} (zone: {response.airlock_zone})")
            print(f"   Trust: {response.trust_score}")
        else:
            print("   No response (timeout)")

        print()

        # Unknown node pings hub
        config_c = TransportConfig(bind_port=17152)
        node_c = IoTNode("jis:demo:unknown", config=config_c, heartbeat_interval=300, discovery_interval=300)
        await node_c.start()

        print("2. Unknown -> Hub: door.unlock (should be ROOD)")
        response = await node_c.send_ping(
            target="jis:demo:hub",
            addr=("127.0.0.1", 17150),
            intent="door.unlock",
            purpose="Unauthorized access attempt",
            timeout=3.0,
        )

        if response:
            print(f"   Response: {response.decision.value}")
        else:
            print("   No response (silent drop -- ROOD)")

        print()
        print("Hub stats:", node_a.stats()["peers"])

        await node_a.stop()
        await node_b.stop()
        await node_c.stop()
        print("\n=== Demo complete ===")

    asyncio.run(_run())


# ── Main entry point ─────────────────────────────────────────

def _usage() -> None:
    print(f"tibet-ping v{__version__}")
    print()
    print("Protocol commands:")
    print("  tibet-ping <jis:did>             Ping a JIS device (proto only)")
    print("  tibet-ping <ip-address>          Legacy ping (easter egg)")
    print("  tibet-ping demo                  Run protocol demo")
    print()
    print("Transport commands:")
    print("  tibet-ping listen [options]      Start node, listen for pings")
    print("    --port PORT                    UDP port (default: 7150)")
    print("    --did DID                      Device DID (default: jis:iot:node)")
    print()
    print("  tibet-ping send <did> <host:port> <intent> [options]")
    print("    --purpose PURPOSE              Purpose description")
    print("    --port PORT                    Local bind port (0=random)")
    print("    --my-did DID                   Our device DID")
    print()
    print("  tibet-ping discover [options]    Broadcast LAN discovery")
    print("    --port PORT                    UDP port (default: 7150)")
    print("    --did DID                      Device DID")
    print("    --timeout SECS                 Listen timeout (default: 5)")
    print()
    print("  tibet-ping net-demo              Run two-node transport demo")
    print()
    print("Examples:")
    print('  tibet-ping jis:home:hub')
    print('  tibet-ping 88.33.294.66')
    print('  tibet-ping listen --did jis:my:hub')
    print('  tibet-ping send jis:hub 192.168.1.10:7150 temperature.report')
    print('  tibet-ping discover --timeout 10')


def main() -> None:
    """CLI entry point."""
    import argparse

    # If no args or simple usage, use the lightweight path
    args = sys.argv[1:]

    if not args or args[0] in ("--help", "-h"):
        _usage()
        return

    command = args[0]

    # Simple commands (no argparse needed)
    if command == "demo":
        _cmd_demo()
        return
    elif _is_ip_address(command):
        _easter_egg_legacy_ping(command)
        return
    elif command not in ("listen", "send", "discover", "net-demo"):
        # Treat as JIS DID ping
        _cmd_ping(command)
        return

    # Transport commands — use argparse
    parser = argparse.ArgumentParser(prog="tibet-ping", add_help=False)
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command")

    # listen
    p_listen = sub.add_parser("listen")
    p_listen.add_argument("--port", type=int, default=7150)
    p_listen.add_argument("--did", default="jis:iot:node")

    # send
    p_send = sub.add_parser("send")
    p_send.add_argument("did")
    p_send.add_argument("addr")
    p_send.add_argument("intent")
    p_send.add_argument("--purpose", default="CLI ping")
    p_send.add_argument("--port", type=int, default=0)
    p_send.add_argument("--my-did", default="jis:iot:cli", dest="my_did")

    # discover
    p_disc = sub.add_parser("discover")
    p_disc.add_argument("--port", type=int, default=7150)
    p_disc.add_argument("--did", default="jis:iot:node")
    p_disc.add_argument("--timeout", type=float, default=5.0)

    # net-demo
    sub.add_parser("net-demo")

    parsed = parser.parse_args(args)

    if parsed.verbose:
        import logging
        logging.basicConfig(level=logging.DEBUG, format="%(name)s %(message)s")

    if parsed.command == "listen":
        _cmd_listen(parsed)
    elif parsed.command == "send":
        _cmd_send(parsed)
    elif parsed.command == "discover":
        _cmd_discover(parsed)
    elif parsed.command == "net-demo":
        _cmd_net_demo()


if __name__ == "__main__":
    main()
