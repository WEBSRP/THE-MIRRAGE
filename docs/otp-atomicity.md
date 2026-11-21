# Concurrent OTP verification and resends

Implemented in source; production workers and the EC2 database have not been
changed. This update requires no new table or column.

## Guarantees

OTP issue, resend and verification normalize the email using the same lowercase
and whitespace rules before acquiring the same PostgreSQL transaction advisory
lock. This covers both existing accounts and emails without any account or OTP row.
The lock key remains compatible with the earlier issuance implementation. SQLite
acquires its database writer lock before reading, including for an unknown email.
The in-process lock supplements these database locks; it is not the concurrency
guarantee between independent workers.

Verification reads the latest OTP with a row lock and refreshes cached ORM values.
It never falls back to an older unused code after the latest code is consumed.
Expiry is checked after acquiring locks. A conditional SQL update requires an
unused, unexpired record with attempts below the configured limit. The update
increments attempts in SQL and closes the record on a correct code or the final
incorrect attempt. Requests arriving after exhaustion are rejected without
increasing the counter beyond its budget.

Only a winning correct-code transaction can create/verify an account. OTP
consumption and account changes commit together before external VPN provisioning
or JWT creation. A database failure rolls both changes back and returns no token.
A later VPN provisioning failure cannot undo consumption or permit OTP replay;
the user must obtain a fresh OTP to sign in, and profile provisioning can be
retried through the normal profile flow. A correct code for a disabled account
is consumed without issuing a token, even if the account is subsequently enabled.

Issuance invalidates all previous unused records in the same transaction that
creates the new code. New numeric codes avoid recently issued and superseded
values, with bounded retries on collisions. Failure to generate a distinct code
rolls back invalidation and leaves the previous code usable until its normal
expiry or attempt limit. Codes retain the existing dedicated HMAC format; raw
codes are not stored in the database.

The existing send policy is preserved: one immediate resend per rolling request
window, then the configured cooldown, with a shared per-email send budget.
Concurrent requests cannot multiply the immediate allowance or bypass the budget.
Cooldown/rate-limit responses retain HTTP 429 and `Retry-After`. UTC conversion
handles both PostgreSQL aware timestamps and SQLite naive timestamps.

Email delivery runs after the issuance commit and outside the critical section.
Provider delay therefore does not hold an OTP transaction lock. Emails can arrive
out of order; only the latest committed code is valid. A failed delivery still
counts as an issuance and now returns a generic HTTP 503 without exposing account
existence; see [email-readiness.md](email-readiness.md).
Trusted-proxy IP throttling and global email budgets now have a source implementation;
see [otp-abuse-controls.md](otp-abuse-controls.md) for migration and proxy rollout.
Provider readiness and private acceptance health are implemented in
[email-readiness.md](email-readiness.md). Real mailbox acceptance, durable retry
queues, delivery webhooks and provider alert integration remain separate work.

## Deployment and verification

Deploy all authentication workers together: older verification workers do not
participate in the shared lock protocol. Use PostgreSQL's default READ COMMITTED
isolation with the existing async session configuration. No live rollout or
database migration was performed in this work. Existing `TIMESTAMPTZ` OTP columns
already support aware UTC timestamps; the Python default was corrected accordingly.

Before publishing, use disposable staging accounts to confirm one login succeeds
when the same code is verified in parallel, the attempt budget cannot be bypassed,
old codes fail after resend, and cooldown/expiry behavior matches the UI. Check
actual email delivery and the disabled-account path. Never test by sending
parallel login attempts to real player accounts.

Run all backend checks from the repository root:

```bash
python3 backend/scripts/check_backend_postgres.py
```

To run only the new concurrency cases, append
`backend/tests/test_otp_concurrency.py`. The runner supplies test-only settings,
uses mock email/VPN services, and removes its network-isolated PostgreSQL container
and temporary socket directory. SQLite tests use separate file-backed connections;
PostgreSQL tests use independent services and database transactions. They cover
single consumption/account creation, concurrent attempt counting, the final
attempt race, stale cached records, resend/verification ordering in both directions,
send budgets, the immediate resend allowance, expiry during lock waiting, disabled
accounts, transaction rollback, numeric collisions and slow email delivery.

Validated on 2026-11-20: **226 backend tests passed, 3 skipped**. The three skips
are SQLite parameterizations of PostgreSQL-specific lock-order/wait cases; their
PostgreSQL versions passed. Python compilation and `git diff --check` also passed.
No live email, VPN or production database was used.

The implementation is in `backend/app/services/auth_service.py`, with timestamp
defaults in `backend/app/models/otp.py`. PostgreSQL documents the transaction and
row-lock behavior in its [explicit locking reference](https://www.postgresql.org/docs/16/explicit-locking.html).
