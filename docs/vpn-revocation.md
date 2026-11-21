# Targeted VPN revocation

Live preparation on 2026-11-21 installed the helpers and numbered CRL generation;
actual helper health passes. OpenVPN management/CCD cutover and RDS migrations
subsequently completed; backend startup and real targeted-revocation acceptance
remain pending. See [live-otp-recovery.md](live-otp-recovery.md). Keep public registration gated until the
real two-client acceptance test below passes.

## Administrator API

Authenticated administrators can request `POST /api/v1/vpn/users/{user_id}/revoke`
and inspect `GET /api/v1/vpn/users/{user_id}/revocation`. The existing
`POST /api/v1/vpn/revoke` remains an administrator-only self-revocation alias.
There is no automatic certificate reissuance endpoint.

The request commits a durable deny record and removes the stored downloadable
profile before scheduling external work. New profile requests, downloads, session
starts, repairs and extensions reject revoked users. Public certificate PEM is
retained for identity proof; private keys/profile bundles are not copied into jobs.
The deny record survives profile/account deletion. Do not reuse a deleted account's
VPN address until its old certificate is demonstrably revoked and disconnected.

`202 pending` means the request was accepted, not that an existing tunnel is gone.
`200 completed` is returned on subsequent requests only after session cleanup,
certificate revocation, verified CRL publication and targeted disconnection succeed.
Responses include attempts and a generic error code, never subprocess diagnostics.
In mock mode, completion verifies the simulated lifecycle only.

The background worker closes the selected user's sessions, removes its CCD,
caches its public certificate before Easy-RSA can move it, disconnects its CN,
runs idempotent Easy-RSA `revoke`/`gen-crl`, publishes a verified CRL, and disconnects
again to cover reconnects racing publication. Other clients are not restarted.
Failures remain pending, with a durable retry schedule and expiring atomic worker
claims. An interrupted worker can be replaced after its lease expires. Pod/gateway
cleanup failure also prevents a completed result.

## Restricted root helper and PKI

`infrastructure/openvpn/vpn_control.py` accepts only block, publish, refresh and
health operations using fixed root-owned configuration. It does not accept a
shell command, arbitrary management command or caller-selected filesystem path.
It uses a protected root-owned Unix management socket; do not expose management
over TCP. Client names are validated before use as commands or CCD basenames.

CRL publication verifies the configured CA signature, validity interval, CRL
number and retention of every installed revoked serial. A targeted publication
also proves the selected cached certificate belongs to that CA/CN and appears
in the candidate CRL. Replacement is atomic. A stale, differently signed,
incomplete or rolled-back CRL leaves the installed file unchanged. Existing
revocations must therefore stay in future CRLs, including expired certificates.
Do not prune the Easy-RSA index without an explicit migration of this policy.

Easy-RSA operations share a process-independent filesystem lock and have bounded
timeouts. All other PKI writers, including manual maintenance, must respect
`.mirrage-pki.lock` or run while the backend is stopped. The backend already has
CA signing access; this helper does not grant additional access to the CA key.
Subprocess output is discarded on error. Python cannot guarantee erasure of secret
strings from memory; the passphrase is kept out of arguments, responses and logs.

The worker checks installed CRL health hourly and regenerates/publishes it when
within seven days of expiry, retrying failures every 30 seconds by default.
`GET /api/v1/vpn/crl-health` exposes the last check, expiry and generic error to
administrators. Configure external alerting for failed/stale checks and pending
revocations; database health records alone do not notify operators.

## Rollout preparation

1. Back up the database and encrypted PKI. Review configuration with a maintenance
   window and a recovery connection independent of the VPN.
2. Install `vpn_control.py` as root-owned mode 0755
   `/usr/local/sbin/mirrage-vpn-control`. Install a root-owned, non-writable
   `/etc/mirrage/vpn-control.json` based on `vpn-control.example.json`.
   Keep its CA trust anchor under protected `/etc/openvpn/server`, and point
   `crl_source`/`issued_directory` at the actual Easy-RSA public output paths.
   The helper's `/var/lib/mirrage/vpn-control` state is root-only and persistent.
3. Review/install the narrow `mirrage-vpn-control.sudoers.example` through
   `visudo`; use the actual backend service account. Do not grant arbitrary sudo.
   Check service restrictions permit this existing sudo-helper model.
4. Add the Unix management directives from `server.conf.example` and the runtime
   directory settings in `openvpn-management.conf.example`, preserving existing
   unit settings. Keep `crl-verify` enabled and `ccd-exclusive` enforced. The
   protected socket parent must be root-owned and not group/world writable.
   A coordinated OpenVPN restart is required for configuration changes.
5. Apply the reviewed versioned migrations for `vpn_revocations` and
   `vpn_crl_maintenance` using [database-migrations.md](database-migrations.md).
   Startup verifies the migration revision and never creates missing tables.
   Never remove completed deny records during cleanup or rollback.
6. Configure `VPN_CONTROL_HELPER` and timing values from `backend/.env.example`.
   Ensure Easy-RSA's CRL lifetime exceeds the refresh margin. Perform an initial
   verified `refresh` and `health` with the installed helper before starting the
   production backend, whose startup checks helper health.

   Verify the Easy-RSA OpenSSL configuration enables `crlnumber` after defining
   its directory variable, and keeps the counter persistent. Some legacy setups
   generate unnumbered CRLs, which this helper rejects. When migrating one, retain
   every previously revoked serial and verify the new signed CRL against the CA;
   never reset an existing numbered counter or discard revocations.

The initial implementation was code-only. The later partial live rollout is
recorded in the recovery notes; remaining steps must not be treated as deployed.

## Validation and acceptance

Backend tests use mock services and disposable databases. Crypto tests generate
ephemeral certificates and use real OpenSSL to test invalid updates and rollback.
Run the full suite, including the independent-worker PostgreSQL cases, from the
repository root using `python3 backend/scripts/check_backend_postgres.py`.
It requires Docker, `backend/.venv` and the `postgres:16-alpine` image, creates a
temporary database with no network or published ports, and removes its container
and socket files afterward. It supplies explicit test settings and ignores the
production environment file.
The root helper integration test runs only inside a disposable container, using
an ephemeral CA and simulated management socket:

```bash
docker run --rm --network none \
  --mount type=bind,source="$PWD/infrastructure/openvpn",target=/checks,readonly \
  --entrypoint python3 mirrage-player-guard:check /checks/check_vpn_control_runtime.py
```

Build `mirrage-player-guard:check` using the instructions in `player-isolation.md`.
The test mounts no host PKI, socket, root state or OpenVPN configuration.

Before publication, connect two real disposable players A and B with separate
certificates and sessions. Revoke A by its user ID. Confirm A's session/gateway
grant and CCD disappear, its tunnel disconnects, its existing profile cannot
reconnect and its API cannot obtain credentials/start/extend. Confirm B remains
connected and its session works. The job must report completed only after all
effects are confirmed. Repeat the request and confirm idempotency. Simulate a
publish/socket failure and backend restart; require pending status and eventual
retry completion. Exercise CRL refresh/expiry and alerting in staging. These
authenticated OpenVPN/CNI acceptance checks have not been run on the live server.

Validated on 2026-11-20: 172 backend tests passed with the PostgreSQL cases enabled;
the disposable root-helper integration passed. Compilation and whitespace checks
also passed. No production rollout was performed.

Explicit reissuance, full account suspension, orphan-resource sweeping, external
monitoring integration and safe administrative account deletion remain separate work.
