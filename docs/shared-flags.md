# Shared CTF flags

MIRRAGE uses three different static flags shared by all players. The submission
endpoint remains `POST /api/v1/challenges/submit`; the browser never receives an
expected flag and the API does not query the target container to verify an answer.

Live recovery update (2026-11-21): private shared flags are installed outside Git
at `/home/admin/.config/mirrage/ctf-flags.json` with an encrypted backup. Backend
DB verifiers match them; the immutable Kubernetes Secret is encrypted at rest.
Release CTF image passed its smoke test and is imported into K3s. Real-player
acceptance remains pending; see [live-otp-recovery.md](live-otp-recovery.md).

| Stage | Existing challenge slug | Target file | File owner | Points on a fresh database |
| --- | --- | --- | --- | --- |
| Web | `first-reflection` | `/var/www/html/flag.txt` | `www-data` | 100 |
| User | `sub-stratum-breach` | `/home/player/flag.txt` | `player` | 250 |
| Root | `oasis-evaporation` | `/root/flag.txt` | `root` | 300 |

The web flag is denied by Nginx's static HTTP route. It is readable through the
intended code execution as `www-data`. The three files are created with mode 600
before any target services start. The intentional cron escalation paths remain.

## Development and dummy values

In development/testing, leaving `CTF_FLAGS_FILE` empty selects
`backend/ctf-flags.example.json`. This contains the same three dummy values used
by the automated tests. No flags are baked into the target image.

For local Compose, the example JSON is mounted automatically:

```bash
docker compose -f containers/docker-compose.yaml up --build
```

This Compose file provides target containers on a private Docker network; it does
not start the platform API or configure a player's VPN/routing.

For custom development flags, create a private JSON with exactly these keys:

```json
{
  "web": "MIRRAGE{your_distinct_web_value}",
  "user": "MIRRAGE{your_distinct_user_value}",
  "root": "MIRRAGE{your_distinct_root_value}"
}
```

Keep the file private, set backend `CTF_FLAGS_FILE` to its path, and set
`MIRRAGE_FLAGS_HOST_FILE` to the **same file's absolute host path** for Compose.
Relative backend paths resolve from `backend/`; absolute paths are recommended
for deployment. Do not use the example values in production.

## Production deployment

1. Generate a private file without printing flags or overwriting existing files:

   ```bash
   python3 backend/scripts/generate_ctf_flags.py --output backend/ctf-flags.json
   ```

   The generator uses a cryptographic random source and creates the file with
   mode 600. The filename is ignored by Git and excluded from Docker builds.
   Store an encrypted backup and restrict access to the backend service identity.

2. Set `CTF_FLAGS_FILE` in the private backend environment, for example:

   ```dotenv
   CTF_FLAGS_FILE=/home/admin/THE-MIRRAGE/backend/ctf-flags.json
   FLAG_SUBMISSIONS_PER_WINDOW=10
   FLAG_SUBMISSION_WINDOW_SECONDS=60
   ```

   Production refuses missing configuration, duplicate flags, malformed values,
   and short or obvious dummy values. Flag bodies must have at least 32 characters;
   the supplied generator produces 48 random hex characters plus a stage prefix.
   For a containerized backend, mount this private file read-only at an absolute
   container path and configure that path. Never copy it into an image or place it
   in any `VITE_*` setting.

3. Build and deploy the updated CTF image and configure `CTF_CONTAINER_IMAGE` to
   use that release. Old images do not implement runtime flag initialization.

4. For Kubernetes, the backend's provisioner needs namespaced `get` and `create`
   access to Secrets in the session namespace in addition to its existing pod
   permissions. It creates/reuses an immutable Secret named
   `mirrage-ctf-flags-<revision>` from the configured JSON. The same revision is
   mounted into every CTF container, root-readable (0400), and is not mounted into
   Mirage. Plaintext values never appear in pod environment variables or commands.

   Do not give player service accounts Secret permissions. Restrict operator
   access and enable Kubernetes Secret encryption at rest: base64 encoding alone
   is not encryption. The sample pod manifest requires substituting the generated
   Secret name; the API provisioner does this automatically.

