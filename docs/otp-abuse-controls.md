# OTP request and email budgets

Implemented in source; no real email, production database or live proxy/service
configuration was changed. These controls complement the atomic OTP verification
in [otp-atomicity.md](otp-atomicity.md).

Later live recovery update (2026-11-21): migrations through `0006`, explicit local
proxy trust, loopback-only Nginx/Uvicorn and `--no-proxy-headers` are now deployed.
Public API health and required/malformed origin-header checks pass. No real OTP
email or live quota-exhaustion test was performed; see
[live-otp-recovery.md](live-otp-recovery.md).

## Limits and storage

| Setting | Default | Meaning |
| --- | --- | --- |
| `OTP_IP_REQUEST_LIMIT` | 10 | Requests per client bucket |
| `OTP_IP_WINDOW_SECONDS` | 600 | Fixed IP request window |
| `OTP_EMAIL_HOURLY_LIMIT` | 100 | Global issuance reservations per UTC hour |
| `OTP_EMAIL_DAILY_LIMIT` | 500 | Global issuance reservations per UTC day |
| `OTP_IP_BUCKET_RETENTION_SECONDS` | 86400 | Retain inactive IP buckets this long after their window expires |
| `OTP_TRUSTED_PROXY_CIDRS` | `[]` | Immediate proxies allowed to provide normalized client identity |

Both `/auth/request-otp` and `/auth/resend-otp` consume the same per-IP allowance
before email-specific cooldown checks. Valid send requests rejected by an email
cooldown or global budget still count against their IP's request allowance. Body
validation errors do not issue a code. Verification keeps the existing per-code
attempt budget; this update does not introduce a separate IP limit on verification.

IPv4 identities are canonicalized, including IPv4-mapped IPv6 addresses. IPv6
addresses in the same `/64` share a bucket to resist interface-ID rotation. Shared
NAT users also share a bucket; tune the defaults using the expected pilot audience.
The database stores a domain-separated HMAC of the network identity using the OTP
HMAC secret, not a raw visitor address. These are pseudonymous identifiers. Secret
rotation changes IP bucket identities; it does not reset the global counters.
Changing the IP window duration also selects a new bucket so incompatible window
numbers cannot lock users out. Treat such configuration changes as a quota reset;
the global hourly/daily counters remain unchanged.

The `otp_abuse_buckets` table holds one current window per IP identity and two
global counters. Atomic upserts arbitrate independent processes/connections. Time
comes from the database; older queued requests cannot reset a newer window backward.
The hourly and daily reservations share the OTP issuance transaction. If either
budget rejects issuance, both reservations and invalidation of the previous code
roll back. Existing email cooldown/rate checks do not consume global send slots.

Once issuance commits, provider failure/cancellation does not refund its slot.
This prevents retry loops from bypassing the cost boundary. These are fixed UTC
windows and issuance reservations, not rolling limits or guarantees of provider
delivery/billing time. Boundary bursts are possible. Configure matching provider
quotas/alerts before opening registration and keep every worker on the same
database and limits. Clearing/restoring counters can reset the budget; reconcile
provider usage before reopening traffic after database recovery. The new table starts
with empty counters, so account for pre-rollout sends when choosing the initial cap.

IP/global rejection returns HTTP 429 with `Retry-After`; the respective public
codes are `OTP_IP_RATE_LIMIT` and `OTP_EMAIL_BUDGET`. Missing proxy identity or an
unavailable counter database blocks sending with a generic HTTP 503. No in-memory
fallback allows email if the quota database fails. Account existence is not exposed.

The worker removes at most 1000 expired IP buckets per pass after the retention
interval. It preserves global counters and rechecks expiry when deleting so a
renewed bucket is not intentionally removed. Restarts retain counters. Cleanup
failure retains rows and is retried; it does not disable request limits.

## Cloudflare Tunnel and Nginx trust contract

The supported host deployment is:

```text
Cloudflare -> local cloudflared -> loopback Nginx -> loopback Uvicorn
```

`infrastructure/nginx/mirrage.conf.example` listens only on `127.0.0.1:80` and
`[::1]:80`. Nginx trusts `CF-Connecting-IP` only from its local tunnel peers,
rejects missing/malformed/list identities, and overwrites `X-Mirrage-Client-IP`
with the normalized visitor address. It also replaces `X-Forwarded-For` and
`X-Real-IP`, and removes `CF-Connecting-IP` before forwarding to the backend.
Incoming caller-provided `X-Mirrage-Client-IP` is overwritten.

The backend uses the socket peer directly unless that peer is in
`OTP_TRUSTED_PROXY_CIDRS`. A trusted peer must provide exactly one valid IP literal
in `X-Mirrage-Client-IP`; malformed, duplicate or absent values fail closed. The
backend never selects an identity from `X-Forwarded-For`, `X-Real-IP`, or
`CF-Connecting-IP`. Wildcard proxy networks are rejected in settings.

For the same-host Nginx service, explicitly configure:

