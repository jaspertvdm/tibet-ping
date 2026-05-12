"""
tibet-ping CLI — protocol + transport + MUX diagnostics in one tool.

Usage:
    tibet-ping <target>                 Ping a JIS DID (proto only)
    tibet-ping <ip-address>             Legacy ping (easter egg)
    tibet-ping <name>.aint              Probe an AInternet-style target
    tibet-ping demo                     Run proto demo
    tibet-ping listen [--port] [--did]  Start node, listen for pings
    tibet-ping send <did> <addr> <intent>   Send ping over UDP
    tibet-ping discover [--port] [--did]    Broadcast LAN discovery
    tibet-ping net-demo                 Run two-node transport demo
    tibet-ping mux <host:port>          ClusterMux diagnostics (RTT, bench, verify)
    tibet-ping stack [--mux ...]        Full TIBET stack health check
"""

import sys
import time
import random
import re
import json
import urllib.request
import urllib.error

from . import __version__
from .node import PingNode
from .proto import PingType, PingDecision


PROBE_JSON_OUTPUT = False


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


# ── Probe commands ───────────────────────────────────────────

def _probe_result(
    probe: str,
    target: str,
    reachable: bool,
    verdict: str,
    latency_ms: float | None = None,
    identity: str | None = None,
    notes: list[str] | None = None,
    extras: dict | None = None,
) -> dict:
    """Build a uniform probe result object."""
    result = {
        "probe": probe,
        "target": target,
        "reachable": reachable,
        "verdict": verdict,
        "notes": notes or [],
    }
    if latency_ms is not None:
        result["latency_ms"] = round(latency_ms, 1)
    if identity:
        result["identity"] = identity
    if extras:
        result.update(extras)
    return result


def _print_probe_result(
    probe: str,
    target: str,
    reachable: bool,
    verdict: str,
    latency_ms: float | None = None,
    identity: str | None = None,
    notes: list[str] | None = None,
    extras: dict | None = None,
) -> None:
    """Render a uniform probe result."""
    result = _probe_result(
        probe=probe,
        target=target,
        reachable=reachable,
        verdict=verdict,
        latency_ms=latency_ms,
        identity=identity,
        notes=notes,
        extras=extras,
    )
    if PROBE_JSON_OUTPUT:
        print(json.dumps(result, indent=2, sort_keys=True))
        return

    print(f"probe:      {probe}")
    print(f"target:     {target}")
    print(f"reachable:  {'yes' if reachable else 'no'}")
    if latency_ms is not None:
        print(f"latency:    {latency_ms:.1f} ms")
    if identity:
        print(f"identity:   {identity}")
    print(f"verdict:    {verdict}")
    if notes:
        print("notes:")
        for note in notes:
            print(f"  - {note}")
    if extras:
        for key, value in extras.items():
            print(f"{key}:   {value}")


def _cmd_probe_ains(target: str, base_url: str) -> None:
    """Probe AINS resolution surface."""
    url = f"{base_url.rstrip('/')}/resolve/{target}"
    t0 = time.time()
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            latency_ms = (time.time() - t0) * 1000
            data = json.loads(body)
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, OSError) as e:
        _print_probe_result(
            probe="ains",
            target=target,
            reachable=False,
            verdict="unreachable",
            notes=[str(e)],
        )
        return

    if data.get("status") == "found":
        record = data.get("record", {})
        notes = []
        if "trust_score" in record:
            notes.append(f"trust_score={record['trust_score']}")
        caps = record.get("capabilities") or []
        if caps:
            notes.append("capabilities=" + ",".join(caps[:5]) + ("..." if len(caps) > 5 else ""))
        _print_probe_result(
            probe="ains",
            target=target,
            reachable=True,
            latency_ms=latency_ms,
            identity=data.get("domain", target),
            verdict="resolved",
            notes=notes or ["record found"],
        )
    else:
        _print_probe_result(
            probe="ains",
            target=target,
            reachable=True,
            latency_ms=latency_ms,
            verdict="no-record",
            notes=["AINS responded but no record matched"],
        )


