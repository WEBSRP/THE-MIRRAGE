# One-day player VPN credentials

Policy confirmed by the user on 2026-11-21: each issued .ovpn profile lasts 24
hours from certificate issuance. Authenticated players may obtain a fresh profile
after expiry, and the existing nine long-lived profiles must also be replaced.
Never push Git or publish through Vercel for this change; the user publishes Git.

## Enforcement

- Easy-RSA receives an explicit `--days=1` for every new client certificate. Server
  and CA lifetimes remain unchanged. Every issuance has a new CN, private key and
  serial; old certificate files are not overwritten or reused.
- The profile's inline signed certificate is authoritative for issuance/expiry.
  Repeated downloads reuse an unexpired one-day profile and cannot extend its
  deadline. JSON profile/status responses expose `expires_at`; the file includes
  a human-readable expiry comment. Mock development profiles are not real VPN
  credentials and do not attest this security policy.
- Expired or legacy long-lived profiles are replaced through the production
  service. It retains the player's reserved IP, blocks/kicks the old CN, revokes
  its certificate and verifies/publishes the CRL before activating the new CCD.
  This does not create an account suspension. Permanent administrator deny records
  still prevent all issuance and renewal.
- PostgreSQL advisory/user/profile/reservation locks serialize independent API
  workers. Allocation is committed before certificate work so failures do not
  recycle an address. PKI operations retain their existing filesystem lock.
- The private CCD includes signed-certificate-derived issued/expiry timestamps
  and serial in a versioned comment. The existing address-learning hook ignores
  this comment and continues enforcing its one ifconfig-push assignment.
- New root-owned `client_connect.py` verifies the TLS-authenticated CN and serial
  against that CCD, rejects missing/expired/mismatched metadata, and writes a
  server-side per-client `session-timeout` for the remaining lifetime. Reconnecting
  cannot reset the issuance deadline. Active tunnel cutoff does not depend on the
  backend cleanup worker. Normal TLS certificate validation also rejects expired
  certificates independently. Server clock correctness remains required.

## Rollout requirements

Do not copy partially edited source into the current live checkout. Complete tests
and stage a separate release first. Keep backend writers stopped while replacing
profiles. Back up DB/PKI/CCD/configuration encrypted, record existing connections,
and preserve direct SSH independent of player VPN.

Install the new hook root-owned 0755 at
`/usr/local/lib/mirrage/client_connect.py`, and add exactly:

```text
client-connect "/usr/bin/python3 -I /usr/local/lib/mirrage/client_connect.py"
```

Preserve exclusive CCDs, nopool, CRL verification, address-learning hook, runtime
privilege dropping, root-only management socket and guard dependencies. Restart VPN with the new hook while keeping the backend stopped. Legacy CCDs
without expiry metadata are then rejected. Keep its protected management socket
available during replacement: targeted retirement needs it to verify disconnects.
Run the new offline `prepare_vpn_isolation.py --apply` as the backend account to
renew eligible existing profiles, then verify the running VPN and all bindings.
Verify all new certificates last one day, old serials appear in the CRL, existing
IP reservations remain unchanged, and old CCDs are absent. Existing players must
re-download/reimport their files. No admin-denied user may be migrated to access.

Then start the staged backend release using the existing production environment
and verify API health and expiry metadata. Do not claim a live rollout or replace
these profiles until deployment and verification are actually completed.

## Validation

Focused tests cover one-day signing, reuse without extension, legacy/expired
renewal, preserved IP addresses, manual-deny refusal, concurrent renewal across
PostgreSQL workers, and serial/deadline fail-closed checks.

The real OpenVPN test uses an ephemeral CA/client/server in a disposable network
namespace, no host ports or production key mounts. Its shortened trusted CCD
deadline exercises the actual per-client timer and reconnect rejection:

```bash
docker build -t mirrage-ctf:recovery-20261121 containers/ctf
docker build -t mirrage-vpn-expiry:check -f infrastructure/openvpn/expiry-test.Dockerfile .
docker run --rm --network none --memory 256m --cpus 0.5 \
  --cap-add NET_ADMIN --device /dev/net/tun \
  --mount type=bind,source="$PWD/infrastructure/openvpn",target=/checks,readonly \
  --entrypoint python3 mirrage-vpn-expiry:check /checks/check_expiry_runtime.py
```

References:
[OpenVPN session-timeout](https://openvpn.net/community-docs/community-articles/openvpn-2-6-manual/),
[TLS serial environment](https://build.openvpn.net/doxygen/ssl__verify_8c_source.html),
[Easy-RSA validity](https://github.com/OpenVPN/easy-rsa/blob/master/doc/EasyRSA-Advanced.md).


## Live deployment completed — 21 November 2026

User explicitly selected self-service renewal after login and replacement of all
nine legacy profiles. The feature is now deployed and verified:

- Nine profiles replaced with new certificate identities, serials and private keys.
  Each signed certificate has exactly 86400 seconds of validity. All old serials
  appear in the installed CRL; old CCDs were removed and the reserved IPs retained.
  Existing users must download/import new files. No administrator deny records
  were removed or created by this renewal migration.
- The installed client-connect hook runs under nobody and validates serial and
  absolute expiry. All nine live bindings passed the installed hook check; wrong
  serials were rejected. Repeated profile retrieval preserved certificate serial,
  bundle and expiry. Public API/database health is HTTP 200/healthy.
- Backend runs from an independent source AND virtual-environment snapshot at
  `/home/admin/mirrage-releases/vpn-expiry-20261121T071051Z`. Its systemd runtime
  override sets that WorkingDirectory/PYTHONPATH and uses `python -m uvicorn`.
  The protected production environment is now `/etc/mirrage/backend.env`
  (root:admin 0640), explicitly selected by ENV_FILE. Further repository edits
  do not change the running release. Backend, VPN, guard, nginx, cloudflared and
  k3s were all verified active. No Git push or Vercel publication was performed.
- Fresh encrypted DB/PKI/config backup was restored/verified before the cutover:
  `/home/admin/mirrage-recovery/backups/20261121T070832Z-aacd66/`, with key stored
  separately under `/home/admin/mirrage-recovery/keys/20261121T070832Z-aacd66.key`.
  Final sanitized report: `vpn-expiry-verified-20261121T071547Z.json` in that run.
  Existing flag backups remain in the earlier recovery run; keep both sets.
- Full isolated backend suite: **355 passed, 5 expected skips**. Final focused
  expiry checks: **8 passed**. A real OpenVPN client/server with an ephemeral CA
  in a separate network namespace connected successfully, was disconnected at a
  shortened trusted deadline, and could not reconnect afterward. No real user
  keys were used in that test.

Initial staging needed parent traversal permissions corrected. The first profile
replacement attempt found the VPN management socket unavailable while VPN was
stopped; the order was corrected before replacement completed. A final source
verification used an ambiguous Python import alias; checking via importlib
confirmed the deployed source/interpreter independently. Retain partial reports
alongside the successful report. No old credential was re-enabled as a workaround.

API JSON profile/status responses expose `expires_at`; current frontend code can
ignore that additional field. The expiry comment is included in every new .ovpn
bundle. Real two-player containment/reference-solve acceptance remains separate
from these expiry checks. Never restore old certificates/CRLs/counters or old
profile rows as an automatic rollback: the old credentials were intentionally
revoked and their users now need the newly issued files.
