# MIRRAGE CTF audit and continuation handoff

Audit date: 2026-11-20 (UTC).

**Current recovery status (2026-11-21):** the user authorized EC2 recovery and
confirmed direct SSH independent of the CTF VPN. `mirrage-backend` is now running
with healthy public API/database. Encrypted RDS/VPN/configuration/source
backups were saved outside this repository; the saved PostgreSQL 18 dump restored
successfully in a network-isolated temporary container, with all seven table
counts matching the same source snapshot. The container and plaintext staging
files were removed. RDS is migrated to `0006`; private flags, release images,
encrypted Kubernetes Secrets and loopback-only proxy settings are active.
All six services are active. See completed recovery steps,
artifact/key locations and decryption instructions in
[live-otp-recovery.md](live-otp-recovery.md). Off-host backup copying is pending.
Recovery step 2 also passed: a fresh isolated restore rejected the original
default mismatch as expected; after removing only that default on the copy,
checked adoption selected `0001` and upgrade reached `0006`. Frozen schema,
Alembic ORM comparison and the backend revision gate passed. Repeating upgrade
at head succeeded; all seven original table counts and row fingerprints were
unchanged. The temporary database and plaintext staging were removed. Live RDS
remains unmigrated and the backend remains stopped. Full application startup,
production-role grants and challenge seeding were not part of this rehearsal.
Step 3 preparation also completed: installed/enabled the dedicated firewall guard,
restricted session/VPN helpers, validated sudo rules, dedicated Kubernetes identity
and matching backend node settings. The existing namespace policy was updated in
place to default deny. Enabled numbered CRL generation, preserved all previous
revocations and passed actual helper/namespace checks. OpenVPN's runtime group can
read CCDs. Step 4 subsequently completed: live RDS atomically adopted/upgraded to
`0006`, preserving original rows; nine real profiles received stable reservations
and CCDs without changing certificate names or profile contents. OpenVPN now runs
the prepared exclusive-CCD/CRL/hook configuration. Its root-only management socket
permissions persist after restart and deny unprivileged access. Backend remains
stopped at that point; step 5 subsequently configured private flags/images/proxy,
enabled/re-encrypted Kubernetes Secrets and started the backend successfully.
Public API health is HTTP 200 with a healthy database, zero restarts and no startup
errors observed. There were zero historical flag submissions, so no submitted
values were redacted or solves backfilled; three challenge verifiers now match
private flags. See steps 3–5 of the recovery notes for exact deployment evidence.
The user confirmed Vercel production branch `main`. Frontend-only commit
`f41c82ea239ddad67ba723942a888332374c65a1` is prepared in an isolated checkout,
with seven browser tests, lint/build/checks passing. Portable patch is
`docs/otp-frontend-main.patch`. Publishing is blocked on GitHub write credentials;
no push/deployment occurred. GitHub integration is now confirmed installed/enabled,
but authenticated GitHub tools have not appeared in this turn; user was asked
whether account authorization finished. Do not repeat the installation request.
Latest instruction: the user will push personally. Do not push or request further
GitHub authentication; the tested frontend-only patch/commit are ready for them.
Real mailbox
and two-player/reference-solve acceptance remain pending. Further backend source
work must use an isolated checkout because the live unit still reads this repo.
The historical entries below precede these recovery actions.

Implementation update (2026-11-20): shared static flags are now configured through
a private JSON file, injected at target startup and verified by hashes. See
[shared-flags.md](shared-flags.md) for the current design, migration, deployment,
and validation details. The findings below describe the original audit snapshot;
F01/F04 and parts of F03/F07/F09/F10 have implementation changes in the working tree.
The user's confirmed design uses three distinct flags shared by all players;
per-player flags are not a requirement. No live services or production database
have been redeployed/migrated by this work.

Current implementation validation: **133 backend tests passed**, including two
concurrency cases against disposable PostgreSQL; frontend lint and production
build passed. A newly built CTF image passed runtime checks for matching flag
contents/ownership, cross-stage file isolation, direct HTTP denial, intended web
flag recovery, absent baked-in flags, and failure without a flags mount. A newly
built backend image passed startup and hash-only challenge initialization. The
earlier SQLite test hang was reproduced with a standalone query and isolated to
the execution sandbox; tests run outside it with explicit test-only settings pass.
Test containers were removed. Separately tagged test images remain cached.

Player-isolation implementation update (2026-11-20): see
[player-isolation.md](player-isolation.md). The working tree now includes stable
database VPN reservations, certificate CCDs and anti-spoofing hook, namespace
default-deny and owner `/32` policies, an expiring root gateway guard, and session
grant/revoke/renew/cleanup integration. Pods are pinned to the configured single
gateway node. Production refuses missing gateway configuration, mock VPN for real
sessions, broad additive policies and invalid controller kubeconfigs. It no longer
falls back to the node's admin kubeconfig. Failed cleanup retains a slot for retry.

Isolation validation: **149 backend tests passed**, including isolated PostgreSQL
allocation/solve/quota concurrency cases. Real nftables inside an isolated test
container passed ownership binding, automatic expiry, revoked-renewal rejection
and restart checks. Packet tests with two simulated players and two targets passed
owner access, cross-player/host/peer denial, owner-only callbacks and revocation.
The tests did not change production VPN/firewall/Kubernetes configuration.

The updated backend image also built as `mirrage-backend:player-isolation-check`.
An additional isolated image-startup recheck could not be confirmed after the tool
runtime reset; a follow-up Docker inspection returned a broken-pipe connection
error. This is not a backend test failure. Do not restart the host Docker daemon
as an automatic fix; inspect the test-image container and rerun the optional check
when the tool/daemon connection is available. The 149-test run and packet/helper
checks above completed successfully before that reset.