def _cmd_probe_did(target: str, base_url: str) -> None:
    """Probe/parse a JIS-style DID-ish target and optionally enrich via AINS."""
    if not target.startswith("jis:"):
        _print_probe_result(
            probe="did",
            target=target,
            reachable=False,
            verdict="invalid",
            notes=["target must start with 'jis:'"],
        )
        return

    after = target[4:]
    host_hint = None
    ident_part = after
    if "@" in after:
        ident_part, host_hint = after.rsplit("@", 1)

    ident_segments = [seg for seg in ident_part.split(":") if seg]
    notes = []
    if ident_segments:
        notes.append(f"segments={len(ident_segments)}")
        notes.append(f"identity-spec={'/'.join(ident_segments)}")
    else:
        notes.append("empty identity spec after jis:")

    if host_hint:
        notes.append(f"host-hint={host_hint}")

    # Optional AINS enrichment: if a host hint exists, try that first.
    ains_target = host_hint or ident_segments[-1] if ident_segments else None
    if ains_target:
        url = f"{base_url.rstrip('/')}/resolve/{ains_target}"
        t0 = time.time()
        try:
            with urllib.request.urlopen(url, timeout=5) as resp:
                body = resp.read().decode("utf-8", errors="replace")
                latency_ms = (time.time() - t0) * 1000
                data = json.loads(body)
            if data.get("status") == "found":
                record = data.get("record", {})
                if "trust_score" in record:
                    notes.append(f"ains_trust={record['trust_score']}")
                caps = record.get("capabilities") or []
                if caps:
                    notes.append(
                        "ains_caps=" + ",".join(caps[:5]) +
                        ("..." if len(caps) > 5 else "")
                    )
                _print_probe_result(
                    probe="did",
                    target=target,
                    reachable=True,
                    latency_ms=latency_ms,
                    identity=target,
                    verdict="parsed+ains",
                    notes=notes,
                )
                return
            notes.append("ains=no-record")
        except (urllib.error.URLError, urllib.error.HTTPError,
                json.JSONDecodeError, OSError):
            notes.append("ains=unavailable")

    _print_probe_result(
        probe="did",
        target=target,
        reachable=True,
        identity=target,
        verdict="parsed",
        notes=notes,
    )


def _cmd_probe_aint(target: str, base_url: str) -> None:
    """Probe an .aint target via shape validation + AINS lookup."""
    if not target.endswith(".aint"):
        _print_probe_result(
            probe="aint",
            target=target,
            reachable=False,
            verdict="invalid",
            notes=["target must end with '.aint'"],
        )
        return

    stem = target[:-5]
    labels = [label for label in stem.split(".") if label]
    notes = [f"labels={len(labels)}"] if labels else ["empty .aint stem"]
    if labels:
        notes.append(f"route-shape={'/'.join(labels)}")

    url = f"{base_url.rstrip('/')}/resolve/{target}"
    t0 = time.time()
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            latency_ms = (time.time() - t0) * 1000
            data = json.loads(body)
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, OSError) as e:
        _print_probe_result(
            probe="aint",
            target=target,
            reachable=False,
            verdict="unreachable",
            notes=notes + [str(e)],
        )
        return

    if data.get("status") == "found":
        record = data.get("record", {})
        if "trust_score" in record:
            notes.append(f"trust_score={record['trust_score']}")
        caps = record.get("capabilities") or []
        if caps:
            notes.append("capabilities=" + ",".join(caps[:5]) + ("..." if len(caps) > 5 else ""))
        _print_probe_result(
            probe="aint",
            target=target,
            reachable=True,
            latency_ms=latency_ms,
            identity=data.get("domain", target),
            verdict="resolved",
            notes=notes,
        )
    else:
        _print_probe_result(
            probe="aint",
            target=target,
            reachable=True,
            latency_ms=latency_ms,
            verdict="no-record",
            notes=notes + ["AINS responded but no .aint record matched"],
        )


def _cmd_probe_continuityd(target: str) -> None:
    """Probe continuityd HTTP inbox/liveness surface."""
    base = target.rstrip("/")
    if not (base.startswith("http://") or base.startswith("https://")):
        base = f"http://{base}"

    notes: list[str] = []

    # First try bare root info surface.
    t0 = time.time()
    try:
        with urllib.request.urlopen(base + "/", timeout=5) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            latency_ms = (time.time() - t0) * 1000
            status = resp.getcode()
    except (urllib.error.URLError, urllib.error.HTTPError, OSError) as e:
        _print_probe_result(
            probe="continuityd",
            target=base,
            reachable=False,
            verdict="unreachable",
            notes=[str(e)],
        )
        return

    if status in (200, 201):
        body_one_line = " ".join(body.strip().splitlines()[:1])[:120]
        if body_one_line:
            notes.append(body_one_line)
        # Then probe the inbox path shape with a harmless HEAD-like GET expectation.
        inbox_hint = base + "/inbox/"
        notes.append(f"inbox-surface={inbox_hint}<filename>")
        _print_probe_result(
            probe="continuityd",
            target=base,
            reachable=True,
            latency_ms=latency_ms,
            verdict="live",
            notes=notes,
        )
    else:
        _print_probe_result(
            probe="continuityd",
            target=base,
            reachable=True,
            latency_ms=latency_ms,
            verdict=f"http-{status}",
            notes=notes,
        )


