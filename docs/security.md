# MIRRAGE Security Architecture and Operational Practices

This document outlines the security controls, credential management boundaries, network isolation mechanisms, and backup protocols implemented across the MIRRAGE platform.

---

## 1. Security Architecture Principles

The platform follows defense-in-depth principles designed around four pillars:
1. **Zero Public Attack Surface for Internal Services**: Compute workloads, sandboxes, and databases have no direct public IPv4 or IPv6 endpoints.
2. **Strict Separation of Public Configuration and Private Secrets**: Repository tracking is restricted strictly to sanitize-by-default templates.
3. **Mandatory Least Privilege**: Pods, systemd units, and VPN profiles run with minimized capabilities, strict filesystem restrictions, and unprivileged user identities.
4. **Hard Fail-Closed Guards**: Security-sensitive endpoints (such as test authentication) automatically reject requests outside designated development environments.

---

## 2. Configuration and Credential Boundaries

Configuration artifacts are categorized strictly based on sensitivity and commit safety.

### Git-Tracked (Safe) Configuration

These files reside in version control and must contain only non-sensitive templates or structural definitions:

- **`backend/.env.example`**: Documents valid environment variable keys using mock or placeholder values. Contains no production credentials, tokens, or live hostnames.
- **`infrastructure/openvpn/server.conf.example`**: OpenVPN server configuration defining routing (`push "route 10.42.0.0 255.255.0.0"`), cipher specifications (`AES-256-GCM`), and standard paths.
- **`infrastructure/nginx/mirrage.conf.example`**: Nginx reverse proxy definition handling loopback forwarding to `127.0.0.1:8000`.
- **`infrastructure/systemd/mirrage-backend.service.example`**: Systemd unit definition running Uvicorn under an unprivileged user.
- **`infrastructure/cloudflare/README.md`**: Procedural guide for setting up the Cloudflare zero-trust tunnel.
- **Kubernetes Manifests (`infrastructure/kubernetes/*.yaml`)**: Generic pod and network policy definitions with template labels and resource limits; no Kubernetes `Secret` resources or embedded credentials are committed.

### EC2-Only Secret Material (NEVER Committed)

The following files contain live cryptographic material, private keys, or infrastructure credentials and exist exclusively on the EC2 host:

- **`backend/.env`**: Houses live production secrets, including the production JWT signing key (`SECRET_KEY`), AWS RDS PostgreSQL database connection credentials (`DATABASE_URL`), and production CORS domain whitelists.
- **`~/openvpn-ca/`**: The complete Easy-RSA Public Key Infrastructure (PKI) directory. This holds the Certificate Authority (CA) private key (`pki/private/ca.key`) and all generated client private keys (`pki/private/*.key`).
- **`~/openvpn-ca/ta.key`**: The shared TLS-crypt key used by OpenVPN to authenticate initial handshakes and prevent port scanning or denial-of-service against the VPN port.
- **`~/vpn-profiles/*.ovpn`**: Generated OpenVPN client bundle configurations containing inline certificates and unencrypted client private keys.
- **`/etc/openvpn/server/`**: Live OpenVPN server certificates, Diffie-Hellman parameters, and server private keys (`server.key`).
- **`/etc/cloudflared/token`**: Cloudflare Tunnel authentication credential allowing the local daemon to establish the tunnel to `api.themirrage.me`.

---

## 3. Security Practices and Controls

### Certificate Authority and PKI Protection

- The Easy-RSA CA private key (`~/openvpn-ca/pki/private/ca.key`) is encrypted on disk with a strong passphrase.
- The backend production provisioning system (`backend/app/services/vpn_provisioner.py`) reads the passphrase from `/etc/mirrage/vpn-ca-passphrase` (restricted permissions: `root:admin 640`).
- Passphrases are passed non-interactively via the `EASYRSA_PASSIN` environment variable directly to the subprocess (`shell=False`, explicit arg list) and removed from the temporary environment mapping after subprocess completion; Python does not guarantee memory erasure.
- Passphrases are NEVER passed via command-line arguments (which would be visible in `ps`/process tables) and NEVER written to logs, database records, API responses, or generated `.ovpn` files.
- PKI subprocess output is withheld from exceptions and responses; failures expose generic messages.
- Targeted administrator revocation commits a durable deny, closes sessions, uses Easy-RSA `revoke`/`gen-crl`, publishes a validated CRL through a narrow root helper, and disconnects the selected client. Retry and CRL expiry maintenance are durable. See [VPN revocation](vpn-revocation.md) for the source implementation, installation requirements and pending live acceptance checks.

### Secret Key Complexity Enforcement

- Production configurations enforce strict validation on `SECRET_KEY` during backend startup.
- In `backend/app/core/config.py`, the validator verifies:
  - Minimum length of 32 characters.
  - Absence of common insecure terms (such as `mirrage`, `test`, `changeme`, `secret`).
- If validation fails when `ENVIRONMENT=production`, the application raises a configuration error and refuses to start.

### File Permissions on Secret Artifacts

