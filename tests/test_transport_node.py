"""End-to-end tests for IoTNode — node A <-> node B over MockTransport."""

from __future__ import annotations

import asyncio

import pytest
import pytest_asyncio
from tibet_ping import PingDecision, RoutingMode

from tibet_ping.transport.iot_node import IoTNode
from conftest_transport import MockTransport


@pytest.fixture
def linked_transports():
    return MockTransport.create_linked_pair()


@pytest_asyncio.fixture
async def hub_node(linked_transports):
    a, _ = linked_transports
    node = IoTNode(
        "jis:test:hub",
        transport=a,
        heartbeat_interval=300,
        discovery_interval=300,
    )
    node._transport.on_receive(node._handle_incoming)
    await node._transport.start()
    node._running = True
    yield node
    node._running = False
    await node._transport.stop()


@pytest_asyncio.fixture
async def sensor_node(linked_transports):
    _, b = linked_transports
    node = IoTNode(
        "jis:test:sensor",
        transport=b,
        heartbeat_interval=300,
        discovery_interval=300,
    )
    node._transport.on_receive(node._handle_incoming)
    await node._transport.start()
    node._running = True
    yield node
    node._running = False
    await node._transport.stop()


class TestEndToEnd:
    @pytest.mark.asyncio
    async def test_trusted_ping_groen(self, hub_node, sensor_node, linked_transports) -> None:
        a, b = linked_transports
        hub_node.set_trust("jis:test:sensor", 0.9)

        response = await sensor_node.send_ping(
            target="jis:test:hub",
            addr=a.own_addr,
            intent="temperature.report",
            purpose="E2E test",
            payload={"celsius": 21.5},
            timeout=2.0,
        )

        assert response is not None
        assert response.decision == PingDecision.ACCEPT
        assert response.airlock_zone == "GROEN"
        assert response.trust_score == pytest.approx(0.9)

    @pytest.mark.asyncio
    async def test_unknown_ping_rood_silent_drop(
        self, hub_node, sensor_node, linked_transports
    ) -> None:
        a, _ = linked_transports

        response = await sensor_node.send_ping(
            target="jis:test:hub",
            addr=a.own_addr,
            intent="door.unlock",
            purpose="Unauthorized",
            timeout=1.0,
        )

        assert response is None

    @pytest.mark.asyncio
    async def test_peer_tracking(self, hub_node, sensor_node, linked_transports) -> None:
        a, b = linked_transports
        hub_node.set_trust("jis:test:sensor", 0.9)

        await sensor_node.send_ping(
            target="jis:test:hub",
            addr=a.own_addr,
            intent="test.tracking",
            purpose="Peer tracking test",
            timeout=2.0,
        )

        peers = hub_node.peers.alive_peers()
        assert len(peers) >= 1
        peer_dids = [p.device_did for p in peers]
        assert "jis:test:sensor" in peer_dids

    @pytest.mark.asyncio
    async def test_request_timeout(self, sensor_node) -> None:
        transport_b = MockTransport(("127.0.0.1", 9999))
        await transport_b.start()

        response = await sensor_node.send_ping(
            target="jis:test:nowhere",
            addr=("127.0.0.1", 9999),
            intent="test.timeout",
            purpose="Timeout test",
            timeout=0.5,
        )

        assert response is None
        await transport_b.stop()


class TestMeshRelay:
    @pytest.mark.asyncio
    async def test_relay_forwarding(self) -> None:
        a_transport = MockTransport(("127.0.0.1", 7150))
        b_transport = MockTransport(("127.0.0.1", 7151))
        a_transport._peer = b_transport
        b_transport._peer = a_transport

        node_a = IoTNode(
            "jis:test:relay",
            transport=a_transport,
            heartbeat_interval=300,
            discovery_interval=300,
        )
        node_a._transport.on_receive(node_a._handle_incoming)
        await node_a._transport.start()
        node_a._running = True

        node_a.peers.record_activity("jis:test:target", ("192.168.1.100", 7150))

        from tibet_ping import PingNode

        sender = PingNode("jis:test:sender")
        packet = sender.ping(
            target="jis:test:target",
            intent="data.forward",
            purpose="Relay test",
            routing_mode=RoutingMode.MESH,
        )

        await b_transport.start()
        await b_transport.send_packet(packet, a_transport.own_addr)

        await asyncio.sleep(0.1)

        relay_stats = node_a.relay.stats()
        assert relay_stats["relayed"] == 1

        node_a._running = False
        await a_transport.stop()
        await b_transport.stop()


class TestStats:
    @pytest.mark.asyncio
    async def test_node_stats(self, hub_node) -> None:
        stats = hub_node.stats()
        assert stats["device_did"] == "jis:test:hub"
        assert "peers" in stats
        assert "relay" in stats
        assert "ping_node" in stats
