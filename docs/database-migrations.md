# Versioned database migrations and recovery

Implemented and tested on disposable databases. No production database, live
backend service, VPN state or deployment configuration was changed.

Later live recovery update (2026-11-21): the existing RDS schema was atomically
aligned, checked/adopted and upgraded to `20261120_0006`, preserving all original
rows. Nine existing real VPN profiles subsequently received stable reservations
and CCDs. Backend remains stopped pending remaining startup prerequisites; see
[live-otp-recovery.md](live-otp-recovery.md) for reports and exact rollout state.

## Revisions and startup

Alembic configuration is `backend/alembic.ini`. Frozen schema definitions live in
`backend/migrations/schema_20261120.py`, `schema_otp_abuse.py` and
`schema_email_health.py`; historical revisions never import the current ORM models. Future model changes require new reviewed revisions.

| Revision | Schema change |
| --- | --- |
| `20261120_0001` | Repository baseline: users, challenges, sessions, profiles, activity, submissions and OTPs |
| `20261120_0002` | Unique challenge solves and durable submission quotas |
| `20261120_0003` | Stable VPN address reservations |
| `20261120_0004` | Durable VPN revocations and CRL maintenance |
| `20261120_0005` | Per-IP OTP request counters and global email budgets |
| `20261120_0006` | Private operational email provider health metadata |

Application startup now checks that the database is at the code's migration head.
It does not call `create_all`, run DDL, or automatically stamp a legacy database.
An empty, unversioned or behind database refuses startup before challenge seeding
and cleanup begin. Production schema changes are an explicit maintenance step.
The runtime database account needs read access to `alembic_version` in addition to
its application permissions. Prefer a separate migration identity with the required
schema ownership/DDL rights; do not grant the runtime account unnecessary DDL rights.

The Docker image packages the Alembic configuration, revisions and migration CLI.
It does not run migrations in its entrypoint. All commands below run from the
repository root using the intended protected configuration through `ENV_FILE`
and/or the existing `DATABASE_URL` setting. Never put credentials in a command-line
argument or print the effective connection URL.

## Empty development database

Install `backend/requirements.txt`, configure a private development environment,
then run:

```bash
backend/.venv/bin/python -m backend.scripts.migrate status
backend/.venv/bin/python -m backend.scripts.migrate upgrade
backend/.venv/bin/python -m backend.scripts.migrate status
```

`upgrade` defaults to `head`; status should report `current` at `20261120_0006`.
The status operation reads revision state and does not initialize tables. Start
the backend normally afterward; challenge seeding/data sanitization occurs there.
The existing explicit initialization helper also applies migrations before seeding:

```bash
backend/.venv/bin/python -m backend.scripts.init_db
```

These operations use the configured database. Verify the intended environment
before running them. A relative SQLite URL resolves against the working directory;
use an absolute URL when moving between repository and backend directories.

## Existing unversioned databases

Existing databases created by earlier `create_all` releases need checked adoption.
Back up and restore a disposable copy first, and rehearse this sequence there:

```bash
backend/.venv/bin/python -m backend.scripts.migrate status
backend/.venv/bin/python -m backend.scripts.migrate adopt
backend/.venv/bin/python -m backend.scripts.migrate upgrade
backend/.venv/bin/python -m backend.scripts.migrate status
```

`adopt` matches the complete schema to one of the six supported snapshots before
recording its revision. It checks table sets, columns/types/nullability/defaults,
indexes/unique keys, foreign keys, primary keys and native PostgreSQL enum labels.
It changes only migration tracking; it does not recreate tables or transform data.
A database already containing all current tables can be adopted at `0006`; a
baseline database adopts `0001` and gets the additive changes through upgrade.

Unknown/partial layouts, altered constraints, extra tables and pre-baseline schemas
are rejected. Examples include a missing unique solve primary key, an unexpected
session enum value, or columns/defaults from an older manual SQL migration that
do not match the supported baseline. Investigate a restored copy and prepare an
explicit correction plan for that actual schema. Do not bypass the mismatch by
blindly stamping `head`, dropping data, or running the historical OTP SQL file.
Blind upgrades and stamps against nonempty unversioned databases are blocked.

Adoption and migration execution share a PostgreSQL transaction advisory lock,
separate from application locks. This serializes cooperating migration processes;
it does not replace stopping application writers or reviewing a maintenance window.
SQLite DDL has driver-specific transaction limitations; PostgreSQL is the tested
production migration target. Restore a development copy if a SQLite migration is
interrupted with a partially created schema rather than blindly stamping it.

## Production maintenance sequence

1. Record the current release, migration status, environment source and rollback
   target. Keep the prior artifact available. Use a database clone to rehearse the
   exact adoption/upgrade and application startup before touching production.
2. Block new API traffic and provisioning, drain player environments through the
   supported cleanup flow, and stop every backend/worker that can write. Coordinate
   gateway/CRL state with the existing isolation/revocation runbooks; keep a recovery
   connection independent of player VPN access.
3. Take a consistent database backup and verify restoration to a separate empty
   database. Keep encrypted PKI/root state backups coordinated with database state.
   Dumps contain sensitive account, OTP, profile/private-key and flag-related data:
   keep them on protected encrypted storage with restricted permissions.
