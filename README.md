# tibet-ping

**Intent-aware ping, identity probe, and stack diagnostics for TIBET-native systems.**

This sandbox copy is not trying to replace `tping`.

It is trying to make a clearer choice available:

- use raw `tping` when you want the old-school network reflex
- choose `tping+` when you want to inspect a deeper stack layer

That distinction matters because the current package already contains
more than the familiar CLI surface suggests.

## The choice

There are really two operator moments here.

### 1. Raw `tping`

Use this when the question is simple:

> Is anything there at all?

Examples:

```bash
tping 192.168.4.85
tping 127.0.0.1
```

What should stay true in raw mode:

- fast operator feel
- minimal syntax
- immediate reachability instinct
- Lionel-vibe warnings still welcome

This is the right mode when you just want the gut check.

### 2. Chosen `tping+`

Use this when the question gets more specific:

> Which layer is there, and what exactly is alive?

Examples:

```bash
tping jasper.aint
tping dl360.jasper.aint
tping --probe aint jasper.aint
tping --probe did jis:humotica:continuityd@192.168.4.76
tping --probe ains root_idd
tping --probe continuityd http://192.168.4.76:8443
tping --probe listener http://192.168.4.76:8443
tping --probe handoff http://192.168.4.76:8443 --active
tping --probe handoff http://192.168.4.76:8443 --active --reply-to jasper.aint
tping --probe roundtrip http://192.168.4.76:8443 --active --reply-to jasper.aint
tping --probe inbox http://192.168.4.76:8443
tping --probe mux 10.0.100.1:4432
tping --probe sendpath jasper.aint
```

This is why the `tping+` framing is useful.

It is not a different binary.

It is the moment where the operator deliberately asks for a deeper,
stack-aware answer.

## Why this fits the real package

The package is already richer than the casual CLI suggests. It already
touches themes like:

- JIS-aware identity
- intent and purpose
- nonce/replay protection
- UDP transport
- LAN discovery
- mesh relay
- mux and stack diagnostics

So the real opportunity is not to bolt on a random extra command.

The opportunity is to make the existing family easier to use at
different depths.

## Probe family

The sandbox probe family currently includes:

- `aint`
  - inspect and resolve an AInternet-style destination such as
    `jasper.aint`
- `did`
  - parse and inspect a JIS-style target
- `ains`
  - ask whether a name resolves and whether metadata exists
- `continuityd`
  - check whether the daemon HTTP surface responds
- `listener`
  - quickly validate that a continuityd listener appears open and
    plausible on a host, laptop, or Termux node
- `handoff`
  - actively push a tiny probe object through the HTTP inbox path when
    you explicitly allow it with `--active`
  - can already emit an ACK/receipt hint surface when you provide
    `--reply-to`
- `roundtrip`
  - declare a manifest-style diagnostic ping with `require_ack` and
    `reply_to`, then push it through the real ingress path
- `inbox`
  - check whether the inbox endpoint family looks real and reachable
- `mux`
  - check whether a mux TCP surface is reachable
- `sendpath`
  - validate an identity-routed path shape without writing a test object

This is intentionally modest.

The first goal is coherence:

- one CLI family
- one muscle-memory
- several legitimate layers to inspect

## What this means operationally

The TIBET stack already has many ping-shaped questions:

- is the host reachable?
- is the DID target sensible?
- does AINS know this name?
- is continuityd alive?
- is the inbox surface there?
- is mux listening?

To an operator these are different layers of the same moment:

> Before I continue, is this thing really there in the way I think it is?

That is why it makes sense to keep them in one command family instead of
spreading them across unrelated tools.

## Current sandbox behavior

This sketch already supports the following probe forms:

```bash
PYTHONPATH=/srv/jtel-stack/sandbox/ai/codex/tibet-ping-plus-sketch/src \
python3 -m tibet_ping.cli jasper.aint
```

```bash
PYTHONPATH=/srv/jtel-stack/sandbox/ai/codex/tibet-ping-plus-sketch/src \
python3 -m tibet_ping.cli --probe aint jasper.aint
```

```bash
PYTHONPATH=/srv/jtel-stack/sandbox/ai/codex/tibet-ping-plus-sketch/src \
python3 -m tibet_ping.cli --probe aint jasper.aint --json
```

```bash
PYTHONPATH=/srv/jtel-stack/sandbox/ai/codex/tibet-ping-plus-sketch/src \
python3 -m tibet_ping.cli --probe did jis:humotica:continuityd@192.168.4.76
```

