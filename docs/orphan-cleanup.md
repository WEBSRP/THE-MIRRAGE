# Abandoned environment cleanup

Implemented in source; not installed or exercised against live EC2 workloads.
The sweep complements database-driven session reconciliation by discovering
resources whose database rows have disappeared.

## Behavior

At backend startup and on each background cleanup cycle, the controller inventories
pods and NetworkPolicies in `K8S_NAMESPACE`, plus the root gateway's persistent
session bindings. Kubernetes listing follows all continuation pages. Both initial
inventories must succeed before cleanup begins. A timeout, authorization failure,
partial list or database error never means that a session or resource is absent.
Each periodic pass runs after expired-session cleanup and DB reconciliation; the
configured worker interval is a minimum delay between passes, not a deadline.

Candidates require the controller's ownership labels, canonical resource name,
UID and resource version. Unrelated pods, the namespace default-deny policy,
shared flag Secrets, service accounts and resources outside this namespace are
not deleted. Missing/inconsistent ownership labels require operator review.
This intentionally does not adopt old, ambiguously labeled resources by name.

Each candidate session is checked against the database again. Valid active
sessions are preserved, including starts within the existing three-minute
initialization window. Missing, expired, stopped, stale-initialization, disabled-user
or VPN-revoked sessions are cleaned. Conflicting user ownership is left pending
for review. PostgreSQL uses the same transaction advisory lock as session creation
and locks existing rows against extension. Invalid rows are durably marked
`STOPPING` before external operations, preventing a restart from regranting access.

Cleanup revokes gateway access first, then deletes the observed pod, then its
policy. Deletion re-reads ownership and sends UID/resource-version preconditions,
so a changed/replaced object is retried from a fresh inventory. Pods receive a
30-second shutdown period. A delete acknowledgement alone does not count as
success: the controller waits for confirmed API absence. A still-terminating pod
keeps its policy and source block and is revisited on the next pass. It does not
remove finalizers or force-delete unreachable pods.

After deletion, fresh Kubernetes and gateway inventories must show no remaining
session resources or pod occupying the binding's IP before the source block is
forgotten. IP occupancy includes pods with ambiguous/unrelated ownership labels;
these are preserved and keep cleanup pending. Terminal DB state is then committed.
Missing-row jobs do not require creating substitute session rows or new tables.
Remaining Kubernetes objects and root state form the durable retry record.

## Failures and operator review

Failures are logged by session ID and retried from actual resources on the next
pass, including after controller restart. Failure in one candidate does not skip
the others. A gateway outage prevents pod deletion; pod deletion failure prevents
policy removal and forgetting its source block. A failed final inventory or
forget operation is retried. Inventory reports counts of cleaned, preserved,
pending and ignored objects in backend logs.

Ignored resources may include benign unrelated infrastructure. Pending resources
with changing identity/labels, finalizers, disconnected nodes, or reused pod IPs
need operator review. Inspect ownership and node/container state before resolving
them. API object absence is not independent proof of process termination after
an administrator force-deletes a pod; force deletion is outside this controller's
cleanup procedure. Do not remove source blocks to hide a stuck cleanup.

External alerts for repeated failures, orphan age and stuck terminating pods remain
an operations task. This sweep is not a cluster-wide garbage collector, does not
scan other namespaces, and does not resolve safe account deletion/address reuse.

## Rollout and validation

1. Deploy the player-isolation and VPN-revocation prerequisites described in
   [player-isolation.md](player-isolation.md) and [vpn-revocation.md](vpn-revocation.md).
   Keep unrestricted registration closed until live acceptance passes.
2. Install the updated root gateway helper and sudoers example. The new read-only
   `mirrage-session-access inventory` operation returns public session/IP/expiry
   bindings under the existing protected root lock. Verify it works as the actual
   backend service account before restarting the backend. It returns no VPN keys,
   profiles, CA material or credentials.
3. Retain the dedicated namespace controller RBAC in
   `infrastructure/kubernetes/backend-isolation-rbac.yaml`: pods and policies already
   have the required get/list/delete permissions. No broader permission is added.
4. Review existing resources for ownership labels and select the intended
   `K8S_NAMESPACE`. Mixed namespaces or legacy pods need a deliberate migration;
   the sweep skips resources it cannot identify safely.
5. In staging, keep player A's session active while leaving player B's test pod,
   policy and gateway binding with its database session record deliberately removed.
   Restart the backend. Confirm only B's resources disappear and A still works.
   Repeat for a policy-only and gateway-only leftover, an expired row, an in-flight
   start, a failed Kubernetes delete and a gateway outage. Confirm retries preserve
   blocking until pod disappearance. Test a changed UID/version between inventory
   and deletion and confirm the replacement is not deleted by that attempt.

The staging deletion scenario uses disposable accounts/resources only; no test in
this implementation removed a production record or queried live Kubernetes.

Run the reproducible full suite from the repository root:

```bash
python3 backend/scripts/check_backend_postgres.py
```

For focused tests, append `backend/tests/test_orphan_cleanup.py`. The runner uses
mock Kubernetes/VPN and temporary SQLite plus network-isolated PostgreSQL for
concurrency cases. Production settings are not inherited. The real nftables
gateway check also exercises inventory of revoked entries and forgetting them,
inside the disposable container documented in `player-isolation.md`.

The new implementation is in `backend/app/services/orphan_cleanup.py`, resource
identity validation in `session_resources.py`, and conditional inventory/deletion
in `k8s_service.py`. No database schema change is required for this sweep.

Validated on 2026-11-20: the 195-test backend suite passed with PostgreSQL enabled.
After the final graceful-deletion and fresh-binding adjustments, all 41 focused
lifecycle checks passed. The isolated real-nftables test, Python compilation and
whitespace checks passed. Live staging/production acceptance remains pending.

Kubernetes documents conditional deletion and list consistency in its
[API reference](https://kubernetes.io/docs/reference/generated/kubernetes-api/v1.34/)
and [API concepts](https://kubernetes.io/docs/reference/using-api/api-concepts/).