The next step is the reviewed maintenance rollout in player-isolation.md and its
two-real-client OpenVPN/CNI acceptance test. Root helpers, sudoers, sysctls, OpenVPN
configuration, CCD migration and node/kubeconfig settings have NOT been installed
on the live host. F02/F05 now have code changes but are not verified in production.
Targeted revocation/CRL distribution now have source fixes as described below;
namespace resource cleanup now has source fixes described in the orphan-cleanup update below. A full manual web-to-user-to-root solve is also required.

VPN-revocation implementation update (2026-11-20): the user explicitly chose
**continue checklist code fixes**, instead of EC2 rollout. See
[vpn-revocation.md](vpn-revocation.md). Source now includes an administrator-selected
player endpoint, permanent deny records and profile scrubbing, session cleanup,
leased durable retries, serialized Easy-RSA operations, verified atomic root CRL
publication, selected-CN management disconnects and durable CRL expiry maintenance.
A request returns pending until external effects and session cleanup are confirmed.
No automatic reissue or full account suspension was added. Completed deny records
must be retained; account/address reuse needs a separate safe administrative flow.

The root helper integration passed in a disposable container using a temporary CA,
real OpenSSL and a simulated Unix management socket. Client A was revoked/kicked,
client B remained trusted, missing selected-certificate revocation and CRL rollback
were rejected, and cached public certificates survived an issued-file move. This
is not a live authenticated OpenVPN test. Live configuration, services, firewall,
PKI and database were not changed. New helper/sudoers/configuration templates and
a two-real-client acceptance checklist are included in the revocation document.

Final revocation validation: **172 backend tests passed**, including all disposable
PostgreSQL allocation, solve, quota and independent revocation-worker checks.
The reproducible runner is `backend/scripts/check_backend_postgres.py`; it does
not inherit production settings, publishes no database ports and cleans up its
container/socket directory. Python compilation and `git diff --check` passed.
The source changes remain uncommitted alongside the earlier flag/isolation work.

Read-only EC2 preparation found the backend, OpenVPN, k3s, nginx and cloudflared
active, but the new gateway guard inactive and `/usr/sbin/nft` absent. Local
non-root kubectl cannot read the node admin kubeconfig. These observations reinforce
that source implementation is not production containment; no attempt was made to
change those live settings. Docker access was available again for disposable tests.

Next release work after the implementation updates below: controlled real-mailbox
acceptance/provider alerts, backup/restore rehearsal with production roles, a clean
reference solve, and staged deployment/isolation acceptance. The original
four release-gate lists below remain unchecked until deployment and acceptance;
use these implementation updates to distinguish source fixes from outstanding work.

Orphan-cleanup implementation update (2026-11-20): the user authorized the next
checklist item, abandoned environment cleanup. See [orphan-cleanup.md](orphan-cleanup.md).
The startup/periodic worker now inventories actual namespace pods, access policies
and persistent root gateway bindings independently of active database rows. It
preserves valid sessions and the existing initialization grace, rechecks database
state under creation/row locks, persists STOPPING before external effects, revokes
before deletion, and uses Kubernetes UID/resource-version deletion preconditions.
A pod receives a 30-second graceful shutdown; continued API presence keeps its
policy/source block and cleanup pending. Fresh inventories precede forgetting a
binding. Missing-row, policy-only and gateway-only leftovers are discoverable
without creating replacement DB rows. Ambiguous ownership is left for review.

The root helper gained a read-only `inventory` command and a matching narrow
sudoers entry. Existing namespace RBAC already permits the required operations.
No new database table or elevated cluster permission was added. The user has not
authorized EC2 deployment; no live workloads, database records, PKI or firewall
state were changed. Source changes remain uncommitted with the preceding work.

Orphan validation: **195 backend tests passed** with disposable PostgreSQL enabled.
After the final graceful-delete/fresh-binding review, **41 focused lifecycle tests
passed** against the final code, including independent PostgreSQL sweepers. The
isolated real-nftables helper test passed with revoked-binding inventory checks.
Compilation and `git diff --check` passed. No authenticated live Kubernetes/VPN
acceptance test has been run. The test runner now accepts optional pytest targets.

OTP atomicity implementation update (2026-11-20): the user authorized the next
checklist fix, safe concurrent OTP verification and resends. See
[otp-atomicity.md](otp-atomicity.md). Issuance, resend and verification now acquire
the same normalized-email PostgreSQL transaction lock; SQLite takes a writer lock
before reading. Verification refreshes/locks the latest row and uses a conditional
SQL increment/consume operation. Concurrent successful requests have one winner;
incorrect attempts cannot overwrite counts or exceed the budget. The final failed
attempt closes the code immediately. Consumed latest codes cannot expose older
unused records. Expiry is checked after lock acquisition.

OTP/account updates commit before VPN provisioning and JWT creation. Disabled
accounts consume correct codes without receiving a token. Issuance atomically
invalidates prior codes, avoids numeric reuse, and preserves the existing cooldown,
immediate resend allowance and per-email request budget. Email delivery occurs
outside the transaction lock. UTC handling now works with both PostgreSQL and
SQLite. No schema change or new external privilege was needed. All authentication
workers must be updated together; older verification workers lack this protocol.

