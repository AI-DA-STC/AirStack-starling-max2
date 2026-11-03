# tools/tests/test_foxglove_bridge.py — the cuVSLAM Foxglove bridge profile and whitelists (static; no docker, no ROS)
import json, pathlib, re, unittest
import xml.etree.ElementTree as ET
ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "localisation/scripts/foxglove_bridge_isaac.sh"
NS = "{http://www.eprosima.com/XMLSchemas/fastRTPS_Profiles}"


def peers(path):
    """every initialPeersList locator as (address, port), in file order"""
    out = []
    for loc in ET.parse(path).getroot().iter(NS + "locator"):
        udp = loc.find(NS + "udpv4")
        if udp is not None:
            out.append((udp.findtext(NS + "address"), int(udp.findtext(NS + "port"))))
    return out


def whitelist(name):
    m = re.search(r"-p %s:='(\[.*?\])'" % name, SCRIPT.read_text())
    assert m, name
    return json.loads(m.group(1))


class Profile(unittest.TestCase):
    def test_bridge_profile_lists_thirty_host_peers(self):
        self.assertEqual(peers(ROOT / "localisation/docker/fastdds_bridge.xml"),
                         [("172.31.0.1", p) for p in range(7660, 7720, 2)])

    def test_bridge_profile_is_udp_without_builtin_transports(self):
        root = ET.parse(ROOT / "localisation/docker/fastdds_bridge.xml").getroot()
        self.assertEqual(root.findtext(".//" + NS + "useBuiltinTransports"), "false")
        self.assertEqual([t.text for t in root.iter(NS + "type")], ["UDPv4"])

    def test_plain_profile_has_no_peers(self):             # the node, recorder and Isaac stay unpeered
        self.assertEqual(peers(ROOT / "localisation/docker/fastdds.xml"), [])


class Script(unittest.TestCase):
    def test_script_exports_the_bridge_profile_before_exec(self):
        src = SCRIPT.read_text()
        export = "export FASTRTPS_DEFAULT_PROFILES_FILE=/exploration/docker/fastdds_bridge.xml"
        self.assertIn(export, src)
        self.assertLess(src.index(export), src.index("exec ros2 run"))

    def test_topic_whitelist_admits_both_worlds(self):
        rx = whitelist("topic_whitelist")
        for t in ("/joy", "/drone_2/joy", "/teleop_frame/status", "/drone_2/teleop_frame/status",
                  "/drone_1/cuvslam/debug_image", "/tf", "/clock"):
            self.assertTrue(any(re.search(r, t) for r in rx), t)
        self.assertFalse(any(re.search(r, "/svg/commander_status") for r in rx))

    def test_service_whitelist_admits_exactly_the_two_services(self):
        rx = whitelist("service_whitelist")
        for s in ("/teleop_frame/set_parameters", "/drone_2/teleop_frame/set_parameters",
                  "/safe_teleop/get_parameters", "/drone_2/safe_teleop/get_parameters"):
            self.assertTrue(any(re.search(r, s) for r in rx), s)
        for s in ("/swarm_commander/land", "/teleop_frame/get_parameters", "/safe_teleop/set_parameters"):
            self.assertFalse(any(re.search(r, s) for r in rx), s)

    def test_client_topics_are_only_joy(self):
        rx = whitelist("client_topic_whitelist")
        self.assertTrue(any(re.search(r, "/joy") for r in rx))
        self.assertTrue(any(re.search(r, "/drone_3/joy") for r in rx))
        self.assertFalse(any(re.search(r, "/cmd_vel") for r in rx))


class Probe(unittest.TestCase):
    def test_slam_up_warns_through_the_shared_helper(self):
        src = (ROOT / "localisation/scripts/slam_up.sh").read_text()
        self.assertIn("tools/lib/firewall_probe.sh", src)
        self.assertIn("sudo ufw allow from 172.31.0.0/24", (ROOT / "tools/lib/firewall_probe.sh").read_text())


if __name__ == "__main__":
    unittest.main()
