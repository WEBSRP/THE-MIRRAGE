# Email readiness, failures and provider health

Implemented in source and tested with mocked providers. No production service,
mailbox, key, database or deployment configuration was changed. No real email was
sent. Real sender authorization and inbox delivery remain release acceptance work.

## Supported configuration

Production startup now refuses incomplete or unsupported email configuration
before flags, database initialization or infrastructure checks. Supported providers
are `resend` and `sendgrid`. The old SMTP path prepared a message without sending
it; that path has been removed and `smtp` is explicitly rejected.

| Setting | Requirement |
| --- | --- |
| `EMAIL_PROVIDER` | `resend` or `sendgrid` |
| `EMAIL_API_KEY` | Nonempty printable ASCII token, without whitespace/control characters |
| `EMAIL_FROM` | Explicit syntactically valid sender address |
| `EMAIL_FROM_NAME` | Optional display name without control characters; at most 128 characters |
| `EMAIL_REPLY_TO` | Optional syntactically valid address |
| `EMAIL_TIMEOUT_SECONDS` | Positive total provider-request bound, at most 60 seconds; default 10 |
| `EMAIL_HEALTH_RETENTION_DAYS` | Positive retention period; default 7 days |

Configure credentials privately through the existing environment-file mechanism;
never paste keys into logs, public source or command arguments. The legacy
`EMAIL_FROM_ADDRESS` field does not substitute for explicit `EMAIL_FROM` readiness.
Sender syntax validation makes no DNS or provider call. It does not prove that a
domain is verified, the API key is authorized, an account has credit, or a mailbox
can receive messages. Verify these with the selected provider and a controlled
mailbox before publication.

## Dispatch and public failure behavior

OTP issuance and its email quotas commit before provider dispatch, preserving
the previous atomicity and budget controls. A separate delivery-intent record
commits before a request can leave the process. If intent cannot be stored, the
provider is not contacted. This avoids silently sending without operational state.

HTTP requests go only to the fixed Resend/SendGrid HTTPS endpoints, with TLS
verification, redirects disabled and environment proxy variables ignored. HTTPX
timeouts and an outer wall-clock timeout bound the operation, including a slow
provider. There is no automatic retry, fallback provider or refund of committed
email budget. A timeout/server error may have accepted a message despite a missing
response; automatically retrying could duplicate it and increase cost.

Resend must return HTTP 200 with a nonempty acceptance ID; SendGrid must return
HTTP 202. The ID/body is not stored or exposed. Other statuses are failures; server
errors, timeouts, transport errors, invalid acceptance receipts or interrupted
requests can have unknown side effects. Raw provider bodies, exception text,
credentials, recipient addresses and OTPs are not copied into health records or
dispatch logs. Only fixed codes and optional HTTP status numbers are retained.

Request/resend failures return a generic HTTP 503 with `OTP_EMAIL_UNAVAILABLE`,
without revealing account existence or provider diagnostics. Other unexpected
issuance failures also no longer fall through to a misleading success response.
Existing HTTP 429 budget/cooldown responses retain their behavior. Successful API
requests indicate that the provider accepted the request, not that inbox delivery
has been confirmed.

If a provider fails after OTP issuance, the new code and budget reservations remain
committed; the old code remains superseded. Use the normal rate-limited resend
flow after resolving an outage. No uncertainty about delivery resets quotas or
makes a consumed OTP reusable. If acceptance occurs but health finalization fails,
the API returns 503 and leaves a pending record rather than claiming success.

Test mode and explicit development OTP mode return a simulated result and do not
contact a provider. Development OTP mode still deliberately prints the code; it
must stay private and is rejected in production. A simulated/unexpected result
cannot count as live provider acceptance outside those modes. Email templates
display the configured OTP expiry period.

## Admin health endpoint

`GET /api/v1/health/email` requires an active administrator token and sends no mail.
Successful responses use `Cache-Control: no-store`. Non-admin players cannot read
provider health or traffic counters. The public platform health route does not
expose this data.

The endpoint reports configuration readiness and the current provider's last
24-hour attempt totals: accepted, failed, unknown, pending and simulated. It also
reports the latest attempt timestamp, fixed error code and HTTP status, plus
`mailbox_delivery_confirmed: false`. It never returns recipients, message contents,
keys, OTPs, raw diagnostics or provider receipt IDs.