OTP validation: **226 backend tests passed, 3 skipped**, including separate-service,
separate-connection SQLite/PostgreSQL races, both verify/resend lock orders, rate
budgets, expiry while waiting, stale ORM state, rollback, disabled accounts and VPN
failure after commit. The three skips are SQLite versions of PostgreSQL-only lock
checks; their PostgreSQL versions passed. Compilation and `git diff --check` passed.
Live EC2 services, database, email and PKI remain unchanged; changes are uncommitted.
Per-IP/global email abuse budgets, reliable mail delivery/alerts, migrations and
live deployment/acceptance remain publication work.

Versioned-migration implementation update (2026-11-20): the user authorized
Alembic setup, baseline/fix migrations and a backup/recovery procedure. See
[database-migrations.md](database-migrations.md). Four immutable revisions cover
the repository baseline, unique solve/quota tables, VPN reservations and durable
revocation/CRL tables. Startup now verifies the recorded Alembic head and never
creates missing tables. The explicit initialization script applies migrations
before seeding; normal application startup does not apply DDL.

The migration CLI provides status, checked adoption, upgrade and explicit-target
downgrade. Adoption matches a supported frozen schema before stamping and rejects
unknown/partial layouts, key/index/column drift and native enum-label drift.
Blind upgrade/stamp of a nonempty unversioned schema is blocked. Downgrades lock
target tables against writers and refuse to discard populated data, including
revocation tombstones, reservations, solves and quotas. There is no force-data-loss
switch. Legacy pre-baseline layouts require separate reviewed corrections on a
restored copy. Runtime and migration credentials/configuration remain operator-owned.

Migration validation: **258 backend tests passed, 4 skipped** in the full suite.
After adding future-revision template and concurrent-writer rollback checks,
**35 migration tests passed, 2 skipped** against disposable SQLite/PostgreSQL.
The skipped cases are SQLite variants of native PostgreSQL checks; PostgreSQL
versions passed. Empty-schema downgrade/re-upgrade, all supported legacy adoption
points, unchanged existing users, model/schema parity, drift rejection, startup
without automatic table creation and data-preserving rollback checks passed.

The separately tagged `mirrage-backend:migrations-check` image built successfully.
`backend/scripts/check_migration_image.py` passed packaged CLI status/upgrade,
unmigrated startup rejection, challenge seeding and mock app startup in a disposable
network-isolated container with a temporary DB and no host state mounted.
Compilation/whitespace checks passed. Live EC2 services, production database,
PKI/firewall and Kubernetes remain unchanged. No real production dump/restore or
maintenance rollout was performed. Source changes remain uncommitted with prior work.

OTP abuse-controls implementation update (2026-11-20): the user authorized shared
per-IP request limits, global email budgets and trusted proxy handling. See
[otp-abuse-controls.md](otp-abuse-controls.md). Request/resend endpoints share a
persistent IP allowance (default 10 per 600 seconds). IPv4-mapped addresses are
canonicalized and IPv6 addresses share a /64 bucket; only domain-separated HMAC
identities are stored. The configured duration participates in that identity so
changing window lengths cannot compare incompatible epoch counters. Default
global issuance budgets are 100/UTC hour and 500/UTC day. They are fixed windows,
not provider billing guarantees; failed provider sends are not refunded.

Database atomic upserts enforce budgets across workers/restarts. Both global
reservations and OTP issuance/invalidation commit or roll back together. An IP
request remains counted if later email/global checks reject it. Quota database
failure blocks sending; 429 includes Retry-After and unavailable identity/counters
returns generic 503. Stale IP buckets are cleaned in bounded batches, preserving
global counters and active expiry. Revision 20261120_0005 creates the new indexed
counter table; checked adoption recognizes the fifth snapshot, and populated
budget data cannot be dropped by downgrade. No historical snapshot was edited.

The Nginx example now binds only to loopback, trusts visitor identity only from
local cloudflared, rejects missing/malformed/list CF identities and overwrites its
own X-Mirrage-Client-IP header. The backend accepts exactly one literal IP only
from explicitly configured immediate proxy CIDRs, ignoring caller-supplied XFF,
CF and real-IP headers otherwise. Default trust is empty; production same-host
Nginx requires explicit loopback trust. Uvicorn examples/Docker command disable
proxy-header rewriting to retain the true socket peer. These templates/settings
have NOT been installed or reloaded on the live EC2 host.

Validation: **295 backend tests passed, 5 skipped** in the full suite. Following
final configurable-window and public API checks, **104 focused abuse/atomicity/
migration tests passed, 5 skipped**. Skips are SQLite variants of native PostgreSQL
checks whose PostgreSQL versions passed. Real Nginx in a disposable container
passed forged-header overwrite, IPv4/IPv6 handling and missing/malformed identity
rejection. The separately tagged mirrage-backend:otp-abuse-check image built and
passed packaged CLI migration/revision guard, mock startup and seeding checks.
Compilation and whitespace checks passed. No real email was sent; production DB,
VPN/PKI, Kubernetes workloads and running services were unchanged. All source
changes remain uncommitted with earlier fixes. Live tunnel propagation, production
role/backup recovery tests and release acceptance remain pending.

Email readiness implementation update (2026-11-20): the user authorized production
provider validation, bounded/sanitized dispatch failures and an admin-visible health
signal. See [email-readiness.md](email-readiness.md). Production startup now rejects
missing/unsupported provider configuration, invalid sender/reply addresses, unsafe
header values and missing API keys. Resend and SendGrid are supported; the SMTP
message-preparation no-op was removed and SMTP is explicitly unsupported. An
explicit EMAIL_FROM is required; default/legacy EMAIL_FROM_ADDRESS is not sufficient.

