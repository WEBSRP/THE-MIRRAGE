#!/usr/bin/python3
"""Root-owned, narrowly scoped nftables helper. Never flush the host ruleset.

Config: /etc/mirrage/player-isolation.json (root-owned).
State/lock: /var/lib/mirrage/player-guard/ (root-only).
Install and upgrade are operator commands; upgrade preserves existing leases.
"""
import argparse
import fcntl
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time

CONFIG = Path("/etc/mirrage/player-isolation.json")
STATE_DIRECTORY = Path("/var/lib/mirrage/player-guard")
TABLE = "mirrage_player_guard"
NFT = "/usr/sbin/nft"
PING_RULE = "mirrage-vpn-echo-v1"


def validate_config(config):
    if set(config) != {"vpn_interface", "pod_interface", "node_name", "vpn_cidr", "pod_cidr", "callback_ports", "max_lease_seconds"}:
        raise ValueError("Invalid gateway configuration keys")
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,15}", config["vpn_interface"]):
        raise ValueError("Invalid VPN interface")
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,15}", config["pod_interface"]):
        raise ValueError("Invalid pod interface")
    if not re.fullmatch(r"[a-z0-9][a-z0-9.-]{0,252}", config["node_name"]):
        raise ValueError("Invalid gateway node name")
    vpn = ipaddress.IPv4Network(config["vpn_cidr"])
    pods = ipaddress.IPv4Network(config["pod_cidr"])
    if vpn.overlaps(pods):
        raise ValueError("VPN and pod networks overlap")
    if (not isinstance(config["callback_ports"], list)
            or any(type(port) is not int or not 1 <= port <= 65535 for port in config["callback_ports"])):
        raise ValueError("Invalid callback ports")
    config = dict(config, callback_ports=sorted(set(config["callback_ports"])))
    if type(config["max_lease_seconds"]) is not int or not 1 <= config["max_lease_seconds"] <= 86400:
        raise ValueError("Invalid lease duration")
    return config


def fingerprint(config):
    return "mirrage-v1:" + hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()


def render_table(config):
    interface = config["vpn_interface"]
    callback = ""
    if config["callback_ports"]:
        ports = ", ".join(map(str, config["callback_ports"]))
        callback = (f"ip saddr @sandbox_pods ip daddr . ip saddr @active_pairs "
                    f"tcp dport {{ {ports} }} accept")
    return f'''table inet {TABLE} {{
 comment "{fingerprint(config)}"
 set sandbox_pods {{ type ipv4_addr; }}
 set active_pairs {{ type ipv4_addr . ipv4_addr; flags timeout; }}
 chain host_input {{
  type filter hook input priority -10; policy accept;
  iifname "{interface}" drop
  iifname "{config['pod_interface']}" meta nfproto ipv6 drop
  ip saddr @sandbox_pods ct state {{ established, related }} accept
  ip saddr @sandbox_pods drop
 }}
 chain player_forward {{
  type filter hook forward priority -10; policy accept;
  iifname "{interface}" ip saddr . ip daddr @active_pairs tcp dport {{ 22, 80, 2222 }} accept
  iifname "{interface}" ip saddr . ip daddr @active_pairs ct state {{ established, related }} accept
  iifname "{interface}" drop
  iifname "{config['pod_interface']}" meta nfproto ipv6 drop
  ip saddr @sandbox_pods ip daddr . ip saddr @active_pairs ct state {{ established, related }} accept
  {callback}
  ip saddr @sandbox_pods drop
  oifname "{interface}" drop
 }}
}}
'''


def render_ping_rules(config):
    vpn = config["vpn_interface"]
    pods = config["pod_interface"]
    chain = f"inet {TABLE} player_ping"
    return f'''add set inet {TABLE} ping_rate {{
 type ipv4_addr . ipv4_addr; flags dynamic, timeout; timeout 10s; size 256;
}}
add chain {chain}
add rule {chain} iifname "{vpn}" oifname "{pods}" icmp type echo-request ip length <= 576 ip saddr . ip daddr @active_pairs update @ping_rate {{ ip saddr . ip daddr limit rate 2/second burst 4 packets }} counter accept
add rule {chain} iifname "{pods}" oifname "{vpn}" icmp type echo-reply ip length <= 576 ip daddr . ip saddr @active_pairs ct direction reply ct state established counter accept
add rule {chain} counter drop
insert rule inet {TABLE} player_forward oifname "{vpn}" icmp type {{ echo-request, echo-reply }} jump player_ping comment "{PING_RULE}"
insert rule inet {TABLE} player_forward iifname "{vpn}" icmp type {{ echo-request, echo-reply }} jump player_ping comment "{PING_RULE}"
'''


