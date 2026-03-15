"""Tests for NetworkDiscovery — beacon broadcast and reception."""

from __future__ import annotations

import asyncio

import pytest
from tibet_ping import PingNode, PingPacket, PingType

from tibet_ping.transport.discovery import NetworkDiscovery
from conftest_transport import MockTransport


class TestNetworkDiscovery:
    @pytest.mark.asyncio
    async def test_ignore_own_beacon(self) -> None:
        transport = MockTransport()
        ping_node = PingNode("jis:test:hub")
        discovery = NetworkDiscovery(
            device_did="jis:test:hub",
            ping_node=ping_node,
            transport=transport,
        )

        discovered = []

        async def on_found(did, addr, resp):
            discovered.append(did)

        discovery.on_discovered(on_found)

        own_packet = ping_node.discover()
        discovery._on_beacon_received(own_packet, ("127.0.0.1", 7151))

        await asyncio.sleep(0.01)

        assert len(discovered) == 0

    @pytest.mark.asyncio
    async def test_handle_foreign_beacon(self) -> None:
        transport = MockTransport()
        hub_node = PingNode("jis:test:hub")
        discovery = NetworkDiscovery(
            device_did="jis:test:hub",
            ping_node=hub_node,
            transport=transport,
        )

        discovered = []

        async def on_found(did, addr, resp):
            discovered.append((did, addr))

        discovery.on_discovered(on_found)

        sensor_node = PingNode("jis:test:sensor")
        foreign_packet = sensor_node.discover(capabilities=["temperature"])
        discovery._on_beacon_received(foreign_packet, ("192.168.1.42", 7151))

        await asyncio.sleep(0.05)

        assert len(discovered) == 1
        assert discovered[0][0] == "jis:test:sensor"
        assert discovered[0][1] == ("192.168.1.42", 7151)

    @pytest.mark.asyncio
    async def test_multiple_callbacks(self) -> None:
        transport = MockTransport()
        ping_node = PingNode("jis:test:hub")
        discovery = NetworkDiscovery(
            device_did="jis:test:hub",
            ping_node=ping_node,
            transport=transport,
        )

        calls_a = []
        calls_b = []

        async def cb_a(did, addr, resp):
            calls_a.append(did)

        async def cb_b(did, addr, resp):
            calls_b.append(did)

        discovery.on_discovered(cb_a)
        discovery.on_discovered(cb_b)

        sensor_node = PingNode("jis:test:sensor")
        packet = sensor_node.discover()
        discovery._on_beacon_received(packet, ("192.168.1.42", 7151))

        await asyncio.sleep(0.05)

        assert len(calls_a) == 1
        assert len(calls_b) == 1
