# Live OTP reset diagnosis and recovery preparation

Observed on 2026-11-21. The user confirmed the issue is on the live website.
The frontend repair is implemented and reviewable. The user subsequently authorized
production recovery and confirmed that direct EC2 SSH works independently of the
CTF VPN. Recovery steps 1–4 below are complete: backups and migration rehearsal,
runtime preparation, live RDS migration to `20261120_0006`, nine existing real VPN
address reservations/CCDs and OpenVPN cutover. The guard, dedicated Kubernetes
identity and VPN controls are installed and checked. Step 5 also completed:
backend is running with healthy public API/database, private flags, imported
release images, encrypted Kubernetes Secrets and private proxy listeners. Frontend
publication, actual email delivery and real-player acceptance remain pending.
Earlier work explicitly remained code-only. However, systemd
was confirmed to execute the backend from this same working checkout. Pending
source changes therefore become live on service restart, even without a separate
publish action. This work should have been isolated from the live service checkout;
future development must use a separate checkout/release artifact.

## Confirmed causes

1. `PublicAuthRoute` used `isAuthLoading` to replace the entire form with a loading
   screen during request/resend/verify. This unmounted the page. A failed response
   then updated an unmounted component, discarding its email/code and error. The
   newly mounted form looked like a reset to email entry.
2. The live `mirrage-backend` unit is in an auto-restart loop. Sanitized journal
   checks confirmed the startup error:
   `K8S_SESSION_NODE_NAME must identify the node running the VPN/gateway guard`.
   No backend listener responded on loopback port 8000 during diagnosis. Nginx and
   cloudflared were active, but a working frontend cannot send OTP through a backend
   that never completes startup.

Additional read-only checks found deferred deployment prerequisites:

- `CTF_FLAGS_FILE` is unset.
- `/usr/sbin/nft` is absent.
- Root session gateway and VPN control helpers are absent.
- Their protected configuration files are absent.
- The configured database is unversioned; the source requires `20261120_0006`.
- The database has seven application tables. The schema matches the frozen baseline
  when its legacy `users.email_verified DEFAULT false` is represented in memory.
  Strict adoption currently rejects that default difference. The in-memory check
  also used existing primary-key and native-enum validation; no DDL was executed.
- Email configuration passes the new syntax checks. This does not prove provider
  authorization or real delivery; no OTP was sent.

Public HTTPS probes from this executor returned 403. That does not establish what
the user's browser receives or independently diagnose Cloudflare. Local listener
and service-state evidence establishes the backend outage without that inference.
Journal output was classified without printing raw log lines, keys, addresses or
OTPs. Database reads were limited to revision/schema metadata; account rows and
stored profile contents were not inspected.

## Frontend repair

`isAuthInitializing` now represents only the initial stored-token check. Route
guards wait on that flag. `isAuthLoading` remains the request/button busy state,
so starting an OTP action no longer removes the form. Errors retain the email/code
and become visible. OTP success/error messages have appropriate status/alert roles.
The authenticated public-route redirect also honors the original requested page,
preventing it from competing with successful verification and forcing `/dashboard`.

Playwright tests mock every backend API, including post-login polling. They cover:

- Failed email request: email retained and backend error displayed.
- Successful request: code-entry screen and recipient notice.
- Invalid code: error and typed code retained.
- Failed resend: code retained and Retry-After countdown respected.
- Successful verification: return to the requested protected page.
- Successful resend: old code cleared and new cooldown shown.
- Stored-token startup: protected content waits for token validation.

Run from `frontend` on a development machine with browser dependencies:

```bash
npm ci
npx playwright install chromium
npm run test:auth
npm run lint
npm run build
```

The test server binds only to loopback port 4189 and overrides the API base so
calls are intercepted. Playwright output is ignored by Git. On this minimal EC2
host, browser binaries, runtime libraries and fonts were downloaded/extracted only
under `/tmp/mirrage-auth-*`; no system packages were installed. Those temporary
directories may disappear. The test does not require or send a real OTP.

