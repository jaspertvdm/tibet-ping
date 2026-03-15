"""IoTNode — async wrapper composing PingNode + Transport + Peers + Discovery + Relay.

The IoTNode is the main entry point for the transport layer. It wraps the sync
PingNode (proto layer) with async transport, peer tracking, LAN discovery,
and mesh relay.

Compositie, geen inheritance. PingNode blijft sync.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional, Tuple, Union

from tibet_ping import (
    PingNode,
    PingPacket,
    PingResponse,
    PingDecision,
    PingType,
    Priority,
    RoutingMode,
)

from .codec import PacketCodec
from .discovery import NetworkDiscovery
from .peers import PeerTracker
from .relay import MeshRelay
from .udp import Transport, TransportConfig, UDPTransport

logger = logging.getLogger(__name__)

# Background task intervals
HEARTBEAT_INTERVAL = 30.0  # seconds
DISCOVERY_INTERVAL = 60.0  # seconds
PEER_CLEANUP_INTERVAL = 45.0  # seconds

# Request timeout
REQUEST_TIMEOUT = 10.0  # seconds


class IoTNode:
    """Async IoT node composing PingNode with network transport.

    Args:
        device_did: JIS DID for this device.
        transport: Transport implementation (defaults to UDPTransport).
        config: Transport config (used only if transport is None).
        heartbeat_interval: seconds between heartbeats.
        discovery_interval: seconds between discovery broadcasts.
        peer_timeout: seconds before a peer is considered stale.
    """

    def __init__(
        self,
        device_did: str,
        transport: Transport | None = None,
        config: TransportConfig | None = None,
        heartbeat_interval: float = HEARTBEAT_INTERVAL,
        discovery_interval: float = DISCOVERY_INTERVAL,
        peer_timeout: float = 90.0,
    ) -> None:
        self._device_did = device_did

        # Proto layer (sync)
        self._ping_node = PingNode(device_did)

        # Transport (async)
        self._config = config or TransportConfig()
        self._transport = transport or UDPTransport(self._config)

        # Peer tracking
        self._peers = PeerTracker(timeout=peer_timeout)

        # Mesh relay
        self._relay = MeshRelay(device_did)

        # Discovery
        self._discovery = NetworkDiscovery(
            device_did=device_did,
            ping_node=self._ping_node,
            transport=self._transport,
        )

        # Request-response correlation
        self._pending: dict[str, asyncio.Future[PingResponse]] = {}

        # Background tasks
        self._tasks: list[asyncio.Task[None]] = []
        self._heartbeat_interval = heartbeat_interval
        self._discovery_interval = discovery_interval
        self._running = False

    @property
    def device_did(self) -> str:
        return self._device_did

    @property
    def ping_node(self) -> PingNode:
        return self._ping_node

    @property
    def peers(self) -> PeerTracker:
        return self._peers

    @property
    def relay(self) -> MeshRelay:
        return self._relay

    @property
    def discovery(self) -> NetworkDiscovery:
        return self._discovery

    @property
    def transport(self) -> Transport:
        return self._transport

    @property
    def running(self) -> bool:
        return self._running

    # --- Lifecycle ---

    async def start(self) -> None:
        """Start the node: transport, discovery, and background tasks."""
        if self._running:
            return

        # Register receive handler
        self._transport.on_receive(self._handle_incoming)

        # Start transport
        await self._transport.start()

        # Start discovery
        try:
            await self._discovery.start_listening()
        except OSError as exc:
            logger.warning("Discovery multicast unavailable: %s", exc)

        # Start background tasks
        self._tasks = [
            asyncio.create_task(self._heartbeat_loop(), name="heartbeat"),
            asyncio.create_task(self._discovery_loop(), name="discovery"),
            asyncio.create_task(self._peer_cleanup_loop(), name="peer_cleanup"),
        ]

        self._running = True
        logger.info("IoTNode %s started", self._device_did)

    async def stop(self) -> None:
        """Stop the node and all background tasks."""
        if not self._running:
            return
        self._running = False

        # Cancel background tasks
        for task in self._tasks:
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks = []

        # Cancel pending requests
        for fut in self._pending.values():
            if not fut.done():
                fut.cancel()
        self._pending.clear()

        # Stop discovery and transport
        await self._discovery.stop()
        await self._transport.stop()

        logger.info("IoTNode %s stopped", self._device_did)

    # --- Sending ---

    async def send_ping(
        self,
        target: str,
        addr: Tuple[str, int],
        intent: str,
        purpose: str,
        ping_type: PingType = PingType.INTENT,
        priority: Priority = Priority.NORMAL,
        routing_mode: RoutingMode = RoutingMode.DIRECT,
        payload: dict[str, Any] | None = None,
        timeout: float = REQUEST_TIMEOUT,
    ) -> PingResponse | None:
        """Send a ping and wait for a response.

        Returns PingResponse or None on timeout.
        """
        # Create packet via proto layer (sync)
        packet = self._ping_node.ping(
            target=target,
            intent=intent,
            purpose=purpose,
            ping_type=ping_type,
            priority=priority,
            routing_mode=routing_mode,
            payload=payload,
        )

        # Set up response future
        loop = asyncio.get_running_loop()
        future: asyncio.Future[PingResponse] = loop.create_future()
        self._pending[packet.packet_id] = future

        # Send over transport
        await self._transport.send_packet(packet, addr)

        # Wait for response with timeout
        try:
            response = await asyncio.wait_for(future, timeout=timeout)
            return response
        except asyncio.TimeoutError:
            logger.debug("Ping %s timed out after %.1fs", packet.packet_id, timeout)
            return None
        finally:
            self._pending.pop(packet.packet_id, None)

    async def send_heartbeat(
        self,
        target: str = "broadcast",
        addr: Tuple[str, int] | None = None,
        status: dict[str, Any] | None = None,
    ) -> None:
        """Send a heartbeat. If addr is None, broadcast."""
        packet = self._ping_node.heartbeat(target=target, status=status)
        if addr:
            await self._transport.send_packet(packet, addr)
        else:
            await self._transport.broadcast(packet)

    # --- Trust management (delegates to PingNode) ---

    def set_trust(self, did: str, trust: float) -> None:
        """Set trust level for a device."""
        self._ping_node.set_trust(did, trust)

    def vouch(self, *args: Any, **kwargs: Any) -> Any:
        """Vouch for devices (delegates to PingNode)."""
        return self._ping_node.vouch(*args, **kwargs)

    def add_rule(self, *args: Any, **kwargs: Any) -> None:
        """Add an airlock rule (delegates to PingNode)."""
        self._ping_node.add_rule(*args, **kwargs)

    # --- Incoming packet handling ---

    async def _handle_incoming(
        self,
        decoded: Union[PingPacket, PingResponse],
        addr: Tuple[str, int],
    ) -> None:
        """Handle an incoming packet or response."""
        if isinstance(decoded, PingResponse):
            self._handle_response(decoded, addr)
            return

        packet: PingPacket = decoded

        # Track peer
        self._peers.record_activity(packet.source_did, addr)

        # Check if this packet is for us
        if packet.target_did != self._device_did and packet.target_did != "broadcast":
            # Not for us — try mesh relay
            await self._handle_relay(packet)
            return

        # Process through proto pipeline (sync)
        response = self._ping_node.receive(packet)

        # ROOD = silent drop (no response sent)
        if response.decision == PingDecision.REJECT:
            logger.debug(
                "ROOD drop: %s from %s", packet.packet_id, packet.source_did
            )
            return

        # Send response back
        await self._transport.send_response(response, addr)

    def _handle_response(
        self, response: PingResponse, addr: Tuple[str, int]
    ) -> None:
        """Handle an incoming response — resolve pending future."""
        future = self._pending.get(response.in_response_to)
        if future and not future.done():
            future.set_result(response)
        else:
            logger.debug(
                "Orphan response %s (no pending request)", response.response_id
            )

    async def _handle_relay(self, packet: PingPacket) -> None:
        """Attempt to relay a packet through the mesh."""
        relayed = self._relay.prepare_relay(packet)
        if relayed is None:
            return

        # Try to find the target in our peer list
        target_addr = self._peers.get_address(relayed.target_did)
        if target_addr:
            await self._transport.send_packet(relayed, target_addr)
            logger.debug(
                "Relayed %s to %s at %s",
                relayed.packet_id,
                relayed.target_did,
                target_addr,
            )
        else:
            # Broadcast and hope someone picks it up
            await self._transport.broadcast(relayed)
            logger.debug(
                "Broadcast relay %s for %s",
                relayed.packet_id,
                relayed.target_did,
            )

    # --- Background tasks ---

    async def _heartbeat_loop(self) -> None:
        """Periodic heartbeat broadcast."""
        while self._running:
            try:
                await asyncio.sleep(self._heartbeat_interval)
                await self.send_heartbeat()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.warning("Heartbeat error: %s", exc)

    async def _discovery_loop(self) -> None:
        """Periodic discovery broadcast."""
        while self._running:
            try:
                await asyncio.sleep(self._discovery_interval)
                await self._discovery.broadcast_discover()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.warning("Discovery error: %s", exc)

    async def _peer_cleanup_loop(self) -> None:
        """Periodic stale peer cleanup."""
        while self._running:
            try:
                await asyncio.sleep(PEER_CLEANUP_INTERVAL)
                pruned = self._peers.prune_stale()
                if pruned:
                    logger.debug("Pruned %d stale peers", pruned)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.warning("Peer cleanup error: %s", exc)

    # --- Stats ---

    def stats(self) -> dict:
        """Comprehensive node statistics."""
        return {
            "device_did": self._device_did,
            "running": self._running,
            "ping_node": self._ping_node.stats(),
            "peers": self._peers.stats(),
            "relay": self._relay.stats(),
            "pending_requests": len(self._pending),
        }