```dotenv
OTP_TRUSTED_PROXY_CIDRS=["127.0.0.1/32","::1/128"]
```

Leave it empty for direct local development. Other deployments must explicitly
identify their immediate trusted proxy; do not trust all Docker/VPN/Internet peers.
Without proxy trust, forwarded headers are ignored and all connections arriving
from one proxy share its peer-IP budget. This restricts availability rather than
allowing a caller-selected identity.

Run Uvicorn with `--no-proxy-headers`, as in the updated systemd example and Docker
command. This keeps its ASGI client address equal to the socket peer so the
application owns this one trust decision. Never use wildcard forwarded trust or
expose the trusted origin/backend publicly. Same-host processes are inside this
trust boundary; CTF workloads must remain unable to access host management ports.

Configure the actual Cloudflare Tunnel origin as `http://127.0.0.1:80`. Retain
Cloudflare's real visitor header; do not enable transforms that remove it or
Pseudo IPv4 overwrite without reviewing this identity contract. The origin
listener restriction and tunnel configuration are part of the control, not merely
optional header parsing. Local HTTP checks through this Nginx template also need
a synthetic `CF-Connecting-IP`; a request missing it intentionally receives 400.

## Rollout and acceptance

1. Keep registration/traffic gated. Review the existing isolation, revocation and
   database migration prerequisites. Deploy all authentication workers together;
   old workers do not participate in these new quotas.
2. Back up and rehearse against a restored copy using
   [database-migrations.md](database-migrations.md). Apply revision
   `20261120_0005`, which creates the indexed budget table. Ensure the runtime role
   has SELECT/INSERT/UPDATE/DELETE permission on this new table. Existing databases at
   `0004` upgrade normally; checked adoption also recognizes the new snapshot.
   Startup refuses an older head. A populated budget table cannot be downgraded
   away merely to reset rate limits.
3. Review the per-IP and global defaults against the pilot and provider allowance.
   Set the same values and HMAC secret on all workers. Set the intended immediate
   proxy allowlist. Store configuration privately; no raw IPs or OTPs need to be
   added to settings or source.
4. Review/install the Nginx template and Uvicorn flag as one maintenance rollout.
   Confirm origin/backend bindings remain private, the real-IP module is available,
   and only the intended tunnel reaches the Nginx listener. No live configuration
   in this work was installed or reloaded.
5. In staging, use disposable addresses and mocked/test email delivery. Confirm
   changing emails cannot evade an IP limit, two legitimate visitors have distinct
   buckets, request/resend share counters, and forged forwarded headers cannot
   choose another identity. Confirm 429/`Retry-After`, global saturation, restart
   persistence and database-outage refusal. Verify actual edge/tunnel header
   propagation before production; a local proxy simulation does not attest it.
6. Monitor global budget exhaustion, repeated 429/503 responses, provider failure
   and cleanup/DB health. Add provider billing/delivery alerts. The counters are
   not a CAPTCHA, edge DDoS control or a reliable mail queue; distributed attackers
   can still consume the allowed budget and temporarily deny OTP availability.

## Reproducible checks

```bash
python3 backend/scripts/check_backend_postgres.py
python3 backend/scripts/check_backend_postgres.py backend/tests/test_otp_abuse.py backend/tests/test_migrations.py
docker build -f backend/Dockerfile -t mirrage-backend:otp-abuse-check .
python3 backend/scripts/check_migration_image.py --image mirrage-backend:otp-abuse-check
docker run --rm --network none \
  --mount type=bind,source="$PWD/infrastructure/nginx",target=/checks,readonly \
  --entrypoint python3 mirrage-ctf:shared-flags-check /checks/check_otp_proxy.py
```

The existing CTF test image provides real Nginx for the last check; its game
entrypoint is bypassed. The harness starts only a fake HTTP backend and Nginx in
that disposable container. It publishes no ports and mounts no host service state.
Backend concurrency tests use independent connections/services and mock email.
No message was sent to a real mailbox.

References: [Cloudflare visitor headers](https://developers.cloudflare.com/fundamentals/reference/http-headers/),
[Nginx real-IP module](https://nginx.org/en/docs/http/ngx_http_realip_module.html),
[Uvicorn proxy settings](https://uvicorn.dev/settings/).

Validated on 2026-11-20: the full backend suite passed **295 tests, 5 skipped**.
After the final configurable-window review and additional public API checks, the
focused abuse/atomicity/migration suite passed **104 tests, 5 skipped**. Skips are
SQLite variants of native PostgreSQL checks whose PostgreSQL versions passed.
The real Nginx contract test, packaged backend build/startup, compilation and
whitespace checks passed. Actual Cloudflare Tunnel propagation and live rollout
have not been exercised.

Provider configuration, bounded failures and admin-only acceptance health now have
a source implementation; see [email-readiness.md](email-readiness.md). Apply the
latest migration head (0006), then complete real mailbox acceptance before rollout.