## Authorized production recovery — maintenance sequence

This is a coordinated rollout, not a single missing-setting edit. Review these
steps with [database migrations](database-migrations.md),
[player isolation](player-isolation.md), [VPN revocation](vpn-revocation.md),
[OTP abuse controls](otp-abuse-controls.md) and [email readiness](email-readiness.md).

1. Agree the maintenance window and recovery access independent of the player
   VPN. Keep new registration/provisioning gated, record the existing release and
   configurations, and take verified database/encrypted PKI backups. Drain player
   sessions before VPN/firewall changes. Do not merely switch production to mocks
   or disable safety checks to get a listener running.
2. Rehearse the actual legacy database on a restored copy. The proposed narrow
   baseline alignment is removal of the known false server default on
   `users.email_verified`, after confirming all writers supply the intended value
   and the remainder still matches the frozen baseline. ORM user creation already
   supplies this field. Proposed DDL, **not executed**:

   ```sql
   ALTER TABLE users ALTER COLUMN email_verified DROP DEFAULT;
   ```

   Recheck exact schema parity, run checked `adopt`, then upgrade to `0006` and
   verify. Do not blind-stamp a mismatching schema. No account rows need to change
   for that default alignment, but startup data initialization also hashes/redacts
   historical flag material, so preserve the pre-change backup and review that
   irreversible behavior before starting the new app.
3. Install/configure the real gateway guard, nftables prerequisites, narrow root
   helpers, sudoers and OpenVPN/CCD changes using the existing runbooks. Configure
   the exact gateway node and dedicated controller identity. Preserve certificate
   identities and perform the reviewed VPN address migration; restart OpenVPN
   only inside the approved maintenance window.
4. Provision the private shared-flag JSON outside source/build layers and set
   `CTF_FLAGS_FILE` with the approved web/user/root values. Keep backend verifier
   and target Secret contents consistent. Do not print those values into the
   handoff, commands or logs. Verify helper, flag, email and migration readiness
   before restarting the backend.
5. Apply the matching loopback-only proxy/header/Uvicorn configuration and restart
   the backend. Check the real listener, public API, admin health and cleanup.
   Preserve an independent recovery path; VPN changes can disconnect players.
6. Publish the reviewed frontend artifact through the existing frontend deployment
   pipeline. Do not push the entire dirty working tree merely to deploy this fix.
   Changes from earlier checklist tasks are still uncommitted and need review.
7. Have the user retry with a mailbox they control. Verify actual OTP receipt,
   code entry, replay refusal and resend. Complete the two-real-player isolation
   test and clean CTF reference solve before unrestricted publishing.

None of the live alignment, adoption, migrations, helper installation, private
configuration, service/VPN restart or frontend publication steps above was executed
during diagnosis. The user then authorized recovery; its first completed operation
is recorded below. Do not confuse that authorization with completed deployment.

Final UI validation on 2026-11-21: all seven browser regressions passed. Frontend
lint, TypeScript/production build and `git diff --check` passed. No live service
configuration, database schema/data, PKI or firewall changes were executed.

## Recovery step 1 completed — verified backups (2026-11-21 UTC)

Run identifier: `20261121T054957Z-0d8ca1`.

- Stopped `mirrage-backend` to end its startup failure/restart loop and prevent
  backend writes during recovery. It remains stopped intentionally. This is an
  explicit service-state change after the earlier read-only diagnosis.
- Created an RDS PostgreSQL 18.3 custom-format dump using the cached PostgreSQL 18
  image, with TLS required. Table counts and `pg_dump` used the same exported,
  repeatable-read database snapshot. No source schema or data was modified.
- Encrypted the dump with AES-256-GCM, authenticated/decrypted the saved artifact,
  and restored that decrypted artifact with `--exit-on-error --single-transaction`
  into a disposable PostgreSQL 18 container. All **seven tables** and their row
  counts matched the source snapshot. Restore omitted original ownership/grants;
  production-role permissions still need separate validation.