- All generated `.ovpn` configuration bundles written to `~/vpn-profiles/` are immediately restricted to octal mode `600` (`-rw-------`), ensuring only the owning user can read or modify the file.
- The Cloudflare tunnel token at `/etc/cloudflared/token` is owned by `root:root` with permissions set to `600`.
- Server private keys in `/etc/openvpn/server/` are restricted to root read-only access.

### Pod Isolation and NetworkPolicy Enforcement

See [player-isolation.md](player-isolation.md) for the implementation, required
maintenance rollout, privileges and release acceptance tests. This is an IPv4,
single-node design; templates alone do not prove that the live server enforces it.

- OpenVPN binds each authenticated certificate to a reserved address through CCDs
  and a learn-address hook. There is no dynamic pool or direct client-to-client path.
- A namespace default-deny policy is supplemented by one owner `/32` session policy
  permitting TCP 22 (CTF SSH), 80 (CTF web), and 2222 (Mirage SSH).
- Pod-initiated connections are allowed only to the owner's configured callback
  ports (default TCP 4444). DNS and internet egress are denied by default.
- A separate root-owned gateway guard enforces expiring VPN/pod address pairs,
  protects host services, denies peer access and blocks IPv6 from the player/pod
  interfaces. Correct routing, bridge filtering and CNI enforcement must be tested.
- Target containers drop all capabilities and add back the limited set required
  by SSH/cron and the intended exercise, including SETUID/SETGID and DAC_OVERRIDE.
  They run root services and intentionally permit an in-container root solve;
  seccomp, disabled privilege escalation and absent service-account tokens remain.
- Revocation precedes pod deletion/IP release; failed cleanup retains a slot and
  is retried. Kubernetes policies do not by themselves protect node-local services.

### Public Exposure Avoidance for CTF Environments

- The CTF environment and Mirage honeypot containers are never bound to public host ports.
- Neither container is exposed via Nginx, Cloudflare Tunnel, or AWS security group ingress.
- Access requires both an active OpenVPN connection authenticated with client PKI credentials and valid IP routing into the Kubernetes overlay network.

### OTP Authentication

- Email OTP verification is the only way to sign in or create an account.
- Password login, password registration, and development login routes are unavailable in every environment (HTTP 404).
- Codes expire, are stored as HMAC hashes, and have attempt limits. Resends enforce cooldown and rate limits.
- Issuance, resends and verification share a database lock for the normalized email. Conditional SQL updates enforce single consumption and bounded attempt counting across workers. See [OTP atomicity](otp-atomicity.md) for validation, rollout requirements and remaining abuse controls.
- Database-backed IP request limits and global hourly/daily issuance budgets apply across workers. Proxy identity is accepted only from explicitly trusted immediate peers; see [OTP abuse controls](otp-abuse-controls.md) for required proxy configuration and pending live acceptance.
- Deactivated accounts cannot obtain tokens through OTP or use existing tokens.
- Production validates supported email configuration; provider failures/timeouts produce generic 503s. Admin-only acceptance health contains no recipients, OTPs or provider bodies. See [email readiness](email-readiness.md) for limits and pending inbox acceptance.
- Existing database password columns are retained for compatibility but are not used for authentication.

### Git Exclusion Verification

The root `.gitignore` enforces exclusion patterns covering all secret types:
- `.env` and `.env.*` (with explicit exception only for `.env.example`).
- Private key files: `*.key`, `*.pem`.
- Client configuration files: `*.ovpn`.
- PKI private directories: `pki/private/`, `openvpn-ca/pki/private/`.
- SQLite database binaries: `*.db`, `*.sqlite`, `*.sqlite3`.

---

## 4. Backup and Disaster Recovery Guidance

| Component | Storage Location | Recovery Strategy | Priority |
| :--- | :--- | :--- | :--- |
| **Easy-RSA CA & PKI** | `~/openvpn-ca/` (EC2) | **Critical**: The CA private key is irreplaceable. If lost, all issued client certificates become invalid and the entire PKI must be rebuilt. Create an encrypted, offline backup (e.g. GPG-encrypted archive stored in an AWS S3 bucket with Object Lock or secure offline vault). | High |
| **RDS PostgreSQL Database** | AWS RDS (AWS Managed) | Automated daily snapshots managed by AWS RDS, combined with point-in-time recovery (PITR) with a retention period of 7 to 30 days. | High |
| **Cloudflare Tunnel Token** | `/etc/cloudflared/token` | Low risk: If deleted or corrupted, a replacement token can be generated immediately within the Cloudflare Zero Trust dashboard without modifying client configuration. | Medium |
| **Server Configurations** | `/etc/nginx/`, `/etc/systemd/` | Fully reproducible from the repository templates in `infrastructure/nginx/` and `infrastructure/systemd/`. | Low |
| **VPN Client Profiles** | `~/vpn-profiles/` | Profiles can be regenerated on demand from Easy-RSA using `vpn_provisioner.py` as long as the CA and client private keys exist. | Low |
