#!/usr/bin/env python3
"""Smoke-test a CTF image without network access or published ports."""
import argparse
from pathlib import Path
import subprocess
import uuid


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default="mirrage-ctf:shared-flags-check")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    missing = subprocess.run([
        "docker", "run", "--rm", "--network", "none", args.image, "/bin/true"
    ], capture_output=True, timeout=15)
    if missing.returncode != 1 or b"CTF startup failed" not in missing.stderr:
        raise RuntimeError("Target must fail closed without a flags mount")
    subprocess.run([
        "docker", "run", "--rm", "--network", "none", "--entrypoint", "python3", args.image,
        "-c", "from pathlib import Path; assert not any(Path(p).exists() for p in "
        "('/var/www/html/flag.txt','/home/player/flag.txt','/root/flag.txt'))",
    ], check=True, timeout=15)
    name = "mirrage-flags-smoke-" + uuid.uuid4().hex[:10]
    command = ["docker", "run", "--rm", "--detach", "--name", name,
               "--network", "none", "--memory", "512m", "--cpus", "0.5",
               "--pids-limit", "128", "--cap-drop", "ALL",
               "--security-opt", "no-new-privileges:true"]
    for capability in ("SYS_CHROOT", "SETUID", "SETGID", "CHOWN", "DAC_OVERRIDE",
                       "FOWNER", "KILL", "AUDIT_WRITE", "NET_BIND_SERVICE"):
        command.extend(["--cap-add", capability])
    command.extend([
        "--mount", f"type=bind,source={root / 'backend/ctf-flags.example.json'},target=/run/mirrage-flags/flags.json,readonly",
        "--mount", f"type=bind,source={root / 'containers/ctf/check_runtime.py'},target=/tmp/check_runtime.py,readonly",
        args.image,
    ])
    started = False
    try:
        subprocess.run(command, check=True, stdout=subprocess.DEVNULL)
        started = True
        subprocess.run(["docker", "exec", name, "python3", "/tmp/check_runtime.py"],
                       check=True, timeout=30)
    finally:
        if started:
            subprocess.run(["docker", "stop", "--time", "5", name],
                           check=True, stdout=subprocess.DEVNULL)


if __name__ == "__main__":
    main()
