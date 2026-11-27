"""Validate the root helper in a NET_ADMIN test container, never on the EC2 host."""
import json
from pathlib import Path
import shutil
import subprocess
import time

from session_access import render_sets, render_table, validate_config


def main():
    if not Path("/.dockerenv").exists():
        raise RuntimeError("Run this check only in the documented isolated Docker container")
    source = Path(__file__).resolve().parent
    Path("/etc/mirrage").mkdir(exist_ok=True)
    shutil.copyfile(source / "player-isolation.example.json", "/etc/mirrage/player-isolation.json")
    helper = "/usr/local/sbin/mirrage-session-access"
    shutil.copyfile(source / "session_access.py", helper)
    Path(helper).chmod(0o755)

    def run(*args, success=True):
        result = subprocess.run([helper, *args], capture_output=True, text=True, timeout=10)
        if (result.returncode == 0) != success:
            raise RuntimeError(f"Unexpected result for helper operation {args[0]}: {result.stderr}")
        return result.stdout

    def contents(name):
        return subprocess.check_output(["/usr/sbin/nft", "-j", "list", "set", "inet",
                                        "mirrage_player_guard", name], text=True)

    config = validate_config(json.loads((source / "player-isolation.example.json").read_text()))
    lease = {"before-upgrade": {"vpn_ip": "10.8.0.10", "pod_ip": "10.42.0.20",
                                "expires_at": int(time.time()) + 30}}
    subprocess.run(["/usr/sbin/nft", "-f", "-"], check=True, text=True,
                   input=render_table(config) + render_sets(config, lease))
    run("check", success=False)
    run("upgrade")
    run("upgrade")
    assert "10.8.0.10" in contents("active_pairs")
    run("install")
    assert "10.8.0.10" not in contents("active_pairs")
    subprocess.run(["/usr/sbin/nft", "delete", "table", "inet", "mirrage_player_guard"], check=True)
    run("install")
    assert json.loads(run("check"))["vpn_interface"] == "tun0"
    expiry = str(int(time.time()) + 30)
    run("grant", "--session", "test-a", "--vpn-ip", "10.8.0.10", "--pod-ip", "10.42.0.20", "--expires-at", expiry)
    assert json.loads(run("status", "--session", "test-a"))["active"]
    assert "10.8.0.10" in contents("active_pairs")
    run("grant", "--session", "test-b", "--vpn-ip", "10.8.0.11", "--pod-ip", "10.42.0.20", "--expires-at", expiry, success=False)
    run("forget", "--session", "test-a", success=False)
    run("revoke", "--session", "test-a")
    inventory = json.loads(run("inventory"))
    assert inventory["test-a"] == {"vpn_ip": "10.8.0.10", "pod_ip": "10.42.0.20", "expires_at": 0}
    run("renew", "--session", "test-a", "--vpn-ip", "10.8.0.10", "--pod-ip", "10.42.0.20", "--expires-at", expiry, success=False)
    assert "10.8.0.10" not in contents("active_pairs")
    assert "10.42.0.20" in contents("sandbox_pods")
    run("forget", "--session", "test-a")
    assert "test-a" not in json.loads(run("inventory"))
    assert "10.42.0.20" not in contents("sandbox_pods")
    run("grant", "--session", "expires", "--vpn-ip", "10.8.0.11", "--pod-ip", "10.42.0.21",
        "--expires-at", str(int(time.time()) + 2))
    time.sleep(3)
    assert "10.8.0.11" not in contents("active_pairs")
    assert "10.42.0.21" in contents("sandbox_pods")
    run("grant", "--session", "boot-check", "--vpn-ip", "10.8.0.12", "--pod-ip", "10.42.0.22",
        "--expires-at", str(int(time.time()) + 30))
    run("install")
    assert not json.loads(run("status", "--session", "boot-check"))["active"]
    print("PASS: nftables installation, configuration checks, owner bindings, revocation, inventory and automatic expiry")


if __name__ == "__main__":
    main()
