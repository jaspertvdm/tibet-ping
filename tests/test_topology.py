"""Tests for topology.py — Hub, Hubby, Pod, Station."""

from tibet_ping.topology import NodeRole, Pod, Station, TopologyManager


def test_create_pod():
    tm = TopologyManager()
    pod = tm.create_pod("pod_kitchen", "Kitchen", "jis:home:hub_k")
    assert pod.pod_id == "pod_kitchen"
    assert pod.hub_did == "jis:home:hub_k"
    assert pod.member_count == 1


def test_add_hubby():
    tm = TopologyManager()
    tm.create_pod("pod_k", "Kitchen", "jis:home:hub")
    tm.add_hubby_to_pod("pod_k", "jis:home:temp")
    tm.add_hubby_to_pod("pod_k", "jis:home:humidity")

    pod = tm.pods["pod_k"]
    assert pod.member_count == 3
    assert "jis:home:temp" in pod.all_members
    assert "jis:home:humidity" in pod.all_members


def test_hubby_dedup():
    tm = TopologyManager()
    tm.create_pod("pod_k", "Kitchen", "jis:home:hub")
    tm.add_hubby_to_pod("pod_k", "jis:home:temp")
    tm.add_hubby_to_pod("pod_k", "jis:home:temp")  # duplicate
    assert tm.pods["pod_k"].member_count == 2


def test_get_pod_for_device():
    tm = TopologyManager()
    tm.create_pod("pod_k", "Kitchen", "jis:home:hub")
    tm.add_hubby_to_pod("pod_k", "jis:home:temp")

    assert tm.get_pod_for_device("jis:home:hub").pod_id == "pod_k"
    assert tm.get_pod_for_device("jis:home:temp").pod_id == "pod_k"
    assert tm.get_pod_for_device("jis:home:unknown") is None


def test_roles():
    tm = TopologyManager()
    tm.create_pod("pod_k", "Kitchen", "jis:home:hub")
    tm.add_hubby_to_pod("pod_k", "jis:home:temp")

    assert tm.get_role("jis:home:hub") == NodeRole.HUB
    assert tm.get_role("jis:home:temp") == NodeRole.HUBBY
    assert tm.get_role("jis:home:unknown") is None


def test_hybrid_role():
    """Device that is hub in one pod and hubby in another = HYBRID."""
    tm = TopologyManager()
    tm.create_pod("pod_a", "A", "jis:device")
    tm.create_pod("pod_b", "B", "jis:other_hub")
    tm.add_hubby_to_pod("pod_b", "jis:device")

    assert tm.get_role("jis:device") == NodeRole.HYBRID


def test_create_station():
    tm = TopologyManager()
    station = tm.create_station("station_home", "Home", "jis:home:gateway")
    assert station.station_id == "station_home"
    assert station.uplink_did == "jis:home:gateway"


def test_station_with_pods():
    tm = TopologyManager()
    tm.create_station("s1", "Building A")
    tm.create_pod("p1", "Kitchen", "jis:hub1", station_id="s1")
    tm.create_pod("p2", "Bedroom", "jis:hub2", station_id="s1")

    assert len(tm.stations["s1"].pod_ids) == 2


def test_stats():
    tm = TopologyManager()
    tm.create_station("s1", "Home")
    tm.create_pod("p1", "Kitchen", "jis:hub", station_id="s1")
    tm.add_hubby_to_pod("p1", "jis:temp")
    tm.add_hubby_to_pod("p1", "jis:humidity")

    stats = tm.stats()
    assert stats["pods"] == 1
    assert stats["stations"] == 1
    assert stats["total_devices"] == 3
    assert stats["roles"]["hub"] == 1
    assert stats["roles"]["hubby"] == 2


def test_pod_to_dict():
    pod = Pod(
        pod_id="p1", name="Kitchen", hub_did="jis:hub",
        hubby_dids=["jis:s1"], capabilities={"temperature"},
    )
    d = pod.to_dict()
    assert d["member_count"] == 2
    assert "temperature" in d["capabilities"]