Provider requests use fixed HTTPS endpoints, no redirects/environment proxies,
network and total wall-clock timeouts, and no automatic retries. Resend requires
HTTP 200 with an acceptance ID; SendGrid requires HTTP 202. Timeout, server-side or
interrupted results can be unknown, not proof that no mail was sent. Provider
bodies/diagnostics, keys, recipients, OTPs and receipt IDs are not logged or copied
into operational health. Generic request/resend failures now return 503 instead
of falling through to success. Existing committed OTP and quota state is retained.
Explicit simulations cannot be reported as real acceptance outside test/dev modes.

Revision 20261120_0006 adds indexed email_delivery_attempts containing operational
metadata only. Dispatch intent commits before provider I/O; failed intent persistence
prevents sending. Unknown/failed finalization stays visible as pending, becoming an
unknown result after the timeout plus 30-second grace. Admin-only GET /api/v1/health/email
reports configuration, the current provider's recent 24-hour outcome counts and
safe latest metadata, with no-store and mailbox_delivery_confirmed=false. Records
survive workers/restarts and are pruned in bounded batches after default 7 days.
Provider acceptance does not confirm inbox delivery. External alerts, delivery
webhooks and a durable mail retry queue were not added.

Validation: **343 backend tests passed, 5 skipped** in the full suite. After final
request/resend fallback and live-acceptance guards, **179 focused provider/OTP/
abuse/migration tests passed, 5 skipped**. Skips are SQLite variants of PostgreSQL
cases whose PostgreSQL versions passed. Tests used HTTPX MockTransport or fake
providers, including rejections, bad receipts, redirects, network/wall timeouts,
cancellation, telemetry failures, admin authorization, privacy, retention,
concurrent accounting, schema adoption and populated downgrade refusal.

The separately tagged mirrage-backend:email-health-check image built and passed
packaged migration/revision guard, challenge seeding and mock app startup with a
temporary database. Compilation and whitespace checks passed. No real mail was
sent, no production config/keys were read for testing, and live EC2 database,
services, VPN/PKI, firewall and Kubernetes were unchanged. All source remains
uncommitted with prior fixes. Real mailbox acceptance with an operator-controlled
recipient and verified sender is still required before publishing.

Live OTP incident update (2026-11-21): the user reported that entering an email
returns to the email screen and confirmed this is the live website. See
[live-otp-recovery.md](live-otp-recovery.md) for the confirmed causes and proposed
production maintenance sequence. The frontend used the request busy flag as a
route-level loading guard, unmounting forms during request/resend/verify and
silently discarding errors and input. A separate boot-only isAuthInitializing
flag now gates routes; forms retain their state while action buttons are busy.
Auth success respects the originally requested protected route. OTP notices now
have status/alert roles. Playwright and seven fully mocked browser regression
cases were added. Lint, TypeScript/production build and whitespace checks passed.

Read-only live diagnosis found mirrage-backend auto-restarting with the exact
missing K8S_SESSION_NODE_NAME startup check; no loopback backend listener responded.
Nginx/cloudflared were running. Required root helpers/configs and nftables are
absent, CTF_FLAGS_FILE is unset, and the database is unversioned at seven tables.
Its schema matches baseline 0001 if the legacy false server default on
users.email_verified is represented in expected metadata. No default, row, revision
or other live setting was changed. Public HTTPS probes from the executor returned
403; do not assume that independently identifies the browser's edge response.

IMPORTANT correction to earlier 'not deployed' wording: systemd was confirmed to
run directly from this working checkout. Source edits can be loaded on service
restart even though no explicit deployment/restart command was issued. The earlier
backend work should have been isolated from that live service checkout. The
pending prerequisite rollout has therefore become a live availability blocker.
Do not disable checks/mocks or stamp a mismatching database to hide the problem.
Future development should use an isolated checkout and reviewed release artifacts.

The UI fix remains in the working tree and has not been published through the
frontend host. Actual live recovery requires the reviewed maintenance rollout:
backup/restore rehearsal, narrow legacy-default alignment if approved, checked
adoption/upgrades, private flags, real gateway/controller/root helper/CCD setup,
coordinated VPN/backend restart and frontend publication. Those live mutations
were not authorized/executed during this diagnosis; the user previously chose
code fixes over rollout. A real mailbox test and containment acceptance remain
required. Browser dependencies/libraries/fonts were extracted under /tmp only;
no system package installation or real OTP send was performed. All existing
uncommitted fixes were preserved.

## Start here

The user requested: understand the repository, analyze its CTF structure, identify flaws, and provide a checklist before publishing. The initial review is complete; shared-flag remediation is described in the update above. The user requested this Markdown handoff so work can continue on their local system after the EC2 session.

**Recommendation: do not open the live CTF to unrestricted players yet.** The main blockers are mismatched flags, missing player-specific network access controls, incomplete VPN revocation, and unreliable pod cleanup. A frontend demo and a secure, functional live CTF are different release milestones.

This is a repository review with limited local checks, not a live infrastructure penetration test. Do not assume checked-in templates match deployed configuration. Intentional command execution and privilege escalation inside a CTF target are part of the exercise; the platform must securely contain them.

## Repository checkpoint and environment