- The verification container had no network or published ports, a 0.5-CPU limit,
  a 512-MiB memory limit and temporary PostgreSQL storage. It was removed after
  verification; no second database remains running on EC2.
- Also saved encrypted archives of the configured Easy-RSA CA/PKI, OpenVPN,
  nginx/cloudflared/private configuration directories, backend environment/unit,
  existing Kubernetes credentials, and the tracked/untracked nonignored working
  source. Git status, HEAD and the prior backend service state were recorded.
  Archive catalogs and encryption round trips passed. PKI restoration itself was
  not performed against the live CA.
- Verified every saved artifact checksum, mode `0600`, key mode `0600`, and backup
  directories mode `0700`. Temporary plaintext working files were removed.
- Confirmed nginx, cloudflared, k3s and `openvpn-server@server` remain active.
  No VPN restart, firewall edit, migration, flag change or real OTP send occurred.

Protected artifacts, outside the repository:

```text
/home/admin/mirrage-recovery/backups/20261121T054957Z-0d8ca1/
  manifest.json
  database.dump.aesgcm
  database-counts.json.aesgcm
  host-config-and-pki.tar.gz.aesgcm
  working-source.tar.gz.aesgcm
  git-status.txt.aesgcm
  service-before.txt.aesgcm
/home/admin/mirrage-recovery/keys/20261121T054957Z-0d8ca1.key
```

The key's contents must stay private; no key, credentials, profiles, OTPs, flags or
account rows were printed. These backups currently exist **only on EC2**. Copy
the encrypted backup directory off-host and retain the key separately before
treating this as disaster recovery against instance/disk loss. Do not commit either
directory to Git or publish the decrypted contents.

The format is the ASCII header `MIRRAGE-BACKUP-v1\n`, a 12-byte nonce, then the
AES-GCM ciphertext/tag. The additional authenticated data is that header followed
by the original encrypted filename in UTF-8. The key file is base64-encoded 32-byte
key material. Keep artifact filenames unchanged when copying. To recover a dump
into a newly created protected working directory:

```bash
umask 077
mkdir -m 700 /tmp/mirrage-manual-restore
backend/.venv/bin/python backend/scripts/decrypt_recovery_backup.py \
  --key-file /home/admin/mirrage-recovery/keys/20261121T054957Z-0d8ca1.key \
  --encrypted-file /home/admin/mirrage-recovery/backups/20261121T054957Z-0d8ca1/database.dump.aesgcm \
  --output /tmp/mirrage-manual-restore/database.dump
```

The helper authenticates before writing, creates output with mode `0600`, and
refuses to overwrite existing files. Decryption does not perform a database
restore. Restore only to a separately verified destination; do not overwrite RDS
as an automatic rollback.

The next migration rehearsal is recorded as completed below. Continue
helper/VPN/proxy preparation from the runbooks before attempting backend startup.
Vercel is confirmed to deploy from GitHub; its production branch is still
unconfirmed, so frontend publication remains pending.

Capacity checkpoint: this EC2 has 2 vCPUs, 7.61 GiB RAM and approximately 6.8 GiB
free root disk. Five configured player pods require a combined 2.5 CPUs and
3.75 GiB memory before host/backend services. Separate requests are absent, so
Kubernetes normally derives requests from those limits; five pods cannot all fit
the current CPU allocation. The user chose backend recovery first. Do not treat
restored backend availability as five-player capacity or production acceptance.

## Recovery step 2 completed — migration rehearsal (2026-11-21 UTC)

Restored the authenticated step-1 backup into a new PostgreSQL 18 container with
network disabled, no published ports, a protected Unix socket, a 0.5-CPU limit,
512-MiB memory limit and temporary database storage. Migration subprocesses used
an explicit testing environment, nonexistent environment-file path and only the
copy's Unix-socket database URL; production configuration was not loaded.

Completed checks:

1. Confirmed the restored database was unversioned and all seven original table
   counts matched the saved snapshot. Strict adoption correctly rejected the
   original schema without changing its revision.