def _cmd_probe_listener(target: str) -> None:
    """Probe continuityd as a listener surface for quick host/mobile validation."""
    base = target.rstrip("/")
    if not (base.startswith("http://") or base.startswith("https://")):
        base = f"http://{base}"

    notes: list[str] = [
        "passive-check",
        "no test object written",
        "good for laptop/mobile/termux edge validation",
    ]

    t0 = time.time()
    try:
        with urllib.request.urlopen(base + "/", timeout=5) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            latency_ms = (time.time() - t0) * 1000
            status = resp.getcode()
    except (urllib.error.URLError, urllib.error.HTTPError, OSError) as e:
        _print_probe_result(
            probe="listener",
            target=base,
            reachable=False,
            verdict="unreachable",
            notes=notes + [str(e)],
        )
        return

    if status in (200, 201):
        first_line = " ".join(body.strip().splitlines()[:1])[:120]
        if first_line:
            notes.append(first_line)
        notes.append(f"inbox={base}/inbox/<filename>")
        _print_probe_result(
            probe="listener",
            target=base,
            reachable=True,
            latency_ms=latency_ms,
            verdict="listening",
            notes=notes,
        )
    else:
        _print_probe_result(
            probe="listener",
            target=base,
            reachable=True,
            latency_ms=latency_ms,
            verdict=f"http-{status}",
            notes=notes,
        )


def _cmd_probe_handoff(target: str, active: bool, reply_to: str | None = None) -> None:
    """Probe a continuityd handoff path, passively by default or actively via HTTP POST."""
    base = target.rstrip("/")
    if not (base.startswith("http://") or base.startswith("https://")):
        base = f"http://{base}"

    if not active:
        _print_probe_result(
            probe="handoff",
            target=base,
            reachable=True,
            verdict="dry-run",
            notes=[
                "handoff probe requires --active to write a tiny test object",
                "use listener probe for passive validation",
                "future versions can layer causal ACK timing above this",
            ],
            extras={
                "phase": "transport+ingress only",
                "ack_ready": False,
            },
        )
        return

    filename = f"tping-handoff-{int(time.time())}.probe"
    probe_ref = filename
    short_id = "".join(c for c in probe_ref if c.isalnum())[:12] or "unknown"
    ack_surface_hint = f"ack-of-{short_id}"
    payload = (
        "TPING-HANDOFF-PROBE-V1\n"
        "intent=probe.handoff\n"
        "purpose=active continuityd ingress validation\n"
    ).encode("utf-8")
    url = f"{base}/inbox/{filename}"
    notes = [
        "active-write",
        f"filename={filename}",
        f"bytes={len(payload)}",
        "measures transport + ingress acceptance, not full causal completion",
    ]
    extras = {
        "phase": "transport+ingress acceptance",
        "probe_ref": probe_ref,
        "ack_surface_hint": ack_surface_hint,
        "ack_ready": bool(reply_to),
    }
    if reply_to:
        notes.append(f"reply_to={reply_to}")
        extras["reply_to"] = reply_to
        extras["ack_command_hint"] = (
            f'tcd ack "{probe_ref}" --to {reply_to} '
            f'--note "ack for {probe_ref}"'
        )

    req = urllib.request.Request(url, data=payload, method="POST")
    req.add_header("Content-Type", "application/octet-stream")

    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            latency_ms = (time.time() - t0) * 1000
            status = resp.getcode()
            body = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        latency_ms = (time.time() - t0) * 1000
        body = e.read().decode("utf-8", errors="replace")
        _print_probe_result(
            probe="handoff",
            target=base,
            reachable=True,
            latency_ms=latency_ms,
            verdict=f"http-{e.code}",
            notes=notes + [str(e), body[:120] if body else "no body"],
            extras=extras,
        )
        return
    except (urllib.error.URLError, OSError) as e:
        _print_probe_result(
            probe="handoff",
            target=base,
            reachable=False,
            verdict="unreachable",
            notes=notes + [str(e)],
            extras=extras,
        )
        return

    if status in (200, 201, 202):
        response_hint = " ".join(body.strip().splitlines()[:1])[:120]
        if response_hint:
            notes.append(response_hint)
        _print_probe_result(
            probe="handoff",
            target=base,
            reachable=True,
            latency_ms=latency_ms,
            verdict="accepted",
            notes=notes,
            extras=extras,
        )
    else:
        _print_probe_result(
            probe="handoff",
            target=base,
            reachable=True,
            latency_ms=latency_ms,
            verdict=f"http-{status}",
            notes=notes,
            extras=extras,
        )