- Repository directory in this session: `/home/admin/THE-MIRRAGE`.
- Branch: `cloud`.
- HEAD at handoff creation: `77bae333d5d8056fed1e31d2923636adca0902c9`.
- The working tree was clean before creating this handoff. No source/configuration fixes were made during the audit.
- This handoff is a new, uncommitted file. It must be copied or committed/transferred to be available in a separate local checkout.
- Shell: Bash. Observed Python: 3.13.5. Observed Node: v22.23.2.
- Installed dependencies were available in `backend/.venv` and `frontend/node_modules`.
- No `AGENTS.md` was found during the review. Check again in the destination checkout before working.
- `AI_HANDOFF.md` already exists at the repository root and is ignored by Git. It was not read or modified in this audit; it may contain older context and should not override current code without verification.
- `migration/`, `ctf-design-local/`, and `frontend-old/` exist. They were not comprehensively audited. The primary implementation reviewed was `backend/`, `frontend/`, `containers/`, `infrastructure/`, and `docs/`.
- A local `mirrage.db` exists and is ignored. Its contents were not inspected. No production `.env`, private PKI, cloud credentials, or database contents were intentionally read.

On the local machine, compare `git rev-parse HEAD` and `git status --short` with this checkpoint. File line references may move after edits. Relative links in this document should work from a local clone.

## Architecture and relevant files

The documented production path is:

```text
Browser -> Vercel frontend
        -> Cloudflare Tunnel -> Nginx -> FastAPI -> PostgreSQL/RDS

Player workstation -> OpenVPN (10.8.0.0/24)
                   -> EC2 routing -> k3s pod network (10.42.0.0/16)
                   -> one player pod containing Mirage + CTF
```

The AWS/Vercel/Cloudflare deployment described above comes from repository documentation, not independent inspection of running services. Public domain names in the repo are `themirrage.me`, `www.themirrage.me`, and `api.themirrage.me`.

| Area | Files | Responsibility |
| --- | --- | --- |
| Overview | [README](../README.md), [architecture](architecture.md) | Intended system design and setup |
| API startup | [main.py](../backend/app/main.py) | Config validation, table creation, challenge seeding, cleanup worker |
| Configuration | [config.py](../backend/app/core/config.py), [.env.example](../backend/.env.example) | Environment, secrets, mode selection, limits |
| Authentication | [auth_service.py](../backend/app/services/auth_service.py), [auth routes](../backend/app/api/v1/endpoints/auth.py), [deps.py](../backend/app/api/deps.py) | Email OTP, JWT, active-user/admin checks |
| Email | [email_service.py](../backend/app/services/email_service.py) | Resend, SendGrid, incomplete SMTP |
| Challenges | [challenge_service.py](../backend/app/services/challenge_service.py), [challenge models](../backend/app/models/challenge.py) | Catalog, flag verification, submission records |
| Sessions | [session_service.py](../backend/app/services/session_service.py), [cleanup.py](../backend/app/workers/cleanup.py) | Slots, start, stop, extend, expiry, reconciliation |
| Kubernetes | [k8s_service.py](../backend/app/services/k8s_service.py) | Runtime pod generation and readiness |
| VPN | [vpn_service.py](../backend/app/services/vpn_service.py), [vpn_provisioner.py](../backend/app/services/vpn_provisioner.py), [VPN routes](../backend/app/api/v1/endpoints/vpn.py) | Profile persistence, Easy-RSA, telemetry, revoke |
| Challenge image | [CTF Dockerfile](../containers/ctf/Dockerfile), [forum backend](../containers/ctf/backend/server.py), [CTF Nginx](../containers/ctf/nginx/default) | Vulnerable exercise environment |
| Mirage image | [Mirage Dockerfile](../containers/mirage/Dockerfile) | Standard SSH server, presented as decoy |
| Network controls | [network-policy.yaml](../infrastructure/kubernetes/network-policy.yaml) | VPN ingress and sandbox egress rules |
| Frontend integration | [AppState.tsx](../frontend/src/state/AppState.tsx), [api.ts](../frontend/src/services/api.ts) | Real API calls mixed with simulated UI features |
| Deployment | [deployment guide](deployment.md), [security guide](security.md), [backend Compose](../backend/docker-compose.yml), [session Compose](../containers/docker-compose.yaml) | Templates and operational claims |

### Actual session services

The production pod generator returns the same pod IP for Mirage and CTF. The containers share the pod network namespace and loopback.

| Service | Actual port | Notes |
| --- | --- | --- |
| Mirage SSH | 2222 | Fixed `admin` account in image |
| CTF SSH | 22 | Fixed `player` account in image |
| CTF Nginx | 80 | Static website and forum reverse proxy |
| Forum backend | 127.0.0.1:5000 | Accessible over loopback from either container |

Several overview/security documents reverse the SSH ports. The Dockerfiles, runtime pod generator, and current session creation code agree on the ports above.

### Intended challenge path inferred from code

1. Discover the forum submission/preprocessor feature.
2. Supply a command through `processor`, `cmd`, or `command`; the backend executes it with `shell=True` as `www-data`.
3. Recover the web flag from `/var/www/html/flag.txt`.
4. Modify `/opt/mirrage/maintenance.sh`. It is owned by `player:maintenance`, mode 775, and both `player` and `www-data` belong to `maintenance`.
5. Cron executes that script as `player` every minute, providing the intended transition to the player account and `/home/player/flag.txt`.
6. Modify `/opt/mirrage/backup.conf`, owned by `player`.
7. Root cron runs `/usr/local/sbin/mirrage-backup`, which sources that writable configuration, providing the intended root transition and `/root/flag.txt`.

This is an inference from the images/scripts. It was not executed end to end in a running target. Do not remove these intentional vulnerabilities without first agreeing on the exercise design.

## Findings and suggested remediation

### F01 — Blocker: target flags and API flags do not match

