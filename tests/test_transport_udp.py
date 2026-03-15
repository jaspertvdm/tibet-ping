"""Tests for Transport — MockTransport lifecycle and communication."""

from __future__ import annotations

import asyncio

import pytest
from tibet_ping import PingNode, PingPacket, PingResponse

from conftest_transport import MockTransport


@pytest.fixture
def linked_pair():
    return MockTransport.create_linked_pair()


@pytest.fixture
def sample_packet() -> PingPacket:
    node = PingNode("jis:test:sender")
    return node.ping(
        target="jis:test:receiver",
        intent="test.ping",
        purpose="Transport test",
    )


class TestMockTransportLifecycle:
    @pytest.mark.asyncio
    async def test_start_stop(self) -> None:
        transport = MockTransport()
        assert not transport.running
        await transport.start()
        assert transport.running
        await transport.stop()
        assert not transport.running

    @pytest.mark.asyncio
    async def test_double_start(self) -> None:
        transport = MockTransport()
        await transport.start()
        await transport.start()
        assert transport.running
        await transport.stop()


class TestLinkedPairCommunication:
    @pytest.mark.asyncio
    async def test_send_receive(self, linked_pair, sample_packet) -> None:
        a, b = linked_pair
        received = []

        async def on_recv(decoded, addr):
            received.append((decoded, addr))

        b.on_receive(on_recv)
        await a.start()
        await b.start()

        await a.send_packet(sample_packet, b.own_addr)

        assert len(received) == 1
        decoded, addr = received[0]
        assert isinstance(decoded, PingPacket)
        assert decoded.packet_id == sample_packet.packet_id
        assert addr == a.own_addr

        await a.stop()
        await b.stop()

    @pytest.mark.asyncio
    async def test_send_response(self, linked_pair, sample_packet) -> None:
        a, b = linked_pair
        received = []

        async def on_recv(decoded, addr):
            received.append(decoded)

        a.on_receive(on_recv)
        await a.start()
        await b.start()

        hub = PingNode("jis:test:receiver")
        hub.set_trust("jis:test:sender", 0.9)
        response = hub.receive(sample_packet)

        await b.send_response(response, a.own_addr)

        assert len(received) == 1
        assert isinstance(received[0], PingResponse)
        assert received[0].in_response_to == sample_packet.packet_id

        await a.stop()
        await b.stop()

    @pytest.mark.asyncio
    async def test_broadcast(self, linked_pair, sample_packet) -> None:
        a, b = linked_pair
        received = []

        async def on_recv(decoded, addr):
            received.append(decoded)

        b.on_receive(on_recv)
        await a.start()
        await b.start()

        await a.broadcast(sample_packet)

        assert len(received) == 1
        assert isinstance(received[0], PingPacket)
        assert received[0].packet_id == sample_packet.packet_id

        await a.stop()
        await b.stop()

    @pytest.mark.asyncio
    async def test_no_delivery_when_stopped(
        self, linked_pair, sample_packet
    ) -> None:
        a, b = linked_pair
        received = []

        async def on_recv(decoded, addr):
            received.append(decoded)

        b.on_receive(on_recv)
        await a.start()

        await a.send_packet(sample_packet, b.own_addr)
        assert len(received) == 0

        await a.stop()


class TestCallbackInvocation:
    @pytest.mark.asyncio
    async def test_multiple_callbacks(self, linked_pair, sample_packet) -> None:
        a, b = linked_pair
        cb1_calls = []
        cb2_calls = []

        async def cb1(decoded, addr):
            cb1_calls.append(decoded)

        async def cb2(decoded, addr):
            cb2_calls.append(decoded)

        b.on_receive(cb1)
        b.on_receive(cb2)
        await a.start()
        await b.start()

        await a.send_packet(sample_packet, b.own_addr)

        assert len(cb1_calls) == 1
        assert len(cb2_calls) == 1

        await a.stop()
        await b.stop()