def _cmd_probe_roundtrip(
    target: str,
    active: bool,
    reply_to: str | None = None,
    ack_window_ms: int = 5000,
) -> None:
    """Probe a diagnostic roundtrip path by declaring ACK intent in the probe object."""
    base = target.rstrip("/")
    if not (base.startswith("http://") or base.startswith("https://")):
        base = f"http://{base}"

    if not reply_to:
        _print_probe_result(
            probe="roundtrip",
            target=base,
            reachable=False,
            verdict="invalid",
            notes=[
                "roundtrip probe requires --reply-to",
                "this probe models a manifest-style diagnostic ping with expected ACK",
            ],
            extras={
                "ack_expected": True,
                "ack_window_ms": ack_window_ms,
            },
        )
        return

    if not active:
        _print_probe_result(
            probe="roundtrip",
            target=base,
            reachable=True,
            verdict="dry-run",
            notes=[
                "roundtrip probe requires --active to write a tiny diagnostic object",
                "current phase declares ACK expectation but does not poll for receipt yet",
            ],
            extras={
                "ack_expected": True,
                "ack_window_ms": ack_window_ms,
                "reply_to": reply_to,
                "phase": "diagnostic handoff declaration only",
            },
        )
        return

    probe_ref = f"tping-roundtrip-{int(time.time())}.probe"
    short_id = "".join(c for c in probe_ref if c.isalnum())[:12] or "unknown"
    ack_surface_hint = f"ack-of-{short_id}"
    payload = (
        "TPING-ROUNDTRIP-PROBE-V1\n"
        "intent=diagnostic.ping\n"
        "require_ack=true\n"
        f"reply_to={reply_to}\n"
        f"max_ack_window_ms={ack_window_ms}\n"
        f"correlation_ref={probe_ref}\n"
        "purpose=active continuityd roundtrip validation\n"
    ).encode("utf-8")
    filename = probe_ref
    url = f"{base}/inbox/{filename}"
    notes = [
        "active-write",
        "manifest-style diagnostic ping",
        f"filename={filename}",
        f"bytes={len(payload)}",
        f"reply_to={reply_to}",
        f"ack_window_ms={ack_window_ms}",
        "measures ingress now; receipt timing will layer above this later",
    ]
    extras = {
        "phase": "ingress accepted, awaiting ack",
        "probe_ref": probe_ref,
        "ack_surface_hint": ack_surface_hint,
        "ack_expected": True,
        "ack_window_ms": ack_window_ms,
        "reply_to": reply_to,
        "ack_command_hint": (
            f'tcd ack "{probe_ref}" --to {reply_to} '
            f'--note "roundtrip ack for {probe_ref}"'
        ),
    }

    req = urllib.request.Request(url, data=payload, method="POST")
    req.add_header("Content-Type", "application/octet-stream")

    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            latency_ms = (time.time() - t0) * 1000
            status = resp.getcode()
            body = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        latency_ms = (time.time() - t0) * 1000
        body = e.read().decode("utf-8", errors="replace")
        _print_probe_result(
            probe="roundtrip",
            target=base,
            reachable=True,
            latency_ms=latency_ms,
            verdict=f"http-{e.code}",
            notes=notes + [str(e), body[:120] if body else "no body"],
            extras=extras,
        )
        return
    except (urllib.error.URLError, OSError) as e:
        _print_probe_result(
            probe="roundtrip",
            target=base,
            reachable=False,
            verdict="unreachable",
            notes=notes + [str(e)],
            extras=extras,
        )
        return

    if status in (200, 201, 202):
        response_hint = " ".join(body.strip().splitlines()[:1])[:120]
        if response_hint:
            notes.append(response_hint)
        _print_probe_result(
            probe="roundtrip",
            target=base,
            reachable=True,
            latency_ms=latency_ms,
            verdict="accepted-awaiting-ack",
            notes=notes,
            extras=extras,
        )
    else:
        _print_probe_result(
            probe="roundtrip",
            target=base,
            reachable=True,
            latency_ms=latency_ms,
            verdict=f"http-{status}",
            notes=notes,
            extras=extras,
        )


def _cmd_probe_sendpath(target: str, base_url: str) -> None:
    """Probe a higher-level delivery path without actually writing an object."""
    if target.endswith(".aint"):
        _cmd_probe_aint(target, base_url)
        return

    if target.startswith("jis:"):
        _cmd_probe_did(target, base_url)
        return

    _print_probe_result(
        probe="sendpath",
        target=target,
        reachable=False,
        verdict="invalid",
        notes=[
            "target must be .aint or jis:...",
            "this probe is for identity-routed path validation",
        ],
    )


def _cmd_probe(args) -> None:
    """Dispatch stack-aware probes."""
    global PROBE_JSON_OUTPUT
    PROBE_JSON_OUTPUT = getattr(args, "json_output", False)

    if args.probe == "ains":
        _cmd_probe_ains(args.target, args.ains_base)
    elif args.probe == "aint":
        _cmd_probe_aint(args.target, args.ains_base)
    elif args.probe == "did":
        _cmd_probe_did(args.target, args.ains_base)
    elif args.probe == "continuityd":
        _cmd_probe_continuityd(args.target)
    elif args.probe == "listener":
        _cmd_probe_listener(args.target)
    elif args.probe == "handoff":
        _cmd_probe_handoff(
            args.target,
            getattr(args, "active", False),
            getattr(args, "reply_to", None),
        )
    elif args.probe == "roundtrip":
        _cmd_probe_roundtrip(
            args.target,
            getattr(args, "active", False),
            getattr(args, "reply_to", None),
            getattr(args, "ack_window_ms", 5000),
        )
    elif args.probe == "inbox":
        _cmd_probe_inbox(args.target)
    elif args.probe == "mux":
        _cmd_probe_mux(args.target)
    elif args.probe == "sendpath":
        _cmd_probe_sendpath(args.target, args.ains_base)
    else:
        print(f"ERROR: unknown probe type: {args.probe}", file=sys.stderr)
        sys.exit(1)