- `containers/ctf/Dockerfile:63` creates three placeholder/test flags.
- `backend/app/services/challenge_service.py:29` seeds three different flags for `first-reflection` (100 points), `sub-stratum-breach` (250), and `oasis-evaporation` (300).
- A static comparison found **3 API flags, 3 image flags, 0 overlapping values**.
- The challenge descriptions reference perception/survey archives, network investigation, and forensic artifacts. These do not consistently map to the web/user/root image path.
- Seeding inserts missing challenges but does not update existing ones, so a deployed database could differ from the checked-in defaults.
- Fix: establish one authoritative catalog mapping each challenge/stage to deployed artifacts and its flag verifier. Prove every recovered flag is accepted in a fresh deployment. Plan migration for existing rows.

### F02 — Blocker: player ownership is absent at the network boundary

- `infrastructure/kubernetes/network-policy.yaml:13` allows the entire VPN CIDR to reach all selected pods on 22, 80, and 2222.
- Pod labels include user/session IDs, but no per-client ownership policy is created in the reviewed provisioner.
- Egress allows all protocols/ports toward the VPN CIDR, which can expose players' workstations to compromised targets.
- The DNS egress rule specifies port 53 without destination selectors, so it is not restricted to internal DNS as documentation claims.
- Fix: choose a reliable client-identity-to-session enforcement design (gateway/firewall rules or per-session policies with trustworthy VPN address assignment). Handle reconnects, address reuse, NAT, and session termination.
- Validate with two real clients. An API ownership check does not protect direct VPN traffic.
- Verify the live CNI actually enforces NetworkPolicy. Host/local-node traffic has special behavior; do not rely on policy alone for host isolation.

### F03 — Challenge integrity: the intended stages have shortcuts

- The web flag is inside the Nginx document root, owned by `www-data`, mode 600. Nginx's static route appears able to serve `/flag.txt` directly. File mode 600 does not protect it from a worker running as its owner.
- Fixed player SSH credentials are baked into the image. Anyone who knows them can skip the web-to-player path.
- Fix: move the web flag outside the served tree or deny direct access, and decide whether SSH credentials should be discovered, generated, or disabled. Add explicit checks for unintended alternate solve paths.
- These shortcuts were identified statically, not confirmed against a running image.

### F04 — Blocker for public source: accepted answers are in the repository

- API seed data and tests contain literal accepted flags. Docker image layers contain static target flags as well.
- Flag submission authenticates the user but does not require a session or bind the submitted answer to that user's environment.
- Fix: generate flags at deployment/session creation, inject them safely, and store a suitable verifier. Per-player/per-challenge flags reduce answer sharing. Keep production flag material out of public source/build layers.
- Requiring an active session is a product choice and does not by itself solve answer leakage.
- No real signing key or production credential exposure was established in this review. Do not confuse intended challenge passwords/flags with verified production secret leaks.

### F05 — Blocker: orphan pods and failed deletion are not reliably reconciled

- `k8s_service.py:205` creates a pod before waiting for readiness; on timeout it raises without returning the pod name.
- `session_service.py:388` stores the pod name only after provisioning returns and additional status validation succeeds.
- On a readiness timeout, the exception cleanup checks `new_session.pod_name`, which may still be empty even though the pod exists.
- Stop changes a session to `TERMINATED` and releases the slot despite deletion failure. Expiry similarly ignores a false deletion result.
- `STOPPING` is not among `ACTIVE_STATUSES`, so slot accounting can release capacity before deletion completes.
- Reconciliation starts from active database sessions; it does not list all labeled pods to find workloads with missing/terminal database records.
- Fix: persist deterministic resource identity before creation/waiting; implement retryable cleanup states; sweep actual cluster resources by labels; confirm disappearance before treating resources as released. Consider a pod-level lifetime deadline as an additional backstop.

### F06 — Blocker: VPN revocation, suspension, and reissuance need completion

- `vpn_provisioner.py:330` regenerates the CRL but only logs an instruction to copy it to the server.
- The checked-in server template has no `crl-verify` directive.
- Generated clients include `<tls-crypt>`, while the checked-in server template does not configure the matching key. A deployment based solely on these templates is inconsistent.
- `/vpn/revoke` is admin-only but revokes the calling admin's profile; it cannot select another player.
- Profile lookup filters out revoked rows, then attempts to create a replacement; the model makes `user_id` unique, and client names are deterministic. Reissue can conflict with an existing row/certificate.
- Disabling an API user is checked on API requests but does not itself disconnect or revoke their VPN certificate.
- Fix: explicit suspension/reissue workflow, targeted admin operations, CRL installation and expiry monitoring, server enforcement, and active-client disconnection. Test old certificates after revocation and after reconnect/renegotiation.
- VPN status path also differs between `.env.example` (`/var/log/openvpn/status.log`) and the server template (`/var/log/openvpn/openvpn-status.log`).
- Full `.ovpn` bundles, including client private keys, are stored as database text. Review DB access/backups and protection of this material; add no-store response headers for profile downloads.

### F07 — High: authentication and submissions need atomicity and abuse controls

- OTP issuance has an in-process lock and a PostgreSQL advisory transaction lock.
- OTP verification (`auth_service.py:112`) lacks equivalent row locking or atomic conditional consumption. Concurrent verification requests can race attempt increments and single-use behavior.
- Request throttling is per email; changing addresses bypasses that boundary. No per-IP/global email budget was found in the application or supplied Nginx template.
- Flag submissions have no visible application rate limit. Duplicate successful submissions are checked before insert without a database uniqueness invariant for a solve.
- Fix: atomic OTP attempt/consume operations; concurrency tests using separate transactions; IP/account/global abuse limits with trusted proxy address handling; one durable solve record per user/challenge.
- Successful solve race does not currently prove persistent score inflation: the code primarily records submissions and returns points, while UI totals are derived from solved challenges. Make future leaderboard scoring use unique solves.

