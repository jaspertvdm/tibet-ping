"""
Network topology: Hub, Hubby, Pod, Station.

Every device can be both hub (uplink) and hubby (downlink).
Pods group devices by function. Stations group pods by location.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set


class NodeRole(Enum):
    """Role in the topology."""
    HUB = "hub"        # Uplink aggregator, routes for pod
    HUBBY = "hubby"    # Downlink, connected to a hub
    HYBRID = "hybrid"  # Both hub and hubby (mesh node)


@dataclass
class Pod:
    """
    Logical group of hub + hubbies with shared function.

    Example: "kitchen_sensors" pod with temperature, humidity, motion sensors.
    """
    pod_id: str
    name: str
    hub_did: str
    hubby_dids: List[str] = field(default_factory=list)
    capabilities: Set[str] = field(default_factory=set)
    station_id: Optional[str] = None

    def add_hubby(self, did: str) -> None:
        """Add a hubby to this pod."""
        if did not in self.hubby_dids:
            self.hubby_dids.append(did)

    def remove_hubby(self, did: str) -> None:
        """Remove a hubby from this pod."""
        if did in self.hubby_dids:
            self.hubby_dids.remove(did)

    @property
    def all_members(self) -> List[str]:
        """All DIDs in this pod (hub + hubbies)."""
        return [self.hub_did] + list(self.hubby_dids)

    @property
    def member_count(self) -> int:
        return 1 + len(self.hubby_dids)

    def to_dict(self) -> dict:
        return {
            "pod_id": self.pod_id,
            "name": self.name,
            "hub_did": self.hub_did,
            "hubby_dids": self.hubby_dids,
            "member_count": self.member_count,
            "capabilities": sorted(self.capabilities),
            "station_id": self.station_id,
        }


@dataclass
class Station:
    """
    Collection of pods with shared uplink.

    Example: "building_A" station with HVAC, security, access pods.
    """
    station_id: str
    name: str
    pod_ids: List[str] = field(default_factory=list)
    uplink_did: Optional[str] = None

    def add_pod(self, pod_id: str) -> None:
        if pod_id not in self.pod_ids:
            self.pod_ids.append(pod_id)

    def remove_pod(self, pod_id: str) -> None:
        if pod_id in self.pod_ids:
            self.pod_ids.remove(pod_id)

    def to_dict(self) -> dict:
        return {
            "station_id": self.station_id,
            "name": self.name,
            "pod_count": len(self.pod_ids),
            "pod_ids": self.pod_ids,
            "uplink_did": self.uplink_did,
        }


class TopologyManager:
    """
    Manage hub/hubby/pod/station topology.

    Any device can be both hub and hubby (mesh capability).
    """

    def __init__(self) -> None:
        self.pods: Dict[str, Pod] = {}
        self.stations: Dict[str, Station] = {}
        self._did_to_pod: Dict[str, str] = {}
        self._did_role: Dict[str, NodeRole] = {}

    def create_pod(
        self,
        pod_id: str,
        name: str,
        hub_did: str,
        station_id: Optional[str] = None,
        capabilities: Optional[Set[str]] = None,
    ) -> Pod:
        """Create a new pod with a hub."""
        pod = Pod(
            pod_id=pod_id,
            name=name,
            hub_did=hub_did,
            station_id=station_id,
            capabilities=capabilities or set(),
        )
        self.pods[pod_id] = pod
        self._did_to_pod[hub_did] = pod_id
        self._did_role[hub_did] = NodeRole.HUB

        if station_id and station_id in self.stations:
            self.stations[station_id].add_pod(pod_id)

        return pod

    def add_hubby_to_pod(self, pod_id: str, hubby_did: str) -> None:
        """Add a hubby device to an existing pod."""
        if pod_id not in self.pods:
            raise ValueError(f"Pod not found: {pod_id}")
        self.pods[pod_id].add_hubby(hubby_did)
        self._did_to_pod[hubby_did] = pod_id
        # If already a hub elsewhere, mark as hybrid
        if hubby_did in self._did_role and self._did_role[hubby_did] == NodeRole.HUB:
            self._did_role[hubby_did] = NodeRole.HYBRID
        else:
            self._did_role[hubby_did] = NodeRole.HUBBY

    def get_pod_for_device(self, did: str) -> Optional[Pod]:
        """Find which pod a device belongs to."""
        pod_id = self._did_to_pod.get(did)
        return self.pods.get(pod_id) if pod_id else None

    def get_role(self, did: str) -> Optional[NodeRole]:
        """Get device role in topology."""
        return self._did_role.get(did)

    def create_station(
        self,
        station_id: str,
        name: str,
        uplink_did: Optional[str] = None,
    ) -> Station:
        """Create a new station."""
        station = Station(
            station_id=station_id,
            name=name,
            uplink_did=uplink_did,
        )
        self.stations[station_id] = station
        return station

    def stats(self) -> dict:
        """Topology statistics."""
        roles = {}
        for r in self._did_role.values():
            roles[r.value] = roles.get(r.value, 0) + 1
        return {
            "pods": len(self.pods),
            "stations": len(self.stations),
            "total_devices": len(self._did_to_pod),
            "roles": roles,
        }