4. Select the intended migration identity/configuration and run `status`. Run
   checked `adopt` only for an unversioned supported layout, then `upgrade` and
   `status`. A failed schema/adoption check is a stop condition, not permission to
   reset migration history. Do not migrate automatically on every worker start.
5. Review the actual schema against the models using:

   ```bash
   backend/.venv/bin/alembic -c backend/alembic.ini check
   ```

   Then start the reviewed backend release with its production flags, dedicated
   kubeconfig and installed root helpers. Its startup revision check must pass.
6. Validate authentication, flag submission/unique solve behavior, VPN revocation,
   reservation ownership and cleanup with disposable staging/pilot accounts. Confirm
   worker health and the two-player isolation matrix before reopening registration.

Schema upgrades create the tables; they do not reserve live VPN addresses, generate
CCDs, alter PKI, or configure Kubernetes. Those remain explicit deployment steps.
Challenge startup initialization still synchronizes flag hashes, backfills historical
unique solves and redacts old submissions. Raw redacted answers cannot be recovered
with a schema downgrade; preserve the pre-change backup according to retention rules.

## Backup, rollback and restoration

Use an operator-managed PostgreSQL service definition and protected password file
or equivalent IAM/RDS authentication. The following are command templates, not
commands that were run against EC2. `mirrage_backup` must select the intended source;
`mirrage_restore` must select a separate, empty recovery database, not the source.

```bash
umask 077
MIRRAGE_BACKUP_FILE=/protected/encrypted-storage/mirrage-before-upgrade.dump
PGSERVICE=mirrage_backup pg_dump --format=custom --file="$MIRRAGE_BACKUP_FILE"
pg_restore --list "$MIRRAGE_BACKUP_FILE" > /dev/null
PGSERVICE=mirrage_restore pg_restore --exit-on-error --single-transaction --no-owner --dbname=service=mirrage_restore "$MIRRAGE_BACKUP_FILE"
```

`pg_restore --list` checks the archive catalog, not recovery correctness. Verify
the restored row counts/integrity, migration status, revocation tombstones,
reservations and solves in the recovery database. Rehearse schema upgrade and mock
application startup against that copy with credentials/settings that cannot reach
live VPN, Kubernetes or email services. A dump/restore against the actual production
engine/version/roles and encrypted backup restoration remain live operations gates;
the automated tests use disposable local databases only.

For an application failure after an additive schema upgrade, keep the maintenance
gate closed. Prefer a reviewed compatible application rollback while retaining the
new schema and security records, or a forward fix. Earlier application releases
may lack the security fixes and must not be exposed to unrestricted players.

An explicit schema downgrade is available for empty tables, with an explicit target:

```bash
backend/.venv/bin/python -m backend.scripts.migrate downgrade 20261120_0004
```

Revision downgrades lock their target tables against writers and refuse if
any target contains rows. They never discard populated revocation records,
reservations, quotas, solves or baseline data, and do not offer a force-data-loss
switch. Empty disposable databases are tested through downgrade to `base` and
re-upgrade. Offline downgrades are disabled because contents cannot be checked.

If recovery requires older data, restore the verified snapshot to a separate
database, review it and deliberately switch the backend configuration while all
writers remain stopped. Do not overwrite the current database or delete its
history as an automatic recovery action. Keep current PKI/CRL enforcement and
reconcile any revocations/reservations and email budget usage created after the snapshot before allowing
access. Restoring an old database must not silently undo a VPN deny or reuse an
address still held by an old certificate. Confirm revision/schema/application
compatibility and access controls before reopening traffic.

## Future changes and validation

Generate a proposed revision against a disposable database at the current head:

```bash
backend/.venv/bin/alembic -c backend/alembic.ini revision --autogenerate -m "describe schema change"
```

Review generated DDL, data preservation, defaults/backfills, constraints, enums,
locking and downgrade behavior. Autogeneration does not understand all changes;
never apply its output unreviewed or edit historical snapshots to match new models.
Add upgrade and failure tests, then rehearse on a restored copy. Offline PostgreSQL
upgrade SQL for review can be generated using `upgrade head --sql` through the
Alembic CLI; it does not perform checked adoption or replace an online rehearsal.

```bash
python3 backend/scripts/check_backend_postgres.py
python3 backend/scripts/check_backend_postgres.py backend/tests/test_migrations.py
docker build -f backend/Dockerfile -t mirrage-backend:migrations-check .
python3 backend/scripts/check_migration_image.py
```

The test runner never inherits production settings and uses temporary SQLite files
and isolated PostgreSQL schemas in a disposable network-isolated container. The
image check uses a temporary SQLite database, mock services and no host state mounts.
It checks the packaged CLI, revision guard, upgrade, challenge seed and app startup.

Validated on 2026-11-20: the full backend suite passed **258 tests, 4 skipped**.
After adding future-revision generation and concurrent-writer rollback coverage,
the final migration suite passed **35 tests, 2 skipped**. The skips are SQLite
versions of native PostgreSQL checks; corresponding PostgreSQL cases passed.
The backend image build/startup check, Python compilation and whitespace checks
passed. Production backup restoration and rollout have not been performed.

References: [Alembic async/programmatic migration cookbook](https://alembic.sqlalchemy.org/en/latest/cookbook.html),
[PostgreSQL locking](https://www.postgresql.org/docs/16/explicit-locking.html).
