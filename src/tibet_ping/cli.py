"""
tibet-ping CLI.

Usage:
    tibet-ping <target>              # Ping a JIS DID
    tibet-ping discover              # Broadcast discovery
    tibet-ping demo                  # Run full demo scenario
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


# ── Real CLI ─────────────────────────────────────────────────

def _cmd_ping(target: str) -> None:
    """Ping a JIS DID."""
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
    print("Proto layer only — no transport yet.")
    print("Packet created but not sent (tibet-iot coming soon).")


def _cmd_demo() -> None:
    """Run the full demo scenario."""
    from .node import PingNode
    from .airlock import AirlockRule, AirlockZone

    print("=" * 60)
    print(f"  tibet-ping v{__version__} — Demo")
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


def _usage() -> None:
    print(f"tibet-ping v{__version__}")
    print()
    print("Usage:")
    print("  tibet-ping <jis:did>       Ping a JIS device identity")
    print("  tibet-ping <ip-address>    Legacy ping (easter egg)")
    print("  tibet-ping demo            Run demo scenario")
    print("  tibet-ping --help          Show this help")
    print()
    print("Examples:")
    print('  tibet-ping jis:home:hub')
    print('  tibet-ping 88.33.294.66')
    print('  tibet-ping demo')


def main() -> None:
    """CLI entry point."""
    args = sys.argv[1:]

    if not args or args[0] in ("--help", "-h"):
        _usage()
        return

    target = args[0]

    if target == "demo":
        _cmd_demo()
    elif _is_ip_address(target):
        _easter_egg_legacy_ping(target)
    else:
        _cmd_ping(target)


if __name__ == "__main__":
    main()
