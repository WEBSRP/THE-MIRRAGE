#!/usr/bin/env python3
"""Test gateway packet filtering on disposable Docker networks without NAT/default routes.

This simulates tun0 with a container interface. It does not validate a live CNI
or replace the final two-client OpenVPN/anti-spoofing deployment acceptance test.
"""
import argparse
import ipaddress
import json
from pathlib import Path
import re
import subprocess
import time
import uuid


def docker(*args, check=True):
    return subprocess.run(["docker", *args], text=True, capture_output=True, check=check, timeout=40)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default="mirrage-player-guard:check")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    suffix = uuid.uuid4().hex[:8]
    prefix = "mirrage-network-check-" + suffix
    # Benchmark-only address space; refuse overlaps with existing host routes.
    routes = json.loads(subprocess.check_output(["ip", "-j", "route", "show"], text=True))
    used = [ipaddress.ip_network(row["dst"]) for row in routes if row.get("dst") not in (None, "default")]
    for octet in range(20, 240):
        vpn = ipaddress.ip_network(f"198.18.{octet}.0/24")
        pods = ipaddress.ip_network(f"198.19.{octet}.0/24")
        if not any(network.overlaps(old) for network in (vpn, pods) for old in used if old.version == 4):
            break
    else:
        raise RuntimeError("No isolated test subnet available")
    vpn_ip = lambda last: str(vpn.network_address + last)
    pod_ip = lambda last: str(pods.network_address + last)
    networks, containers = [], []
    try:
        for label, subnet in (("vpn", vpn), ("pods", pods)):
            name = prefix + "-" + label
            # Docker's --internal filter also blocks intentionally routed traffic
            # between these test subnets. Disable NAT and delete default routes
            # instead, so all test traffic stays within the two benchmark CIDRs.
            docker("network", "create", "--opt", "com.docker.network.bridge.enable_ip_masquerade=false",
                   "--subnet", str(subnet), name)
            networks.append(name)

        def start(label, network, address, port):
            name = prefix + "-" + label
            extra = ["--sysctl", "net.ipv4.ip_forward=1"] if label == "gateway" else []
            docker("run", "--rm", "--detach", "--name", name, "--network", network,
                   "--ip", address, "--cap-add", "NET_ADMIN", "--memory", "192m", "--pids-limit", "64",
                   "--mount", f"type=bind,source={root / 'infrastructure/openvpn'},target=/checks,readonly",
                   *extra, "--entrypoint", "python3", args.image, "-m", "http.server", str(port))
            containers.append(name)
            return name

        gateway = start("gateway", networks[0], vpn_ip(254), 8000)
        docker("network", "connect", "--ip", pod_ip(254), networks[1], gateway)
        clients = [start("a", networks[0], vpn_ip(10), 4444), start("b", networks[0], vpn_ip(11), 4444)]
        targets = [start("target-a", networks[1], pod_ip(20), 80), start("target-b", networks[1], pod_ip(21), 80)]

        def execute(container, *command, check=True):
            return docker("exec", container, *command, check=check)

        for container in containers:
            execute(container, "ip", "route", "del", "default", check=False)

        execute(gateway, "ip", "link", "set", "eth0", "down")
        execute(gateway, "ip", "link", "set", "eth0", "name", "tun0")
        execute(gateway, "ip", "link", "set", "tun0", "up")
        for index, client in enumerate(clients):
            execute(client, "ip", "route", "replace", str(pods), "via", vpn_ip(254))
            # Real tun clients send peer traffic through OpenVPN, not direct L2.
            execute(client, "ip", "route", "replace", vpn_ip(11 - index) + "/32", "via", vpn_ip(254))
        for target in targets:
            execute(target, "ip", "route", "replace", str(vpn), "via", pod_ip(254))
        config = {"vpn_interface": "tun0", "pod_interface": "eth1", "node_name": "test-node",
                  "vpn_cidr": str(vpn), "pod_cidr": str(pods),
                  "callback_ports": [4444], "max_lease_seconds": 18000}
        execute(gateway, "python3", "-c", "from pathlib import Path; "
                "Path('/etc/mirrage').mkdir(exist_ok=True); "
                f"Path('/etc/mirrage/player-isolation.json').write_text({json.dumps(json.dumps(config))})")

        def helper(*command):
            return execute(gateway, "python3", "/checks/session_access.py", *command)

        helper("install")
        expiry = str(int(time.time()) + 120)
        for index in range(2):
            helper("grant", "--session", f"player-{index}", "--vpn-ip", vpn_ip(10 + index),
                   "--pod-ip", pod_ip(20 + index), "--expires-at", expiry)

        def reachable(container, address, port):
            result = execute(container, "curl", "--noproxy", "*", "--silent", "--output", "/dev/null",
                             "--connect-timeout", "1", "--max-time", "2", "--write-out", "%{http_code}",
                             f"http://{address}:{port}/", check=False)
            return result.returncode == 0 and result.stdout == "200"

        def ping(container, address, *options):
            return execute(container, "ping", "-n", "-q", "-W", "1", *options, address, check=False)

        burst = ping(clients[0], pod_ip(20), "-i", "0.01", "-c", "20")
        replies = re.search(r"\b(\d+) received\b", burst.stdout)
        assert burst.returncode == 0 and replies and 1 <= int(replies[1]) < 20, burst.stdout + burst.stderr
        assert ping(clients[1], pod_ip(21), "-c", "1").returncode == 0, "A's burst blocked B's ping"
        time.sleep(0.5)
        assert ping(clients[0], pod_ip(20), "-c", "1").returncode == 0, "Owner ping did not recover"
        assert ping(clients[1], pod_ip(21), "-s", "600", "-c", "1").returncode == 1, "Oversized ping was allowed"
        assert ping(clients[0], pod_ip(21), "-c", "1").returncode == 1, "Cross-player ping was allowed"
        assert ping(clients[0], vpn_ip(254), "-c", "1").returncode == 1, "Gateway accepted player ping"
        assert ping(targets[0], vpn_ip(10), "-c", "1").returncode == 1, "Pod initiated a VPN ping"

        assert reachable(gateway, "127.0.0.1", 8000)
        for index in range(2):
            assert reachable(clients[index], pod_ip(20 + index), 80), "Owner target was blocked"
            assert not reachable(clients[index], pod_ip(21 - index), 80), "Cross-player target was reachable"
            assert not reachable(clients[index], vpn_ip(254), 8000), "Gateway host service was reachable"
            assert not reachable(clients[index], vpn_ip(11 - index), 4444), "Other VPN client was reachable"
            assert reachable(targets[index], vpn_ip(10 + index), 4444), "Owner callback was blocked"
            assert not reachable(targets[index], vpn_ip(11 - index), 4444), "Wrong-player callback was reachable"
            assert not reachable(targets[index], pod_ip(254), 8000), "Sandbox reached the host service"
        helper("revoke", "--session", "player-0")
        assert ping(clients[0], pod_ip(20), "-c", "1").returncode == 1, "Revoked player could still ping"
        assert not reachable(clients[0], pod_ip(20), 80), "Revoked player still reached target"
        assert not reachable(targets[0], vpn_ip(10), 4444), "Revoked callback was still reachable"
        assert reachable(clients[1], pod_ip(21), 80), "Revoking A interrupted B"
        print("PASS: owner-only access, rate-limited ping, host/peer denial and revocation")
    finally:
        for name in reversed(containers):
            docker("stop", "--time", "1", name, check=False)
        for name in reversed(networks):
            docker("network", "rm", name, check=False)


if __name__ == "__main__":
    main()