def _cmd_probe_inbox(target: str) -> None:
    """Probe continuityd HTTP inbox path shape more explicitly."""
    base = target.rstrip("/")
    if not (base.startswith("http://") or base.startswith("https://")):
        base = f"http://{base}"

    inbox_url = base + "/inbox/test-probe-placeholder"
    t0 = time.time()
    req = urllib.request.Request(inbox_url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            latency_ms = (time.time() - t0) * 1000
            status = resp.getcode()
            body = resp.read().decode("utf-8", errors="replace")
            _print_probe_result(
                probe="inbox",
                target=base,
                reachable=True,
                latency_ms=latency_ms,
                verdict=f"unexpected-{status}",
                notes=["GET unexpectedly succeeded on inbox path", body[:120] if body else "no body"],
            )
            return
    except urllib.error.HTTPError as e:
        latency_ms = (time.time() - t0) * 1000
        if e.code == 404:
            _print_probe_result(
                probe="inbox",
                target=base,
                reachable=True,
                latency_ms=latency_ms,
                verdict="surface-present",
                notes=[
                    "peer responded to inbox path shape",
                    "GET is not the write method, but endpoint family appears present",
                ],
            )
            return
        _print_probe_result(
            probe="inbox",
            target=base,
            reachable=True,
            latency_ms=latency_ms,
            verdict=f"http-{e.code}",
            notes=[str(e)],
        )
        return
    except (urllib.error.URLError, OSError) as e:
        _print_probe_result(
            probe="inbox",
            target=base,
            reachable=False,
            verdict="unreachable",
            notes=[str(e)],
        )
        return


def _cmd_probe_mux(target: str) -> None:
    """Probe MUX TCP reachability and basic latency."""
    import asyncio

    endpoint = target
    if endpoint.startswith("http://") or endpoint.startswith("https://"):
        endpoint = endpoint.split("://", 1)[1]
        endpoint = endpoint.split("/", 1)[0]

    try:
        host, port = _parse_host_port(endpoint)
    except Exception as e:
        _print_probe_result(
            probe="mux",
            target=target,
            reachable=False,
            verdict="invalid-target",
            notes=[str(e)],
        )
        return

    async def _run() -> tuple[bool, float | None, list[str], str]:
        notes: list[str] = []
        t0 = time.time()
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=5.0,
            )
            latency_ms = (time.time() - t0) * 1000
            notes.append("tcp-connect-ok")
            notes.append("mux reachability baseline established")
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass
            return True, latency_ms, notes, "live"
        except asyncio.TimeoutError:
            return False, None, ["connect-timeout"], "timeout"
        except OSError as e:
            return False, None, [str(e)], "unreachable"

    reachable, latency_ms, notes, verdict = asyncio.run(_run())
    _print_probe_result(
        probe="mux",
        target=target,
        reachable=reachable,
        latency_ms=latency_ms,
        verdict=verdict,
        notes=notes,
    )


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


# ── MUX Diagnostics ─────────────────────────────────────────

