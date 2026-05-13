# tping+ sketch

This is a sandbox copy of `tibet-ping` for exploring a broader
probe-oriented CLI without touching the original package.

## Why

Right now there are two truths at once:

- `tping <ip>` has excellent old-school operator feel
- the real `tibet-ping` package already contains far richer primitives
  than that CLI surface suggests

That makes it a good candidate for a `tping+` evolution:

- keep the raw vibe
- add stack-aware probes
- preserve one muscle-memory across layers

## Core idea

One command family, multiple probes:

```bash
tping 192.168.4.85
tping --probe did jis:humotica:continuityd@192.168.4.76
tping --probe ains root_idd
tping --probe continuityd http://192.168.4.76:8443
tping --probe inbox http://192.168.4.76:8443
tping --probe mux http://192.168.4.76:8001
```

## Design split

### Raw mode

Keep:

- simple operator feel
- immediate reachability check
- funny warnings / Lionel vibe if desired

### Probe mode

Add:

- stack-layer-specific diagnostics
- identity and intent-aware checks
- optional structured output

## Good first probes

- `icmp`
  - old-school network baseline
- `did`
  - resolve / inspect identity-style target
- `ains`
  - check AINS resolution and trust metadata
- `continuityd`
  - liveness / HTTP inbox availability / version surface
- `inbox`
  - can the inbox endpoint accept a tiny test object?
- `mux`
  - can the mux endpoint or websocket ingress answer?

## Uniform result shape

Every probe should ideally report:

- `probe`
- `target`
- `reachable`
- `latency_ms`
- `identity`
- `verdict`
- `notes`

That keeps the operator surface consistent even though the transports
and semantics differ.

## Relationship to the stack

This is useful because the stack already has many "ping-like" checks,
but they are fragmented:

- network ping
- AINS resolve
- continuityd HTTP liveness
- HTTP inbox POST
- mux status
- DID-level intent ping

`tping+` would not invent all of those from scratch.

It would give them one CLI family.

## Next likely step

Add a small design note and then patch the CLI in this sandbox copy to
support:

- `--probe`
- raw fallback mode
- at least one or two real stack probes first