2. Compared the complete schema to frozen baseline `0001`, including primary keys
   and native enum labels. Its only mismatch was the already identified
   `users.email_verified DEFAULT false`.
3. **On the copy only**, ran
   `ALTER TABLE public.users ALTER COLUMN email_verified DROP DEFAULT`, then
   checked adoption. It adopted revision `20261120_0001` without a blind stamp.
4. Upgraded successfully through `20261120_0006`. Status reported `current`.
5. Verified the complete frozen head schema, passed Alembic's check against the
   current ORM models, and passed the backend's database startup revision check.
6. Repeated `upgrade` at head successfully. All seven original tables retained
   identical row counts and per-table row fingerprints before and after migration.
   No account/profile/OTP values or fingerprints were printed.
7. Removed the temporary container, socket directory and decrypted working files.
   Confirmed nginx, cloudflared, k3s and OpenVPN remain active. The backend remains
   deliberately stopped, and live RDS schema/data remain unchanged.

Sanitized report, mode `0600`, outside Git:

```text
/home/admin/mirrage-recovery/backups/20261121T054957Z-0d8ca1/migration-rehearsal-20261121T060220Z.json
```

This verifies the schema migration on the actual saved database contents using
PostgreSQL 18. It does not verify original RDS ownership/grants, full production
application startup, challenge seeding/redaction, real email, or player isolation.
Application seeding was intentionally not executed during this migration check.
The existing ORM supplies `email_verified` through its Python default or explicitly
on OTP verification; confirm any external database writers before removing the
server default on production.

Runtime preparation is now recorded in step 3 below. Private flags, matching proxy
configuration and coordinated RDS/VPN/backend cutover remain required. Do not
reopen unrestricted player access before live containment and reference-solve checks.

## Recovery step 3 completed — helpers and node preparation (2026-11-21 UTC)

Applied authorized live infrastructure changes with the backend stopped. Preflight
found no connected VPN clients and no Running/Pending player-session pods. Terminal
test/player pods and the unrelated Pending `ssh-diag-test` were not deleted.

- Installed Debian nftables 1.1.3. General `nftables.service` stays disabled; the
  dedicated `mirrage-player-guard` service is enabled and active. It manages only
  `inet mirrage_player_guard`, preserving direct EC2 SSH through the host interface.
- Installed root-owned session/VPN helpers, hook, protected configurations,
  restricted sudoers (validated with visudo), guard sysctls and unit dependencies.
  The backend account's actual production gateway and VPN adapters pass checks.
- Set the existing node `ip-172-31-21-145`, `tun0`, `cni0`, VPN `10.8.0.0/24`
  and cluster pod CIDR `10.42.0.0/16` in the protected backend environment. The
  node's currently allocated pod CIDR is `10.42.0.0/24`. Backend and guard match.
- Issued a dedicated `mirrage-backend` client certificate, with no administrator
  organization, and installed the reviewed controller RBAC. Kubeconfig is
  `/etc/mirrage/backend-controller.yaml`, root:admin `0640`. Namespace pod/secret
  access is allowed; node listing and cluster-role-binding creation are denied.
  Certificate expires **2027-11-21 06:03:19 UTC**; rotate before expiry.
- Updated `isolate-player-sessions` in place to namespace default deny. The
  replacement keeps the existing name; no policy deletion is needed. The real
  backend's network-boundary validation passes using its dedicated identity.
- OpenVPN drops privileges to `nobody:nogroup`. CCD directory is admin:nogroup
  `2750`; the actual hook successfully read a temporary `0640` test CCD as nobody.
  The test was removed. Existing user reservations are not yet created.
- The legacy signed CRL lacked a sequence number. Added
  `crlnumber = $dir/crlnumber` **after** the existing `dir` definition in
  `/home/admin/openvpn-ca/openssl-easyrsa.cnf`, initialized the legacy counter,
  and generated a numbered CRL as admin under the application's PKI lock. Compared
  its revoked serial set with the encrypted original backup: all prior revocations
  remain. Published with the verified helper to `/etc/openvpn/server/crl.pem`;
  actual backend VPN-helper health passes. Certificates/private keys are preserved.
  Future generations must preserve the sequence counter and configuration.