def _cmd_mux(args) -> None:
    """ClusterMux diagnostics — RTT, throughput bench, integrity verify."""
    import asyncio
    import json
    import hashlib

    endpoint = args.endpoint
    bench_blocks = getattr(args, 'bench', 0)
    verify = getattr(args, 'verify', False)

    async def _run():
        print(f"tibet-ping mux {endpoint}")
        print(f"{'=' * 56}")

        # ── Step 1: TCP connect + RTT ──
        t0 = time.time()
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(*_parse_host_port(endpoint)),
                timeout=5.0,
            )
        except (ConnectionRefusedError, OSError) as e:
            print(f"  FAIL: Cannot connect to {endpoint}")
            print(f"  Error: {e}")
            print(f"\n  Is the RAM RAID server running?")
            print(f"  Start with: tibet-dgx serve --bind {endpoint}")
            return
        except asyncio.TimeoutError:
            print(f"  FAIL: Connection timeout to {endpoint}")
            print(f"  Check: firewall, port, network route")
            return

        connect_ms = (time.time() - t0) * 1000
        print(f"  TCP connect:    {connect_ms:.1f}ms")

        # MUX echo ping — send small block, measure RTT from response
        # ClusterMux uses length-prefixed binary frames
        # We do 5 sequential TCP connect + first-byte tests for RTT
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass

        rtts = []
        for i in range(5):
            try:
                t1 = time.time()
                r, w = await asyncio.wait_for(
                    asyncio.open_connection(*_parse_host_port(endpoint)),
                    timeout=3.0,
                )
                rtt_us = int((time.time() - t1) * 1_000_000)
                rtts.append(rtt_us)
                w.close()
                try:
                    await w.wait_closed()
                except Exception:
                    pass
            except Exception:
                rtts.append(-1)

        valid_rtts = [r for r in rtts if r >= 0]
        if valid_rtts:
            valid_rtts.sort()
            print(f"  MUX RTT:        min={valid_rtts[0]}µs, median={valid_rtts[len(valid_rtts)//2]}µs, max={valid_rtts[-1]}µs")
            print(f"  Pings:          {len(valid_rtts)}/5 OK")
        else:
            print(f"  MUX RTT:        all 5 connect attempts failed")
            print(f"  Server may be overloaded or dropping connections")

        # ── Step 2: Throughput bench ──
        if bench_blocks > 0:
            print(f"\n  Benchmark: {bench_blocks} × 2MB blocks")
            try:
                reader2, writer2 = await asyncio.wait_for(
                    asyncio.open_connection(*_parse_host_port(endpoint)),
                    timeout=5.0,
                )
                block_size = 2 * 1024 * 1024
                test_data = bytes(range(256)) * (block_size // 256)
                test_hash = hashlib.sha256(test_data).hexdigest()

                # Store
                t2 = time.time()
                for i in range(bench_blocks):
                    store_frame = json.dumps({
                        "type": "Store",
                        "channel_id": i + 1,
                        "block_index": i,
                        "from_aint": "tibet-ping.aint",
                        "content_hash": test_hash,
                        "ed25519_seal": "bench",
                        "raw_size": block_size,
                        "bus_seq": i,
                    }).encode()
                    store_len = len(store_frame).to_bytes(4, 'big')
                    writer2.write(store_len + store_frame)
                    await writer2.drain()

                    # Send payload
                    payload_len = len(test_data).to_bytes(4, 'big')
                    writer2.write(payload_len + test_data)
                    await writer2.drain()

                    # Read response
                    resp_len_bytes = await asyncio.wait_for(reader2.readexactly(4), timeout=10.0)
                    resp_len = int.from_bytes(resp_len_bytes, 'big')
                    await asyncio.wait_for(reader2.readexactly(resp_len), timeout=10.0)

                store_s = time.time() - t2
                store_mbps = (bench_blocks * block_size) / 1_000_000 / max(store_s, 0.001)
                print(f"  Store:          {bench_blocks} blocks in {store_s:.2f}s ({store_mbps:.0f} MB/s)")

                writer2.close()
                try:
                    await writer2.wait_closed()
                except Exception:
                    pass
            except Exception as e:
                print(f"  Bench failed: {e}")
                print(f"  (MUX bench requires tibet-dgx serve or ram-raid-cluster-demo server)")

        # ── Step 3: Integrity verify ──
        if verify:
            print(f"\n  Integrity: store → fetch → SHA-256 verify")
            try:
                reader3, writer3 = await asyncio.wait_for(
                    asyncio.open_connection(*_parse_host_port(endpoint)),
                    timeout=5.0,
                )
                test_block = b"tibet-ping integrity test " + str(time.time()).encode()
                test_block = test_block.ljust(4096, b'\x00')
                expected_hash = hashlib.sha256(test_block).hexdigest()
                print(f"  Block size:     {len(test_block)} bytes")
                print(f"  Expected SHA:   {expected_hash[:32]}...")
                print(f"  Status:         store → fetch → verify pipeline ready")
                print(f"  (Full verify requires MUX protocol — use tibet-dgx bench for now)")

                writer3.close()
                try:
                    await writer3.wait_closed()
                except Exception:
                    pass
            except Exception as e:
                print(f"  Verify failed: {e}")

        # ── Summary ──
        print(f"\n{'=' * 56}")
        status = "REACHABLE" if valid_rtts else "TCP OK, MUX UNKNOWN"
        print(f"  {endpoint}: {status}")
        if valid_rtts:
            avg_ms = sum(valid_rtts) / len(valid_rtts) / 1000
            print(f"  Avg RTT: {avg_ms:.2f}ms")

    asyncio.run(_run())


def _cmd_stack(args) -> None:
    """Full TIBET stack health check — MUX, AINS, I-Poll, local services."""
    import asyncio
    import json

    mux_endpoint = getattr(args, 'mux', None)
    ains_url = getattr(args, 'ains', 'http://localhost:8000/api/ains')
    ipoll_url = getattr(args, 'ipoll', 'http://localhost:8000/api/ipoll')

    print("tibet-ping stack — TIBET Health Check")
    print("=" * 56)
    results = {}

    # ── AINS ──
    print("\n  [AINS] AInternet Name Service")
    try:
        import urllib.request
        t0 = time.time()
        resp = urllib.request.urlopen(f"{ains_url}/list", timeout=5)
        data = json.loads(resp.read())
        ms = (time.time() - t0) * 1000
        domains = len(data) if isinstance(data, list) else len(data.get('domains', data.get('agents', [])))
        print(f"    Status:   OK ({ms:.0f}ms)")
        print(f"    Domains:  {domains} registered")
        results['ains'] = 'OK'
    except Exception as e:
        print(f"    Status:   FAIL ({e})")
        results['ains'] = 'FAIL'

    # ── I-Poll ──
    print("\n  [I-Poll] AI Messaging")
    try:
        t0 = time.time()
        resp = urllib.request.urlopen(f"{ipoll_url}/status", timeout=5)
        data = json.loads(resp.read())
        ms = (time.time() - t0) * 1000
        print(f"    Status:   OK ({ms:.0f}ms)")
        if isinstance(data, dict):
            for k in ['total_messages', 'agents', 'uptime']:
                if k in data:
                    print(f"    {k}: {data[k]}")
        results['ipoll'] = 'OK'
    except Exception as e:
        print(f"    Status:   FAIL ({e})")
        results['ipoll'] = 'FAIL'

    # ── Brain API ──
    print("\n  [Brain API] Central Nervous System")
    try:
        t0 = time.time()
        resp = urllib.request.urlopen("http://localhost:8000/", timeout=5)
        ms = (time.time() - t0) * 1000
        code = resp.getcode()
        print(f"    Status:   OK ({ms:.0f}ms, HTTP {code})")
        results['brain'] = 'OK'
    except Exception as e:
        print(f"    Status:   FAIL ({e})")
        results['brain'] = 'FAIL'

    # ── MUX (optional) ──
    if mux_endpoint:
        print(f"\n  [MUX] ClusterMux Transport ({mux_endpoint})")
        try:
            async def _mux_check():
                t0 = time.time()
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(*_parse_host_port(mux_endpoint)),
                    timeout=5.0,
                )
                ms = (time.time() - t0) * 1000
                writer.close()
                try:
                    await writer.wait_closed()
                except Exception:
                    pass
                return ms

            ms = asyncio.run(_mux_check())
            print(f"    Status:   OK ({ms:.1f}ms connect)")
            results['mux'] = 'OK'
        except Exception as e:
            print(f"    Status:   FAIL ({e})")
            results['mux'] = 'FAIL'

    # ── Ollama (P520) ──
    print("\n  [Ollama] LLM Backend")
    for name, host in [("localhost", "localhost:11434"), ("P520", "192.168.4.85:11434")]:
        try:
            t0 = time.time()
            resp = urllib.request.urlopen(f"http://{host}/api/tags", timeout=3)
            data = json.loads(resp.read())
            ms = (time.time() - t0) * 1000
            models = len(data.get('models', []))
            print(f"    {name:12s} OK ({ms:.0f}ms, {models} models)")
            results[f'ollama_{name}'] = 'OK'
        except Exception:
            print(f"    {name:12s} UNREACHABLE")
            results[f'ollama_{name}'] = 'FAIL'

    # ── Summary ──
    ok = sum(1 for v in results.values() if v == 'OK')
    total = len(results)
    print(f"\n{'=' * 56}")
    print(f"  {ok}/{total} services healthy")

    if ok == total:
        print("  All systems nominal. T-T-T-TIBET and the checks!")
    else:
        failed = [k for k, v in results.items() if v == 'FAIL']
        print(f"  Down: {', '.join(failed)}")


