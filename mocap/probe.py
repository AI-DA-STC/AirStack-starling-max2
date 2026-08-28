#!/usr/bin/env python3
"""Answer "is mocap data actually reaching this laptop?" without ROS.

Listens raw on UDP 1511 for 6 seconds and reports how many NatNet packets
arrived, from where, and to what destination address. Run it any time poses
look dead — it separates "network problem" from "ROS problem" in one step.

  Destination 255.255.255.255 -> Motive is in Broadcast mode (our default;
                                 fine for mocap.sh, invisible to natnet_ros2)
  Destination 239.255.42.99   -> Motive is in Multicast mode (fine for both)
  0 packets                   -> nothing on the wire: Motive not streaming,
                                 wrong network, or a switch is filtering.

Safe to run alongside the bridge (it co-binds the port read-only).
"""
import socket
import struct
import time

s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
s.setsockopt(socket.IPPROTO_IP, socket.IP_PKTINFO, 1)
s.bind(("0.0.0.0", 1511))
s.settimeout(1.0)

print("listening on UDP 1511 for 6 seconds...")
end = time.time() + 6
count = 0
srcs = {}
dests = {}
first = None
while time.time() < end:
    try:
        data, anc, _flags, addr = s.recvmsg(65535, 1024)
    except socket.timeout:
        continue
    count += 1
    srcs[addr[0]] = srcs.get(addr[0], 0) + 1
    if first is None and len(data) >= 4:
        first = struct.unpack("<HH", data[:4])
    for lvl, typ, cd in anc:
        if lvl == socket.IPPROTO_IP and typ == socket.IP_PKTINFO:
            dst = socket.inet_ntoa(cd[8:12])
            dests[dst] = dests.get(dst, 0) + 1

print(f"packets in 6s : {count}  (~{count / 6:.0f} Hz)")
print(f"sources       : {srcs or 'none'}")
print(f"destinations  : {dests or 'none'}")
if first:
    msg = {7: "FrameOfData (pose frames - good)", 5: "ModelDef", 1: "ServerInfo"}
    print(f"first packet  : NatNet message id {first[0]} = "
          f"{msg.get(first[0], 'other')}")
if count == 0:
    print("VERDICT: nothing on the wire. Check: Motive streaming enabled? "
          "Laptop cable in the mocap LAN? Right subnet (see CONFIG.md)?")
elif any(d == "255.255.255.255" for d in dests):
    print("VERDICT: Motive is BROADCASTING - use ./mocap.sh (natnet_ros2 "
          "cannot hear this, see MOCAP.md).")
else:
    print("VERDICT: data is arriving as multicast - either receiver works.")
