#!/usr/bin/env python3

import getpass
import os
import re
import subprocess
from pathlib import Path


# ============================================================
# Configuration
# ============================================================

EASY_RSA_DIR = Path.home() / "openvpn-ca"

CA_CERT = EASY_RSA_DIR / "pki" / "ca.crt"
TLS_KEY = EASY_RSA_DIR / "ta.key"

OUTPUT_DIR = Path.home() / "vpn-profiles"

VPN_SERVER = "ec2-18-205-71-26.compute-1.amazonaws.com"
VPN_PORT = 1194


# ============================================================
# Validation
# ============================================================

def validate_username(username: str) -> str:
    """
    Validate the VPN client name.

    Only letters, numbers, underscore and hyphen are allowed.
    Maximum length is 32 characters.
    """

    if not re.fullmatch(r"[a-zA-Z0-9_-]{1,32}", username):
        raise ValueError(
            "Invalid username. Use only letters, numbers, _ and -."
        )

    return username


# ============================================================
# Create Client Certificate
# ============================================================

def create_certificate(username: str):
    """
    Create a client certificate using Easy-RSA.

    The CA private key is encrypted, so the user is asked
    for the CA passphrase each time.
    """

    username = validate_username(username)

    command = [
        "./easyrsa",
        "build-client-full",
        username,
        "nopass"
    ]

    # Ask for the CA passphrase without displaying it.
    ca_password = getpass.getpass("Enter CA passphrase: ")

    # Environment variables used by Easy-RSA/OpenSSL.
    env = os.environ.copy()

    env["EASYRSA_BATCH"] = "1"
    env["EASYRSA_PASSIN"] = f"pass:{ca_password}"

    try:

        result = subprocess.run(
            command,
            cwd=EASY_RSA_DIR,
            env=env,
            text=True,
            capture_output=True
        )

    finally:

        # Remove the password from our Python variable
        # as soon as the subprocess has completed.
        ca_password = None

    if result.returncode != 0:

        error_message = result.stderr.strip()

        if not error_message:
            error_message = result.stdout.strip()

        raise RuntimeError(
            f"Easy-RSA failed:\n{error_message}"
        )

    print(f"Client certificate created for: {username}")


# ============================================================
# Generate .ovpn Profile
# ============================================================

def generate_ovpn(username: str) -> Path:
    """
    Generate an OpenVPN client profile containing:

    - CA certificate
    - Client certificate
    - Client private key
    - TLS crypt key
    """

    username = validate_username(username)

    client_cert = (
        EASY_RSA_DIR
        / "pki"
        / "issued"
        / f"{username}.crt"
    )

    client_key = (
        EASY_RSA_DIR
        / "pki"
        / "private"
        / f"{username}.key"
    )

    # --------------------------------------------------------
    # Verify required files
    # --------------------------------------------------------

    if not CA_CERT.exists():
        raise FileNotFoundError(
            f"Missing CA certificate: {CA_CERT}"
        )

    if not TLS_KEY.exists():
        raise FileNotFoundError(
            f"Missing TLS key: {TLS_KEY}"
        )

    if not client_cert.exists():
        raise FileNotFoundError(
            f"Missing client certificate: {client_cert}"
        )

    if not client_key.exists():
        raise FileNotFoundError(
            f"Missing client private key: {client_key}"
        )

    # --------------------------------------------------------
    # Read certificates and keys
    # --------------------------------------------------------

    ca = CA_CERT.read_text()

    cert = client_cert.read_text()

    key = client_key.read_text()

    tls_key = TLS_KEY.read_text()

    # --------------------------------------------------------
    # Build OpenVPN configuration
    # --------------------------------------------------------

    ovpn = f"""client

dev tun
proto udp

remote {VPN_SERVER} {VPN_PORT}

resolv-retry infinite
nobind

persist-key
persist-tun

remote-cert-tls server

data-ciphers AES-256-GCM:AES-128-GCM:CHACHA20-POLY1305
auth SHA256

verb 3

<ca>
{ca}
</ca>

<cert>
{cert}
</cert>

<key>
{key}
</key>

<tls-crypt>
{tls_key}
</tls-crypt>
"""

    # --------------------------------------------------------
    # Create output directory
    # --------------------------------------------------------

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    # --------------------------------------------------------
    # Create profile
    # --------------------------------------------------------

    output_file = (
        OUTPUT_DIR
        / f"{username}.ovpn"
    )

    output_file.write_text(ovpn)

    # Only the owner can read/write the profile.
    output_file.chmod(0o600)

    return output_file


# ============================================================
# Create Complete VPN Profile
# ============================================================

def create_vpn_profile(username: str) -> Path:
    """
    Complete provisioning process:

    1. Validate username
    2. Create client certificate
    3. Generate .ovpn profile
    """

    username = validate_username(username)

    print()
    print("=" * 50)
    print("Mirrage VPN Provisioner")
    print("=" * 50)
    print()

    print(f"Creating VPN certificate for: {username}")
    print()

    create_certificate(username)

    print()
    print("Generating OpenVPN profile...")

    profile = generate_ovpn(username)

    print()
    print("=" * 50)
    print("VPN profile created successfully")
    print("=" * 50)
    print()
    print(f"Profile: {profile}")
    print()
    print("File permissions: 600")
    print()


    return profile


# ============================================================
# Main
# ============================================================

if __name__ == "__main__":

    import argparse

    parser = argparse.ArgumentParser(
        description="Create a Mirrage OpenVPN client profile."
    )

    parser.add_argument(
        "username",
        help="CTF player username"
    )

    args = parser.parse_args()

    try:

        create_vpn_profile(args.username)

    except KeyboardInterrupt:

        print()
        print("Operation cancelled.")

        raise SystemExit(130)

    except Exception as error:

        print()
        print(f"ERROR: {error}")

        raise SystemExit(1)