### F08 — High: Mirage is an SSH decoy, not the documented telemetry system

- The image creates an ordinary SSH account/server. No command capture, fake filesystem/story artifacts, or activity ingestion pipeline was found in this image.
- It shares loopback with the CTF backend, so `127.0.0.1:5000` is reachable from Mirage too.
- Fix: define the deception objective, artifacts, discovery criteria, and telemetry implementation. If stronger network separation is required, separate pods/network namespaces are needed.

### F09 — High: deployment templates are inconsistent

- `containers/docker-compose.yaml:9` references `./mirrage`, which does not exist; the actual directory is `./mirage`.
- Its CTF bind mount targets `/opt/ctf` and can hide the backend copied into the image at `/opt/ctf/backend`.
- Compose advertises Mirage port 22, while the image listens on 2222.
- Backend Compose uses repository-root build context, but `backend/Dockerfile:17` copies `requirements.txt` from that context root; no root requirements file exists.
- Changing that build context alone also requires checking the `backend.app.main` import layout.
- Backend Compose publishes PostgreSQL 5432 and API 8000 on all host interfaces.
- The Nginx template listens on all IPv4/IPv6 interfaces despite documentation describing loopback-only binding. Actual public reachability depends on live host/cloud controls.
- `infrastructure/kubernetes/session-pod.yaml` is a legacy sample lacking the namespace, policy selector label, and runtime security controls of the current generator. Applying it does not put it under the supplied policy.
- Config/default/template image names differ and use mutable `latest` tags.
- Fix: choose and test a single supported deployment path, align images/ports/paths, restrict host exposure, and remove or clearly label unsafe legacy samples.

### F10 — Product correctness: several visible UI features are simulated

In `frontend/src/state/AppState.tsx`:

- `startSession` ignores the supplied challenge identifier; every challenge uses the same pod image.
- `appendTerminalOutput` fabricates an execution-success message for unsupported commands; it is not a remote shell.
- `updateUser` changes React state only and reports that settings were saved.
- The leaderboard always ranks the current player first and inserts fictional competitors.
- Challenge refresh pushes both slug and ID into `solvedChallengeIds`; displaying its length counts each solved challenge twice.
- Fix: replace these with supported backend behavior or clearly mark/remove them. A shared lab for multiple stages is valid if the UI explains it accurately.

### F11 — Operational readiness and documentation gaps

- SMTP (`email_service.py:236`) constructs a message and logs preparation but does not send it. Resend/SendGrid have actual HTTP implementations.
- Startup production checks do not validate a working email provider; OTP endpoints can return generic success while delivery fails. Keep anti-enumeration behavior, but add deployment checks and operational alerts.
- `Base.metadata.create_all` initializes tables but does not migrate existing schemas. Alembic is listed as a dependency, but no complete versioned migration workflow was found.
- Python requirements use lower bounds without a lock; frontend has a tracked package lock. No tracked GitHub CI workflow was found.
- Runtime pods have CPU/memory limits and useful security settings, but no ephemeral storage/PID budget or namespace quota was found in reviewed manifests.
- Backend uses synchronous Kubernetes client operations inside async functions; slow Kubernetes calls can block the event loop.
- The supplied systemd service runs as the general `admin` user without explicit hardening. The Kubernetes loader may use broad local/k3s credentials. Actual permissions were not inspected.
- Docs say capabilities are dropped, but runtime adds several back, including `DAC_OVERRIDE`, `SETUID`, and `SETGID`. Some may be necessary for the exercise/SSH; document the actual boundary and minimize what is possible.
- `.gitignore` allows `.env.production`, does not globally exclude `*.key`/`*.pem`, and does not match all claims in the security guide. Tracked frontend production configuration inspected here contains public URLs, not established secrets. A full Git-history secret scan remains outstanding.

## Checks performed and limits

| Check | Result |
| --- | --- |
| Frontend `npm run lint` | Passed |
| Frontend `npm run build` | Passed; TypeScript and Vite production output generated |
| Frontend `npm run test:visuals` | Passed; one Node test-file subtest reported |
| Backend `backend/tests_unit` | 2 passed in 0.74s |
| Backend `backend/tests` | Collected 118 tests; stalled at the first database fixture; overall unverified |
| Static flag comparison | 3 API flags, 3 image flags, 0 overlap |
| Git status after checks | Clean before adding this document |

The main suite was initially interrupted after hanging. A second run used a 35-second timeout and `faulthandler_timeout=12`. It reached `backend/tests/test_auth.py::test_get_me`; the trace showed an aiosqlite worker and the main event loop waiting during async fixture setup. It exited 124 on timeout. **The cause was not established**; do not claim that all 118 tests failed or that this proves a production backend failure. Investigate environment, SQLite/async fixture behavior, and installed dependency compatibility.

Existing concurrency tests use in-memory SQLite and, in at least one case, share one AsyncSession across concurrent requests. They do not establish correctness under separate PostgreSQL transactions/processes or real Kubernetes networking.

Not performed: Docker image builds, running the exploit chain, live cluster/EC2/RDS inspection, VPN connection/revocation tests, firewall validation, full history secret scan, dependency vulnerability scan, browser end-to-end testing, capacity/chaos testing, or backup restoration.

### Safe local test reproduction