- Installed OpenVPN guard/management unit drop-ins and staged the reviewed server
  configuration at `/etc/mirrage/openvpn-server.pending.conf` (root `0600`), keeping
  `user nobody/group nogroup`. It has **not** replaced the running configuration.
  Management socket, exclusive CCD assignment and anti-spoofing hook activation
  require a later coordinated restart after RDS migration/reservations.

The existing protected backup run directory contains an additional authenticated
encrypted pre-install host/firewall archive. The original broad policy snapshot
is `network-policy-before-20261121T061010Z.json.aesgcm`; later snapshots already
contain default deny. Successful completion report:
`runtime-preparation-completed-20261121T061119Z.json`.
Earlier partial reports are retained. Initial CRL generation needed its configuration
variable order corrected. An unnecessary policy deletion was prevented by its
UID/version precondition after apply had updated the object; no policy was deleted.
Final configuration, production helper adapters, controller permissions, namespace
boundary and CCD permissions all passed. No real OTP or player session was created.

Final services: backend inactive intentionally; guard enabled/active; OpenVPN,
nginx, cloudflared and k3s active. RDS remains unchanged. Next: confirm external
database-writer/default assumptions, apply rehearsed RDS alignment/adoption/upgrade,
prepare existing real-profile reservations/CCDs, activate the staged OpenVPN config,
and verify management/CRL/CCD enforcement. Supply private flags and matching
images/proxy settings before starting the backend. Frontend publication and real
mailbox/two-player containment acceptance remain pending.

## Recovery step 4 completed — live RDS migration and VPN cutover (2026-11-21 UTC)

The user explicitly authorized this live migration/reservation/VPN-cutover step.
Preflight reconfirmed backend stopped, guard active, zero connected VPN clients
and all staged certificate/key/DH/TLS-crypt/CRL paths present.

- Observed no other database client connections and no custom public-table
  triggers. Repository user creation supplies `email_verified` explicitly or via
  its ORM default. Rechecked the complete legacy schema under write locks.
- In **one transaction**, acquired the migration advisory lock and access-exclusive
  locks on all seven original tables, removed only the known legacy false server
  default, checked/adopted baseline `0001` and upgraded through `0006`. Lock and
  statement timeouts bounded the operation. No blind stamp was used.
- Verified the exact head schema, startup revision gate and original table row
  counts/fingerprints before commit. All original rows were preserved by the
  schema migration. Rechecked committed schema/revision; production CLI reports
  `current` at `20261120_0006`. Application startup/seeding/redaction was not run.
- Stopped OpenVPN with zero clients. Verified eligible existing certificates
  against the CA and installed CRL, then ran offline reservation preparation as
  backend user admin. **Nine** active real profiles received stable reservations
  and private CCDs; certificate names and downloadable profile contents remained
  identical. Assigned addresses match database reservations and CCD contents.
- Verified all nine CCDs remain admin-owned `0640` in the setgid admin:nogroup
  directory. The hook as nobody accepts each reserved address and rejects a
  mismatching address. Backend can read the restarted VPN's status file.
- Saved the exact old server configuration as another authenticated encrypted
  artifact. Activated `/etc/mirrage/openvpn-server.pending.conf` at the real
  `/etc/openvpn/server/server.conf`, then successfully restarted OpenVPN.
- Verified the daemon runs as nobody and the live configuration uses `nopool`,
  exclusive CCDs, the learn-address hook, DCO disabled and the installed numbered
  CRL. Dynamic-pool, duplicate-CN and client-to-client directives are absent.
- Verified the real management socket responds to `status 2`. Its parent is
  root-owned `0750`; the socket is root-owned **0600**, with unprivileged access
  denied. OpenVPN created it as 0777 initially despite the protected parent/root
  peer checks. Added and tested persistent
  `ExecStartPost=/usr/bin/chmod 0600 /run/openvpn/server.mgmt` in its unit drop-in;
  a second restart confirmed enforcement. Updated the repository example too.