def _parse_host_port(endpoint: str) -> tuple:
    """Parse host:port string."""
    parts = endpoint.rsplit(":", 1)
    return (parts[0], int(parts[1]))


# ── Main entry point ─────────────────────────────────────────

def _usage() -> None:
    print(f"tibet-ping v{__version__}")
    print()
    print("Protocol commands:")
    print("  tibet-ping <jis:did>             Ping a JIS device (proto only)")
    print("  tibet-ping <ip-address>          Legacy ping (easter egg)")
    print("  tibet-ping <name>.aint           Probe an AInternet-style destination")
    print("  tibet-ping --probe aint <name>   Probe .aint resolution")
    print("  tibet-ping --probe did <target>  Probe JIS-style identity target")
    print("  tibet-ping --probe ains <name>   Probe AINS resolution")
    print("  tibet-ping --probe continuityd <url>  Probe continuityd HTTP surface")
    print("  tibet-ping --probe listener <url>     Probe continuityd listener surface")
    print("  tibet-ping --probe handoff <url>      Probe active continuityd ingress")
    print("  tibet-ping --probe roundtrip <url>    Probe manifest-style diagnostic roundtrip")
    print("  tibet-ping --probe inbox <url>   Probe continuityd inbox surface")
    print("  tibet-ping --probe mux <host:port>  Probe mux TCP surface")
    print("  tibet-ping --probe sendpath <target>  Probe .aint/JIS delivery path")
    print("    --json                         Emit probe output as JSON")
    print("    --active                       Allow tiny write where probe supports it")
    print("    --reply-to TARGET              Optional return target for later ACK path")
    print("    --ack-window-ms N              Expected ACK window for roundtrip probes")
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
    print("MUX diagnostics:")
    print("  tibet-ping mux <host:port>              ClusterMux RTT + connection test")
    print("    --bench N                              Throughput benchmark (N × 2MB blocks)")
    print("    --verify                               SHA-256 integrity roundtrip")
    print()
    print("Stack health:")
    print("  tibet-ping stack                         Full TIBET stack health check")
    print("    --mux <host:port>                      Include ClusterMux in check")
    print()
    print("Examples:")
    print('  tibet-ping jis:home:hub')
    print('  tibet-ping 88.33.294.66')
    print('  tibet-ping jasper.aint')
    print('  tibet-ping --probe aint jasper.aint --json')
    print('  tibet-ping --probe did jis:humotica:continuityd@192.168.4.76')
    print('  tibet-ping --probe ains root_idd')
    print('  tibet-ping --probe continuityd http://192.168.4.76:8443')
    print('  tibet-ping --probe listener http://192.168.4.76:8443')
    print('  tibet-ping --probe handoff http://192.168.4.76:8443 --active')
    print('  tibet-ping --probe handoff http://192.168.4.76:8443 --active --reply-to jasper.aint')
    print('  tibet-ping --probe roundtrip http://192.168.4.76:8443 --active --reply-to jasper.aint')
    print('  tibet-ping --probe inbox http://192.168.4.76:8443')
    print('  tibet-ping --probe mux 10.0.100.1:4432')
    print('  tibet-ping --probe sendpath jasper.aint')
    print('  tibet-ping listen --did jis:my:hub')
    print('  tibet-ping send jis:hub 192.168.1.10:7150 temperature.report')
    print('  tibet-ping discover --timeout 10')
    print('  tibet-ping mux 10.0.100.1:4432')
    print('  tibet-ping mux 10.0.100.1:4432 --bench 50')
    print('  tibet-ping stack --mux 10.0.100.1:4432')


