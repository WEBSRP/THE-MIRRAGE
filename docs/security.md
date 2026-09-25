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
- Passphrases are passed non-interactively via the `EASYRSA_PASSIN` environment variable directly to the subprocess (`shell=False`, explicit arg list) and cleared from memory immediately upon subprocess completion.
- Passphrases are NEVER passed via command-line arguments (which would be visible in `ps`/process tables) and NEVER written to logs, database records, API responses, or generated `.ovpn` files.
- All subprocess errors are passed through `_sanitize_error()` to strip any potential passphrase or private key references before raising exceptions.
- Certificate revocation is managed via Easy-RSA `revoke` and `gen-crl`, updating `pki/index.txt` and generating updated CRLs (`pki/crl.pem`).

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

- Sandboxes are segregated inside the dedicated `mirrage-sessions` Kubernetes namespace.
- A strict `NetworkPolicy` (`infrastructure/kubernetes/network-policy.yaml`) isolates player pods:
  - **Ingress**: Only packets originating from the OpenVPN CIDR (`10.8.0.0/24`) destined for TCP port 22 (Mirage Honeypot) or TCP port 2222 (CTF Challenge) are accepted. All inter-pod communication and traffic from the host network are blocked.
  - **Egress**: Pod outbound connections are restricted solely to established sessions on `10.8.0.0/24` and DNS lookup via internal nameservers on port 53. Pods cannot pivot into host networks, cloud metadata endpoints (`169.254.169.254`), or the internet.
- Pod security contexts explicitly drop `ALL` Linux capabilities and disable privilege escalation (`allowPrivilegeEscalation: false`).

### Public Exposure Avoidance for CTF Environments

- The CTF environment and Mirage honeypot containers are never bound to public host ports.
- Neither container is exposed via Nginx, Cloudflare Tunnel, or AWS security group ingress.
- Access requires both an active OpenVPN connection authenticated with client PKI credentials and valid IP routing into the Kubernetes overlay network.

### Fail-Closed Authentication Guards

- The development test login route (`POST /api/v1/auth/dev-login`) allows developers to authenticate without credentials during local work.
- The endpoint implementation in `backend/app/api/v1/endpoints/auth.py` enforces a strict guard:
  ```python
  if settings.ENVIRONMENT != "development":
      raise MirrageException(
          status_code=status.HTTP_403_FORBIDDEN,
          detail="Development access is disabled in this environment.",
          code="DEV_ACCESS_FORBIDDEN"
      )
  ```
- Any invocation in `production`, `testing`, or unset environments immediately aborts and returns HTTP 403 Forbidden.

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
