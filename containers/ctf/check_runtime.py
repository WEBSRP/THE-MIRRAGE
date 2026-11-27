"""Run inside an isolated test container after its normal entrypoint/CMD start."""
import hashlib
import json
from pathlib import Path
import pwd
import socket
import subprocess
import time
import urllib.error
import urllib.request


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def main():
    flags = json.loads(Path("/run/mirrage-flags/flags.json").read_text())
    for port in (80, 5000):
        for _ in range(50):
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=1):
                    break
            except OSError:
                time.sleep(0.1)
        else:
            raise RuntimeError(f"Target service on port {port} did not start")
    with socket.socket() as ssh:
        ssh.settimeout(1)
        require(ssh.connect_ex(("127.0.0.1", 22)) != 0, "SSH started without a developer key")
    with urllib.request.urlopen("http://127.0.0.1/_health", timeout=3) as response:
        require(response.status == 200, "Forum backend readiness endpoint failed")
    paths = {
        "web": (Path("/var/www/html/flag.txt"), "www-data"),
        "user": (Path("/home/player/flag.txt"), "player"),
        "root": (Path("/root/flag.txt"), "root"),
    }
    for stage, (path, owner) in paths.items():
        account = pwd.getpwnam(owner)
        require(path.stat().st_uid == account.pw_uid, f"Wrong {stage} flag owner")
        require(path.stat().st_mode & 0o777 == 0o600, f"Wrong {stage} flag mode")
        require(path.read_text().strip() == flags[stage], f"Wrong {stage} flag content")
    for account, path in (
        ("www-data", paths["user"][0]), ("www-data", paths["root"][0]),
        ("player", paths["root"][0]),
        ("www-data", Path("/run/mirrage-flags/flags.json")),
        ("player", Path("/run/mirrage-flags/flags.json")),
    ):
        result = subprocess.run(["runuser", "-u", account, "--", "cat", str(path)], capture_output=True)
        require(result.returncode != 0, f"Unexpected {account} read access")
    for path in ("/flag.txt", "/%66lag.txt"):
        try:
            urllib.request.urlopen("http://127.0.0.1" + path, timeout=3)
        except urllib.error.HTTPError as error:
            require(error.code == 404, "Web flag route must return 404")
        else:
            raise RuntimeError("Web flag is directly downloadable")
    # Exercise the deliberately vulnerable path only inside this isolated target.
    with urllib.request.urlopen(
        "http://127.0.0.1/forum/submit?cmd=cat%20flag.txt", timeout=3
    ) as response:
        digest = hashlib.sha256(response.read().strip()).hexdigest()
    require(digest == hashlib.sha256(flags["web"].encode()).hexdigest(),
            "Intended web-stage flag recovery is broken")
    print("PASS: services, flag content/ownership, stage isolation, HTTP denial and intended web recovery")


if __name__ == "__main__":
    main()