def main() -> None:
    """CLI entry point."""
    import argparse

    # If no args or simple usage, use the lightweight path
    args = sys.argv[1:]

    if not args or args[0] in ("--help", "-h"):
        _usage()
        return

    # Probe mode shortcut: `tibet-ping --probe continuityd http://...`
    if args[0] == "--probe":
        import argparse
        probe_parser = argparse.ArgumentParser(prog="tibet-ping")
        probe_parser.add_argument("--probe", choices=("did", "aint", "ains", "continuityd", "listener", "handoff", "roundtrip", "inbox", "mux", "sendpath"), required=True)
        probe_parser.add_argument("target")
        probe_parser.add_argument(
            "--json",
            dest="json_output",
            action="store_true",
            help="Emit probe result as JSON",
        )
        probe_parser.add_argument(
            "--active",
            action="store_true",
            help="Allow a probe to write a tiny test object where applicable",
        )
        probe_parser.add_argument(
            "--reply-to",
            default=None,
            help="Optional return target to align a later ACK/receipt path",
        )
        probe_parser.add_argument(
            "--ack-window-ms",
            type=int,
            default=5000,
            help="Expected ACK window in milliseconds for roundtrip probes",
        )
        probe_parser.add_argument(
            "--ains-base",
            default="http://localhost:8000/api/ains",
            help="AINS base URL (default: http://localhost:8000/api/ains)",
        )
        parsed_probe = probe_parser.parse_args(args)
        _cmd_probe(parsed_probe)
        return

    command = args[0]

    # Simple commands (no argparse needed)
    if command == "demo":
        _cmd_demo()
        return
    elif _is_ip_address(command):
        _easter_egg_legacy_ping(command)
        return
    elif command.endswith(".aint"):
        parsed_probe = argparse.Namespace(
            probe="aint",
            target=command,
            ains_base="http://localhost:8000/api/ains",
            json_output=False,
        )
        _cmd_probe(parsed_probe)
        return
    elif command not in ("listen", "send", "discover", "net-demo", "mux", "stack"):
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

    # mux
    p_mux = sub.add_parser("mux")
    p_mux.add_argument("endpoint", help="ClusterMux endpoint (host:port)")
    p_mux.add_argument("--bench", type=int, default=0, help="Throughput benchmark (N blocks)")
    p_mux.add_argument("--verify", action="store_true", help="SHA-256 integrity check")

    # stack
    p_stack = sub.add_parser("stack")
    p_stack.add_argument("--mux", default=None, help="ClusterMux endpoint to include")
    p_stack.add_argument("--ains", default="http://localhost:8000/api/ains", help="AINS base URL")
    p_stack.add_argument("--ipoll", default="http://localhost:8000/api/ipoll", help="I-Poll base URL")

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
    elif parsed.command == "mux":
        _cmd_mux(parsed)
    elif parsed.command == "stack":
        _cmd_stack(parsed)


if __name__ == "__main__":
    main()