def validate_entry(config, session, entry):
    if not re.fullmatch(r"[a-z0-9-]{1,100}", session):
        raise ValueError("Invalid session identifier")
    if set(entry) != {"vpn_ip", "pod_ip", "expires_at"}:
        raise ValueError("Invalid session entry")
    for key, network_key in (("vpn_ip", "vpn_cidr"), ("pod_ip", "pod_cidr")):
        address = ipaddress.IPv4Address(entry[key])
        network = ipaddress.IPv4Network(config[network_key])
        if address not in network or address in (network.network_address, network.broadcast_address):
            raise ValueError("Address outside permitted network")
        if str(address) != entry[key]:
            raise ValueError("Noncanonical address")
    if type(entry["expires_at"]) is not int or entry["expires_at"] < 0:
        raise ValueError("Invalid session expiry")


def change_state(config, state, action, session, vpn_ip=None, pod_ip=None, expires_at=None, now=None):
    now = int(time.time()) if now is None else now
    state = {key: dict(value) for key, value in state.items()}
    for key, entry in state.items():
        validate_entry(config, key, entry)
    if not re.fullmatch(r"[a-z0-9-]{1,100}", session):
        raise ValueError("Invalid session identifier")
    if action in ("grant", "renew"):
        entry = {"vpn_ip": vpn_ip, "pod_ip": pod_ip, "expires_at": expires_at}
        validate_entry(config, session, entry)
        if not now < expires_at <= now + config["max_lease_seconds"]:
            raise ValueError("Expired or excessive access lease")
        previous = state.get(session)
        if action == "renew" and (not previous or previous["expires_at"] <= now):
            raise ValueError("A revoked/expired session cannot be renewed")
        if previous and (previous["vpn_ip"], previous["pod_ip"]) != (vpn_ip, pod_ip):
            raise ValueError("Session address binding cannot change")
        if action == "renew":
            # Out-of-order concurrent renewals must not shorten a newer lease.
            entry["expires_at"] = max(expires_at, previous["expires_at"])
        for key, other in state.items():
            if key != session and (other["pod_ip"] == pod_ip or (
                other["vpn_ip"] == vpn_ip and other["expires_at"] > now
            )):
                raise ValueError("Address is already bound to another session")
        state[session] = entry
    elif action == "revoke":
        if session in state:
            state[session]["expires_at"] = 0
    elif action == "forget":
        if session in state and state[session]["expires_at"] > now:
            raise ValueError("Revoke access before forgetting a pod")
        state.pop(session, None)
    else:
        raise ValueError("Invalid state operation")
    return state


def render_sets(config, state, now=None):
    now = int(time.time()) if now is None else now
    commands = [f"flush set inet {TABLE} active_pairs", f"flush set inet {TABLE} sandbox_pods"]
    pods, pairs = set(), []
    for session, entry in state.items():
        validate_entry(config, session, entry)
        pods.add(entry["pod_ip"])
        remaining = entry["expires_at"] - now
        if remaining > 0:
            remaining = min(remaining, config["max_lease_seconds"])
            pairs.append(f'{entry["vpn_ip"]} . {entry["pod_ip"]} timeout {remaining}s')
    if pods:
        commands.append(f"add element inet {TABLE} sandbox_pods {{ {', '.join(sorted(pods))} }}")
    if pairs:
        commands.append(f"add element inet {TABLE} active_pairs {{ {', '.join(pairs)} }}")
    return "\n".join(commands) + "\n"


def nft(*arguments, script=None):
    result = subprocess.run([NFT, *arguments], input=script, text=True,
                            capture_output=True, timeout=10)
    if result.returncode:
        raise RuntimeError("Gateway nftables operation failed")
    return result.stdout