Protected sanitized reports in the existing backup run directory:

```text
live-migration-20261121T061650Z.json
vpn-cutover-verified-20261121T062013Z.json
```

The earlier `vpn-cutover-20261121T061846Z.json` records the initial socket-mode
verification failure, corrected before the successful final report. Both are
retained. No credentials, profile contents, account rows or row fingerprints were
printed. Existing profile/address changes are expected application-data changes
after the schema migration's preservation check.

Backend remains deliberately stopped; guard, OpenVPN, nginx, cloudflared and k3s
are active. Existing players retain their profile files and must reconnect for
their reserved addresses. No real player tunnel/packet acceptance test or OTP
email was performed. Restoring pre-rollout state requires coordinated DB/CCD/PKI
recovery; do not discard reservations or reset the CRL counter automatically.

Next: private shared flags, matching target images and loopback/proxy header
configuration, then backend start and health checks. Frontend publication, real
mailbox acceptance, two-player isolation/revocation and reference solve remain
release gates.

## Recovery step 5 completed — backend online (2026-11-21 UTC)

- Built `docker.io/library/mirrage-ctf:recovery-20261121` and
  `docker.io/library/mirrage-mirage:recovery-20261121`. The CTF release passed
  isolated runtime checks for services, flag content/ownership, stage separation,
  HTTP flag denial and intended web recovery using dummy test flags. Imported both
  releases into K3s containerd and configured the backend to use those local tags.
