"""PacketCodec — wire framing for TIBET transport.

Wire format:
    Offset  Size  Field
    0       2     Magic bytes: 0x54 0x50 ("TP")
    2       1     Version: 0x01
    3       1     Flags: bit 0 = is_response, bit 1 = msgpack
    4       4     Payload length (uint32, big-endian)
    8       N     Payload (JSON or msgpack)

8 bytes header overhead. JSON default (debugbaar), msgpack optioneel (40% kleiner).
"""

from __future__ import annotations

import enum
import json
import struct
from typing import Union

from tibet_ping import PingPacket, PingResponse

MAGIC = b"\x54\x50"  # "TP"
VERSION = 0x01
HEADER_SIZE = 8
HEADER_FMT = ">2sBBI"  # magic(2) + version(1) + flags(1) + length(4)
MAX_PAYLOAD = 64 * 1024  # 64 KB


class FrameFlags(enum.IntFlag):
    """Wire frame flag bits."""

    NONE = 0
    IS_RESPONSE = 1 << 0
    MSGPACK = 1 << 1


class PacketCodec:
    """Encode/decode PingPackets and PingResponses to/from wire bytes."""

    def __init__(self, use_msgpack: bool = False) -> None:
        self._use_msgpack = use_msgpack
        if use_msgpack:
            try:
                import msgpack as _mp  # noqa: F401

                self._msgpack = _mp
            except ImportError:
                raise ImportError(
                    "msgpack is required for binary encoding. "
                    "Install with: pip install tibet-ping[msgpack]"
                )
        else:
            self._msgpack = None

    @property
    def use_msgpack(self) -> bool:
        return self._use_msgpack

    def encode_packet(self, packet: PingPacket) -> bytes:
        """Encode a PingPacket to wire bytes."""
        flags = FrameFlags.NONE
        if self._use_msgpack:
            flags |= FrameFlags.MSGPACK
        return self._encode(packet.to_dict(), flags)

    def encode_response(self, response: PingResponse) -> bytes:
        """Encode a PingResponse to wire bytes."""
        flags = FrameFlags.IS_RESPONSE
        if self._use_msgpack:
            flags |= FrameFlags.MSGPACK
        return self._encode(response.to_dict(), flags)

    def decode(self, data: bytes) -> Union[PingPacket, PingResponse]:
        """Decode wire bytes to a PingPacket or PingResponse.

        Raises ValueError on malformed data.
        """
        if len(data) < HEADER_SIZE:
            raise ValueError(
                f"Truncated header: got {len(data)} bytes, need {HEADER_SIZE}"
            )

        magic, version, flags_raw, payload_len = struct.unpack(
            HEADER_FMT, data[:HEADER_SIZE]
        )

        if magic != MAGIC:
            raise ValueError(f"Bad magic: {magic!r}, expected {MAGIC!r}")
        if version != VERSION:
            raise ValueError(f"Unsupported version: {version}, expected {VERSION}")

        flags = FrameFlags(flags_raw)

        expected = HEADER_SIZE + payload_len
        if len(data) < expected:
            raise ValueError(
                f"Truncated payload: got {len(data)} bytes, expected {expected}"
            )

        payload_bytes = data[HEADER_SIZE : HEADER_SIZE + payload_len]
        obj = self._deserialize(payload_bytes, flags)

        if flags & FrameFlags.IS_RESPONSE:
            return PingResponse.from_dict(obj)
        return PingPacket.from_dict(obj)

    def _encode(self, obj: dict, flags: FrameFlags) -> bytes:
        payload = self._serialize(obj, flags)
        if len(payload) > MAX_PAYLOAD:
            raise ValueError(
                f"Payload too large: {len(payload)} bytes, max {MAX_PAYLOAD}"
            )
        header = struct.pack(HEADER_FMT, MAGIC, VERSION, int(flags), len(payload))
        return header + payload

    def _serialize(self, obj: dict, flags: FrameFlags) -> bytes:
        if flags & FrameFlags.MSGPACK:
            return self._msgpack.packb(obj, use_bin_type=True)
        return json.dumps(obj, separators=(",", ":")).encode("utf-8")

    def _deserialize(self, data: bytes, flags: FrameFlags) -> dict:
        if flags & FrameFlags.MSGPACK:
            if self._msgpack is None:
                try:
                    import msgpack

                    self._msgpack = msgpack
                except ImportError:
                    raise ImportError(
                        "msgpack is required to decode this packet. "
                        "Install with: pip install tibet-ping[msgpack]"
                    )
            return self._msgpack.unpackb(data, raw=False)
        return json.loads(data.decode("utf-8"))
