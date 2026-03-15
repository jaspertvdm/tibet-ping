"""Tests for PacketCodec — wire format roundtrip."""

from __future__ import annotations

import struct

import pytest
from tibet_ping import PingPacket, PingResponse, PingType, PingDecision

from tibet_ping.transport.codec import (
    PacketCodec,
    FrameFlags,
    MAGIC,
    VERSION,
    HEADER_SIZE,
    HEADER_FMT,
)


@pytest.fixture
def codec() -> PacketCodec:
    return PacketCodec()


@pytest.fixture
def sample_packet() -> PingPacket:
    from tibet_ping import PingNode

    node = PingNode("jis:test:sender")
    return node.ping(
        target="jis:test:receiver",
        intent="temperature.read",
        purpose="Unit test",
    )


@pytest.fixture
def sample_response(sample_packet: PingPacket) -> PingResponse:
    from tibet_ping import PingNode

    hub = PingNode("jis:test:receiver")
    hub.set_trust("jis:test:sender", 0.9)
    return hub.receive(sample_packet)


class TestEncodeDecodePacket:
    def test_roundtrip(self, codec: PacketCodec, sample_packet: PingPacket) -> None:
        data = codec.encode_packet(sample_packet)
        decoded = codec.decode(data)
        assert isinstance(decoded, PingPacket)
        assert decoded.packet_id == sample_packet.packet_id
        assert decoded.source_did == sample_packet.source_did
        assert decoded.target_did == sample_packet.target_did
        assert decoded.intent == sample_packet.intent

    def test_header_magic(self, codec: PacketCodec, sample_packet: PingPacket) -> None:
        data = codec.encode_packet(sample_packet)
        assert data[:2] == MAGIC

    def test_header_version(self, codec: PacketCodec, sample_packet: PingPacket) -> None:
        data = codec.encode_packet(sample_packet)
        assert data[2] == VERSION

    def test_header_flags_packet(
        self, codec: PacketCodec, sample_packet: PingPacket
    ) -> None:
        data = codec.encode_packet(sample_packet)
        flags = data[3]
        assert not (flags & FrameFlags.IS_RESPONSE)
        assert not (flags & FrameFlags.MSGPACK)

    def test_header_length(self, codec: PacketCodec, sample_packet: PingPacket) -> None:
        data = codec.encode_packet(sample_packet)
        _, _, _, payload_len = struct.unpack(HEADER_FMT, data[:HEADER_SIZE])
        assert payload_len == len(data) - HEADER_SIZE


class TestEncodeDecodeResponse:
    def test_roundtrip(
        self, codec: PacketCodec, sample_response: PingResponse
    ) -> None:
        data = codec.encode_response(sample_response)
        decoded = codec.decode(data)
        assert isinstance(decoded, PingResponse)
        assert decoded.response_id == sample_response.response_id
        assert decoded.in_response_to == sample_response.in_response_to
        assert decoded.decision == sample_response.decision

    def test_header_flags_response(
        self, codec: PacketCodec, sample_response: PingResponse
    ) -> None:
        data = codec.encode_response(sample_response)
        flags = data[3]
        assert flags & FrameFlags.IS_RESPONSE


class TestMalformedData:
    def test_truncated_header(self, codec: PacketCodec) -> None:
        with pytest.raises(ValueError, match="Truncated header"):
            codec.decode(b"\x54\x50\x01")

    def test_bad_magic(self, codec: PacketCodec) -> None:
        data = b"\xff\xff\x01\x00\x00\x00\x00\x04test"
        with pytest.raises(ValueError, match="Bad magic"):
            codec.decode(data)

    def test_bad_version(self, codec: PacketCodec) -> None:
        data = struct.pack(HEADER_FMT, MAGIC, 0x99, 0, 4) + b"test"
        with pytest.raises(ValueError, match="Unsupported version"):
            codec.decode(data)

    def test_truncated_payload(self, codec: PacketCodec) -> None:
        data = struct.pack(HEADER_FMT, MAGIC, VERSION, 0, 100) + b"test"
        with pytest.raises(ValueError, match="Truncated payload"):
            codec.decode(data)


class TestMsgpack:
    def test_msgpack_roundtrip(self, sample_packet: PingPacket) -> None:
        pytest.importorskip("msgpack")
        mp_codec = PacketCodec(use_msgpack=True)

        data = mp_codec.encode_packet(sample_packet)
        flags = data[3]
        assert flags & FrameFlags.MSGPACK

        decoded = mp_codec.decode(data)
        assert isinstance(decoded, PingPacket)
        assert decoded.packet_id == sample_packet.packet_id

    def test_msgpack_smaller(self, sample_packet: PingPacket) -> None:
        pytest.importorskip("msgpack")
        json_codec = PacketCodec(use_msgpack=False)
        mp_codec = PacketCodec(use_msgpack=True)

        json_data = json_codec.encode_packet(sample_packet)
        mp_data = mp_codec.encode_packet(sample_packet)
        assert len(mp_data) < len(json_data)