- Found Kubernetes Secret encryption disabled. Followed the
  [official existing-cluster procedure](https://docs.k3s.io/cli/secrets-encrypt#enable-secrets-encryption-on-an-existing-cluster):
  saved an authenticated encrypted SQLite/token/config backup, enabled encryption,
  added `secrets-encryption: true` while preserving the existing K3s config, restarted,
  rotated/reencrypted, then restarted again. Status is Enabled, `reencrypt_finished`,
  hashes match. API/node and the player guard passed readiness checks. An early
  status probe ran before the encryption controller was ready; it was retried
  after the documented initialized state was observed.
- Verified current Secret versions have the encrypted AES-CBC prefix in the actual
  SQLite datastore. Saved a second authenticated encrypted SQLite/token/encryption
  config/state backup after completion. This verifies current stored versions;
  it does not promise erasure of old SQLite pages/historical backups. Never restore
  an encrypted datastore without its matching encryption configuration and token.
- Created three distinct high-entropy shared flags at
  `/home/admin/.config/mirrage/ctf-flags.json`, admin-owned `0600` in a `0700`
  directory outside Git. Generated without printing values; immediately saved
  `ctf-flags.json.aesgcm` in the protected backup run. Private backend configuration
  points to this file. The immutable Secret matches the same contents, and its
  actual stored datastore value was separately verified encrypted.
- Confirmed the token-managed tunnel's current route from sanitized configuration
  metadata: `api.themirrage.me -> http://127.0.0.1:80`. No tunnel token or raw logs
  were printed. No Cloudflare configuration change was required.
- Applied the reviewed Nginx template, explicit loopback proxy trust and backend
  unit override: one Uvicorn worker at `127.0.0.1:8000` with `--no-proxy-headers`.
  The override is `/etc/systemd/system/mirrage-backend.service.d/runtime.conf`.
  Nginx needed a full restart because reload retained its former wildcard listeners.
  Verified final listeners are only `127.0.0.1:80`, `[::1]:80`, `127.0.0.1:8000`.
- Automatic approval review initially rejected startup because of its historical
  flag redaction/backfill behavior. Read-only inspection found **zero historical
  submissions and zero correct solve pairs**. Added assertions for empty history
  and no other DB clients to the rollout preflight, then resubmitted with that
  evidence; review allowed execution. No historical submitted values were erased
  or solves backfilled. Startup synchronized the three legacy challenge verifiers
  to the explicitly configured private flag hashes.
- Backend completed startup. Confirmed all three DB verifiers match the private
  flags, all challenge verifiers are hash-only, and submission history remains
  empty. Observed zero backend restarts and zero error/traceback messages since
  startup. The normal session reconciliation and cleanup worker are now running.
- Verified direct DB health, origin health with a valid synthetic visitor header,
  and public `https://api.themirrage.me/api/v1/health/`: HTTP 200, database healthy.
  Missing or malformed visitor identities return HTTP 400 at the private origin.
- Email syntax/configuration is ready; operational status remains `not_checked`.
  No real OTP email was sent. Public health mode labels alone do not establish
  player isolation or mailbox delivery.

Final sanitized report is `backend-recovery-verified-20261121T063318Z.json` in the
existing protected backup directory. Also retain
`encryption-images-20261121T062754Z.json`, the encrypted
before/after K3s archives and backend pre-start archive. The earlier
`backend-start-20261121T063022Z.json` records the Nginx listener/header-check
failure before the full proxy restart corrected it.

All six services are active: backend, player guard, OpenVPN, nginx, cloudflared,
K3s. Backend recovery is complete; this is not unrestricted publication acceptance.
The frontend OTP fix still needs deployment. The user confirmed that Vercel's
production branch is **main**. Do not push the entire dirty checkout to publish it.
Real mailbox, two-player isolation/revocation, reference solve and capacity tests
remain pending. Backend still reads this working checkout: further source work
must use a separate checkout/release to avoid repeating the incident.

## Frontend publication prepared — user will push

Latest user instruction: **make the changes; the user will push them personally**.
Do not push, publish or continue requesting GitHub authentication. The prepared
commit and portable frontend-only patch below are ready for the user's deployment.
The connection diagnostics below are historical and no longer block this handoff.

The user confirmed `main` while backend recovery was being verified. Prepared a
fresh isolated production-branch checkout at
`/tmp/mirrage-frontend-main-20261121` (temporary path), from main commit
`1b733020b692ba6468968b6065c6c34f0607a799`. Created local branch
`codex/otp-frontend-recovery` and commit
`f41c82ea239ddad67ba723942a888332374c65a1`.

The commit includes only the OTP form/route fix, accessible notices, seven mocked
browser regressions, Playwright config/dependency and ignored test output. It
excludes backend changes and even the unrelated frontend flag-score corrections
present in the live working checkout. The isolated patch passed lint,
TypeScript/Vite build, whitespace checks and all **seven browser tests**. Tests
intercept every API call and send no email. Build JS asset: `index-_tiJ6pXm.js`.
The test/build reused the existing matching installed dependencies via an ignored
node_modules symlink; the committed lockfile includes the Playwright dependency.

Portable, non-secret patch saved in the repository:

```text
/home/admin/THE-MIRRAGE/docs/otp-frontend-main.patch
```

GitHub read access works over HTTPS. EC2's SSH fetch fails with public-key
authentication; the forwarded agent cannot be queried for an identity, no GitHub
CLI/token is configured, and no Git credential helper is configured. No push or
Vercel deployment occurred. GitHub integration was discovered and suggested;
subsequent checks confirmed it is **installed and enabled**, including its required
GitHub app dependency. However, no authenticated GitHub tools are exposed to this
turn yet, and EC2 Git credentials remain unusable. Account authorization completion
was asked of the user; they subsequently chose to push personally. Do not repeat
the authentication/installation request. When the user publishes, they should recheck
current remote main, publish this frontend-only commit using a normal fast-forward
update (never force push), then verify Vercel's deployment and the public OTP flow.

If publishing from a local authenticated clone instead, copy the patch and use a
clean current main checkout:

```bash
git switch main
git pull --ff-only origin main
git am /path/to/otp-frontend-main.patch
git push origin main
```

Stop and review conflicts if main changed; do not overwrite remote work. The
portable patch remains available if the temporary EC2 checkout disappears.
