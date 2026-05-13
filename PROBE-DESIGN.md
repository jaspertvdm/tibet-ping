# tping+ probe design

## Proposed probe names

- `icmp`
- `did`
- `ains`
- `continuityd`
- `inbox`
- `mux`

## Semantics

### `icmp`

Classic network reachability baseline.

### `did`

Intent-aware identity ping using JIS/TIBET primitives where possible.

### `ains`

Check whether a name resolves and whether trust/capability metadata is
available.

### `continuityd`

Check whether a continuityd peer is present and responding on its known
HTTP or liveness surface.

### `inbox`

Check whether the HTTP inbox path is writable/accepted, ideally with a
dry or tiny signed test object in later versions.

### `mux`

Check whether a mux endpoint responds, and later possibly whether a
basic channel open/close path works.

## CLI direction

Examples:

```bash
tping 192.168.4.85
tping --probe ains root_idd
tping --probe continuityd http://192.168.4.76:8443
tping --probe inbox http://192.168.4.76:8443
tping --probe did jis:humotica:continuityd@192.168.4.76
```

## Output direction

Human mode:

```text
probe: continuityd
target: http://192.168.4.76:8443
reachable: yes
latency: 14.2 ms
verdict: live
notes: HTTP inbox present
```

Machine mode:

```json
{
  "probe": "continuityd",
  "target": "http://192.168.4.76:8443",
  "reachable": true,
  "latency_ms": 14.2,
  "verdict": "live",
  "notes": ["http-inbox-present"]
}
```