5. Before the first production restart, take a database backup and drain existing
   player sessions. Apply the versioned migrations in
   [database-migrations.md](database-migrations.md) to create `challenge_solves` and
   `flag_submission_quotas`. Startup verifies the schema revision, then runs the
   following idempotent data initialization in a transaction:

   - Existing stage IDs, titles, points, active status, and solve history remain.
   - The three default verifiers are synchronized to the configured flag hashes.
   - Custom legacy plaintext challenge answers are hashed, not replaced.
   - Historical correct attempts are backfilled into unique solve records.
   - Historical submitted flag strings are replaced with `[REDACTED]`.

   The redaction is intentional and irreversible without a backup. Backups taken
   before migration still contain the old plaintext and need appropriate protection.
   Start one instance for initialization before scaling API workers. All workers
   must use the same configuration file contents. Do not run a rolling mixed-version
   deployment: older code expects plaintext answers and does not use the new quota
   and solve tables. Rollback requires restoring compatible code and database state.

## Verification behavior

```http
POST /api/v1/challenges/submit
Authorization: Bearer <player-token>
Content-Type: application/json

{"challenge_slug":"first-reflection","flag":"MIRRAGE{candidate}"}
```

- A correct first submission returns `is_correct: true` and awards stage points.
- A correct repeat returns `already_solved: true` and awards zero additional points.
- A wrong-stage or incorrect answer returns `is_correct: false` and zero points.
- Missing/inactive challenges return 404; unauthenticated requests return 401.
- All authenticated attempts count toward an account-wide fixed-window limit
  across stages and API workers. Exceeding it returns 429, `FLAG_RATE_LIMIT`, and
  `Retry-After`. The default is 10 requests per 60-second window. As with any fixed
  window, requests can cluster around a boundary. This is not a global/per-IP DoS
  control; gateway-level protection remains a separate publication task.
- The database stores `sha256:<hex>` verifiers in the legacy `challenges.flag`
  column, and `[REDACTED]` in the legacy `flag_submissions.submitted_flag` column.
  Comparison is constant-time over hashes. The unique `(user_id, challenge_id)`
  solve key makes simultaneous correct requests award points only once. Solve,
  attempt, and activity record commit in the same transaction.
- Matching trims surrounding whitespace only and remains case-sensitive. Production
  flags must be high-entropy because a plain SHA-256 verifier is not a password hash.

## Rotation and operational limits

Flag configuration is loaded once per backend process. To rotate it, drain/stop
existing sessions, update the private JSON, and restart all backend workers with
the same revision. Recreate player pods from the new revision. Existing solves
remain credited. An old pod retains its old immutable Secret and must not be left
running against a new verifier. Old Secrets are intentionally not deleted by
provisioning; an operator can remove an obsolete revision after confirming no pod
references it.

Shared flags can be passed between players. This is an accepted property of the
chosen static-flag design; the platform does not prove that a player followed the
intended exploit path. Player-specific flags would be a separate design change.

Subsequent VPN/pod isolation and cleanup integration is documented in
[player-isolation.md](player-isolation.md). Its live rollout/acceptance tests,
fixed SSH credential shortcuts, cluster-wide orphan sweeping and targeted VPN
revocation remain publication/operations work in [the audit handoff](CTF_AUDIT_HANDOFF.md).

## Checks

Deploy the updated CTF image before enabling the backend's HTTP readiness probe.
The probe requests `/_health` through Nginx and the forum backend. For optional
developer SSH, set `CTF_DEVELOPER_SSH_PUBLIC_KEY` to a single OpenSSH public key
in the backend environment. The private key stays with the developer. When the
setting is empty, the CTF image does not start SSH.

To build and smoke-test the target image locally (Docker required):

```bash
docker build -t mirrage-ctf:shared-flags-check containers/ctf
python3 backend/scripts/check_ctf_image.py
```

The smoke test uses dummy flags, the normal image entrypoint/CMD and sandbox-like
capabilities, with no network or published host ports. It checks service readiness,
flag ownership/modes, denied cross-stage reads, denied direct HTTP flag downloads,
and intended web-stage recovery. It also checks that flags are absent from the
image and that missing runtime configuration prevents startup. Its own temporary
container is stopped afterward.

Use explicit test settings and mock infrastructure; do not run tests against a
production database. The new tests cover both players sharing the three flags,
hash-only storage, wrong-stage answers, legacy migration, file modes, immutable
Secrets, duplicate solves under separate concurrent connections, and concurrent
quota enforcement. Optional PostgreSQL concurrency cases use
`MIRRAGE_TEST_POSTGRES_URL`, which must point at a disposable isolated database.

Validated on 2026-11-20: 133 backend tests passed with the PostgreSQL cases enabled;
frontend lint/build, both image builds, the CTF runtime smoke test and isolated
backend startup also passed. No production database migration, live Kubernetes
provisioning, or full deployed user/root exploit walkthrough was performed.