```bash
PYTHONPATH=/srv/jtel-stack/sandbox/ai/codex/tibet-ping-plus-sketch/src \
python3 -m tibet_ping.cli --probe ains root_idd
```

```bash
PYTHONPATH=/srv/jtel-stack/sandbox/ai/codex/tibet-ping-plus-sketch/src \
python3 -m tibet_ping.cli --probe continuityd http://192.168.4.76:8443
```

```bash
PYTHONPATH=/srv/jtel-stack/sandbox/ai/codex/tibet-ping-plus-sketch/src \
python3 -m tibet_ping.cli --probe listener http://192.168.4.76:8443
```

```bash
PYTHONPATH=/srv/jtel-stack/sandbox/ai/codex/tibet-ping-plus-sketch/src \
python3 -m tibet_ping.cli --probe handoff http://192.168.4.76:8443 --active
```

```bash
PYTHONPATH=/srv/jtel-stack/sandbox/ai/codex/tibet-ping-plus-sketch/src \
python3 -m tibet_ping.cli --probe handoff \
  http://192.168.4.76:8443 \
  --active \
  --reply-to jasper.aint \
  --json
```

```bash
PYTHONPATH=/srv/jtel-stack/sandbox/ai/codex/tibet-ping-plus-sketch/src \
python3 -m tibet_ping.cli --probe roundtrip \
  http://192.168.4.76:8443 \
  --active \
  --reply-to jasper.aint \
  --ack-window-ms 5000 \
  --json
```

```bash
PYTHONPATH=/srv/jtel-stack/sandbox/ai/codex/tibet-ping-plus-sketch/src \
python3 -m tibet_ping.cli --probe inbox http://192.168.4.76:8443
```

```bash
PYTHONPATH=/srv/jtel-stack/sandbox/ai/codex/tibet-ping-plus-sketch/src \
python3 -m tibet_ping.cli --probe mux 10.0.100.1:4432
```

```bash
PYTHONPATH=/srv/jtel-stack/sandbox/ai/codex/tibet-ping-plus-sketch/src \
python3 -m tibet_ping.cli --probe sendpath jasper.aint
```

The probe output currently tries to stay uniform:

- `probe`
- `target`
- `reachable`
- `latency`
- `identity` where relevant
- `verdict`
- `notes`

That matters because the semantics differ, but the operator should not
need a new reading habit for every layer.

For scripting, probe mode can also emit JSON:

```bash
tping --probe aint jasper.aint --json
tping --probe continuityd http://192.168.4.76:8443 --json
tping --probe listener http://192.168.4.76:8443 --json
tping --probe handoff http://192.168.4.76:8443 --active --json
tping --probe handoff http://192.168.4.76:8443 --active --reply-to jasper.aint --json
tping --probe roundtrip http://192.168.4.76:8443 --active --reply-to jasper.aint --json
```

## Listener philosophy

For `continuityd`, a quick listener check is useful.

That is especially true on small edge hosts such as:

- laptops
- Termux / Android
- lightweight MIPS or ARM boxes

But the default probe should stay conservative.

So the current `listener` direction is:

- passive
- non-mutating
- useful for "is my listener there and plausibly configured?"

Later, a separate explicit write-path probe can exist for cases where you
really want to push a tiny signed object through the path.

That next step is now modeled as `handoff`:

- passive by default only in the sense that it refuses to write unless
  you add `--active`
- explicit when you want a tiny object to cross the real ingress path
- useful for proving that a phone, laptop, or small edge host is not
  merely listening, but actually admitting arrival

It still does not measure full causal completion.

For that, the natural next layer is:

- tiny handoff
- then receipt or ACK back
- then causal timing over the roundtrip

`handoff` now already leaves space for that next step by exposing:

- a probe reference
- an `ack-of-<shortid>` surface hint
- an optional `--reply-to` target

So the later receipt loop can align with `tcd ack` instead of inventing
an unrelated shape.

`roundtrip` is the next layer above that:

- it writes a tiny diagnostic object
- it declares `require_ack=true`
- it includes `reply_to`
- it carries an expected ACK window

Today it stops at:

- ingress acceptance
- correlation reference
- ACK expectation declaration

Later it can grow into:

- actual receipt observation
- separate ingress and receipt latency
- a real causal roundtrip measurement

## Design principle

The best version of this tool probably does not replace the raw mode.

It should let someone move naturally between:

- `just ping it`
- and:
- `probe the layer I actually care about`

That preserves the friendly operator surface while allowing the tool to
grow with the continuity-native stack.

## Short framing

Raw `tping` asks:

> Is anything there?

Chosen `tping+` asks:

> Which layer is there, and in what state?

That is the right evolution.