Use a development checkout. The explicit environment below avoids loading the EC2 `.env`, selects mock infrastructure, and selects an in-memory database. Adjust virtualenv paths for your operating system.

```bash
# From repository root:
ENV_FILE=/tmp/mirrage-audit-no-env \
ENVIRONMENT=testing \
SECRET_KEY=audit-only-test-key-not-for-production-123456 \
OTP_HMAC_SECRET=audit-only-otp-key-not-for-production-123456 \
K8S_MODE=mock VPN_MODE=mock \
DATABASE_URL=sqlite+aiosqlite:///:memory: \
PYTHONPATH=. backend/.venv/bin/python -m pytest backend/tests_unit -q

# Diagnose the main suite with the same environment prefix:
# ... python -m pytest backend/tests -vv -s -o faulthandler_timeout=12

cd frontend
npm run lint
npm run build
npm run test:visuals
```

The example test keys above are deliberately non-production placeholders, not extracted credentials. The nonexistent `ENV_FILE` path should remain nonexistent; choose another nonexistent path if needed. The stalled run used GNU `timeout 35s`; use an equivalent on your local OS.

## Prioritized publication checklist

### Gate 1: solvable and fair exercise

- [ ] Agree whether this is one lab with web/user/root stages or three separate challenge environments.
- [ ] Unify catalog descriptions, artifacts, points, flags, and UI launch behavior.
- [ ] Generate private flags outside public source/build layers; bind them to appropriate player/challenge identity.
- [ ] Remove direct web flag exposure and unwanted SSH shortcuts.
- [ ] Complete each intended solve from a clean image and submit its recovered flag successfully.
- [ ] Check alternate solve paths and provide a private reference walkthrough.
- [ ] Define the Mirage decoy's actual purpose and observable artifacts.

### Gate 2: containment and access lifecycle

- [ ] Prove VPN client A cannot access player B's pod or workstation.
- [ ] Prove targets cannot reach host management, Kubernetes API, metadata, RDS, or unauthorized internet destinations.
- [ ] Restrict DNS to intended resolvers and sandbox-to-VPN traffic to required behavior.
- [ ] Confirm CNI policy enforcement and VPN source-IP/NAT behavior in the actual deployment.
- [ ] Persist resource identity and reconcile cluster resources independently of active DB rows.
- [ ] Test readiness timeout, failed deletion, API restart, expiry, and crash recovery with zero surviving unintended workloads.
- [ ] Implement suspension, targeted VPN revoke/reissue, CRL deployment, and active-client disconnection.
- [ ] Add quotas/storage/PID budgets and review least-privilege Kubernetes/backend credentials.

### Gate 3: platform correctness and abuse resistance

- [ ] Make OTP attempts and consumption atomic under concurrent transactions.
- [ ] Make solve recording unique/idempotent and enforce inactive-challenge behavior.
- [ ] Add OTP/submission/environment-creation abuse controls and email budgets.
- [ ] Implement persistent profile edits and a real leaderboard, or remove unsupported claims.
- [ ] Correct doubled solved counts and misleading terminal messages.
- [ ] Verify email delivery; implement SMTP or stop advertising support.
- [ ] Resolve the backend test stall and run meaningful PostgreSQL/infrastructure integration tests.

### Gate 4: reproducible deployment and operations

- [ ] Fix build contexts, bind mounts, images, service ports, status-log paths, CORS values, and host bindings.
- [ ] Keep mocks disabled in production and validate required settings at startup/deployment.
- [ ] Pin releases/images and establish repeatable Python dependency resolution.
- [ ] Establish versioned DB migrations and a rollback procedure.
- [ ] Test restoration of DB and encrypted PKI backups.
- [ ] Scan full Git history and release artifacts for private keys, credentials, profiles, and production answers.
- [ ] Correct security docs to match actual controls; label/remove obsolete samples.
- [ ] Monitor provisioning latency, orphan pods, cleanup failures, capacity, email failures, and CRL expiry.
- [ ] Publish permitted targets, scope/rules, telemetry retention, support, and accurate VPN instructions.
- [ ] Run an invited pilot with a strict capacity limit before unrestricted registration.

## Recommended next work session

1. Read this handoff and the current code; compare the Git checkpoint and inspect any new instructions.
2. Resolve challenge/catalog intent with the user before changing the exercise progression.
3. Address F01/F03/F04 together so the lab is both solvable and resistant to source-answer shortcuts.
4. Address F02/F05/F06 before any public live-player trial.
5. Add focused integration checks for actual failure modes, then complete the remaining release gates.

The user subsequently authorized flag, isolation and revocation code fixes, and explicitly chose checklist code work over EC2 rollout. Deployment remains outside the current scope. Do not silently publish services, alter live PKI/firewall state, delete workloads, or rotate production material merely because those items appear in the checklist.

Suggested continuation prompt:

> Read docs/CTF_AUDIT_HANDOFF.md and inspect the current repository. Confirm the outstanding publication blockers against current code. Help me implement the fixes in priority order, starting with an agreed challenge catalog and working flag flow. Keep intentional CTF vulnerabilities contained, and separate local changes from live EC2 deployment actions.

## External references consulted

- [Kubernetes NetworkPolicy behavior and limitations](https://kubernetes.io/docs/concepts/services-networking/network-policies/)
- [Kubernetes networking model and shared pod networking](https://kubernetes.io/docs/concepts/services-networking/)
- [OpenVPN certificate revocation and CRL enforcement](https://openvpn.net/community-docs/revoking-certificates/)

These references supported interpretation of network and revocation behavior. They do not verify this deployment's live state.