| Status | Meaning |
| --- | --- |
| `unconfigured` | Provider configuration is invalid; production startup would refuse it |
| `not_checked` | No recent attempt for the configured provider |
| `pending` | Latest attempt is still within its request/grace interval |
| `accepting` | Latest attempt was accepted, with no unresolved recent unknown outcomes |
| `degraded` | Latest failure/unknown result, or an unresolved unknown attempt |
| `simulated` | Explicit testing/development simulation; no live readiness claim |

An interrupted worker leaves durable pending intent. After the configured timeout
plus 30 seconds, health counts it as unknown and degrades the signal. Independent
workers share the same database metadata; process restart does not clear history.
Old metadata is removed in batches of at most 1000 per cleanup pass. Records have
no recipient or OTP foreign key. New attempts and final outcomes commit separately
from OTP/account transactions; a provider failure cannot undo those earlier commits.

This is provider acceptance telemetry, not a signed bounce/delivery webhook system,
mailbox verification service, alert integration or durable email-retry queue. Arrange
external monitoring with authorized admin access and provider-side delivery alerts.
Retain a recovery channel independent of email/VPN; expired admin tokens cannot be
renewed through a broken OTP provider merely to read this endpoint.

## Migration and controlled rollout

1. Review the maintained migration, isolation and OTP-abuse runbooks. Keep public
   registration gated and rehearse against a restored copy with test credentials.
2. Apply `20261120_0006`, which creates indexed `email_delivery_attempts`. Existing
   `0005` databases upgrade normally; checked adoption recognizes the new snapshot.
   Grant the runtime role its required read/write/delete access on this new table.
   A downgrade refuses to discard populated health history. No migration was
   applied to the live EC2 database in this work.
3. Configure a supported provider, an authorized verified sender, API key, optional
   reply address, timeout and retention privately. Use credentials permitted to
   send from that sender. Remove any reliance on the old SMTP no-op/default sender.
4. Deploy all reviewed backend workers together during maintenance. Startup must
   pass syntax/configuration and migration checks. Existing quotas, proxy trust
   and infrastructure prerequisites still apply. No provider call is made merely
   by starting the backend or polling the health endpoint.
5. Check admin health before a probe: `ready`/`not_checked` is expected without recent
   traffic; it is not proof of delivery. Using a mailbox you control, request one
   OTP through the normal application flow. Confirm provider acceptance, inspect
   inbox/spam, enter that code successfully, and confirm the old code cannot be
   reused. Verify resend, expiry and sender/reply headers with that disposable
   account. This deliberate probe consumes normal quotas and needs the operator's
   chosen recipient; automated checks did not send it.
6. Confirm the provider console's actual delivery/bounce result and restore normal
   traffic only after the controlled acceptance check. Monitor 503s, provider
   rejection/timeouts, stale pending/unknown counts, quotas and cleanup health.
   Investigate with the provider console and protected configuration, not raw
   exception/payload logging. Fix provider authorization or sender verification
   before changing application quotas.

## Reproducible local checks

```bash
python3 backend/scripts/check_backend_postgres.py
python3 backend/scripts/check_backend_postgres.py backend/tests/test_email_delivery.py backend/tests/test_migrations.py
docker build -f backend/Dockerfile -t mirrage-backend:email-health-check .
python3 backend/scripts/check_migration_image.py --image mirrage-backend:email-health-check
```

Provider tests use HTTPX `MockTransport`, including accepted requests, rejections,
redirects, malformed receipts, transport failures and wall-clock timeouts. Other
checks cover production startup refusal, admin authorization, private diagnostics,
simulation, cancellation, health-state failure, retention, concurrent accounting,
OTP/quota invariants and schema adoption/downgrade. Disposable PostgreSQL/SQLite
tests and the mock image startup use no live provider key or service state.

Validated on 2026-11-20: the full backend suite passed **343 tests, 5 skipped**.
Following final live-acceptance and generic failure guards, the focused provider,
OTP, abuse and migration suites passed **179 tests, 5 skipped**. Skips are SQLite
variants of native PostgreSQL cases whose PostgreSQL versions passed. Image build,
packaged migration/mock startup, compilation and whitespace checks passed. No real
mailbox delivery or production rollout was performed.

References: [Resend OpenAPI](https://github.com/resend/resend-openapi/blob/main/resend.yaml),
[SendGrid Mail Send](https://www.twilio.com/docs/sendgrid/api-reference/mail-send/mail-send),
[SendGrid acceptance is not inbox delivery](https://support.sendgrid.com/hc/en-us/articles/37945843123995-SendGrid-API-Returns-202-Accepted-Response-but-doesn-t-Send-Email),
[HTTPX timeouts](https://www.python-httpx.org/advanced/timeouts/).