def gateway_rules(config):
    for path in ("/proc/sys/net/ipv4/ip_forward", "/proc/sys/net/bridge/bridge-nf-call-iptables",
                 "/proc/sys/net/bridge/bridge-nf-call-ip6tables"):
        if Path(path).read_text().strip() != "1":
            raise RuntimeError("Required gateway/bridge packet filtering is disabled")
    data = json.loads(nft("-j", "list", "table", "inet", TABLE))
    tables = [row["table"] for row in data["nftables"] if "table" in row]
    if len(tables) != 1 or tables[0].get("comment") != fingerprint(config):
        raise RuntimeError("Gateway rules/configuration mismatch")
    return data["nftables"]


def ping_installed(rules):
    return sum(row.get("rule", {}).get("comment") == PING_RULE for row in rules) == 2


def check(config):
    if not ping_installed(gateway_rules(config)):
        raise RuntimeError("Gateway ping rules missing; run the operator upgrade")


def upgrade(config):
    if not ping_installed(gateway_rules(config)):
        # One transaction and no changes to the live pair set or its deadlines.
        nft("-f", "-", script=render_ping_rules(config))
    check(config)


def save_state(path, state):
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as handle:
            temporary = Path(handle.name)
            os.fchmod(handle.fileno(), 0o600)
            json.dump(state, handle)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["install", "upgrade", "check", "inventory", "status", "grant", "renew", "revoke", "forget"])
    parser.add_argument("--session")
    parser.add_argument("--vpn-ip")
    parser.add_argument("--pod-ip")
    parser.add_argument("--expires-at", type=int)
    args = parser.parse_args()
    if os.geteuid() != 0:
        raise RuntimeError("Gateway helper must run as root")
    info = CONFIG.stat()
    if CONFIG.is_symlink() or info.st_uid != 0 or info.st_mode & 0o022:
        raise RuntimeError("Gateway configuration must be root-owned and protected")
    config = validate_config(json.loads(CONFIG.read_text()))
    STATE_DIRECTORY.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = STATE_DIRECTORY.stat()
    if STATE_DIRECTORY.is_symlink() or info.st_uid != 0 or info.st_mode & 0o077:
        raise RuntimeError("Gateway state directory must be root-only")
    with (STATE_DIRECTORY / "lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        path = STATE_DIRECTORY / "sessions.json"
        state = json.loads(path.read_text()) if path.exists() else {}
        if args.action == "install":
            # Only our dedicated table, never 'flush ruleset' or k3s chains.
            present = subprocess.run([NFT, "list", "table", "inet", TABLE], capture_output=True).returncode == 0
            if not present:
                nft("-f", "-", script=render_table(config) + render_ping_rules(config))
            upgrade(config)
            # Pod IPs may have changed across a reboot. Keep source blocking, but
            # never replay permissions until the API rechecks actual pod ownership.
            state = {key: dict(entry, expires_at=0) for key, entry in state.items()}
            save_state(path, state)
            nft("-f", "-", script=render_sets(config, state))
        elif args.action == "upgrade":
            upgrade(config)
        elif args.action == "check":
            check(config)
            print(json.dumps(config))
        elif args.action == "inventory":
            check(config)
            for session, entry in state.items():
                validate_entry(config, session, entry)
            print(json.dumps(state))
        elif args.action == "status":
            check(config)
            if not re.fullmatch(r"[a-z0-9-]{1,100}", args.session or ""):
                raise ValueError("Invalid session identifier")
            entry = state.get(args.session)
            active = False
            if entry and entry["expires_at"] > time.time():
                validate_entry(config, args.session, entry)
                result = subprocess.run([NFT, "get", "element", "inet", TABLE, "active_pairs",
                                         "{", entry["vpn_ip"], ".", entry["pod_ip"], "}"],
                                        capture_output=True, timeout=10)
                active = result.returncode == 0
            print(json.dumps({"active": active, "binding": entry}))
        else:
            check(config)
            state = change_state(config, state, args.action, args.session or "", args.vpn_ip,
                                 args.pod_ip, args.expires_at)
            # Durable intent first: a failed kernel update is retryable after a crash.
            save_state(path, state)
            # One nft transaction: no momentary hole between set updates.
            nft("-f", "-", script=render_sets(config, state))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, TypeError, RuntimeError, subprocess.SubprocessError):
        print("Player gateway operation failed; check installation/configuration", file=sys.stderr)
        raise SystemExit(1) from None
