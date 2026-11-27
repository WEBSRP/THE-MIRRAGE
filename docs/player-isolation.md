# Player network isolation

This implementation supports the repository's **single-node, IPv4 k3s deployment**:
OpenVPN, the gateway guard, backend systemd service, and player pods run on the same
EC2 node. Live recovery preparation on 2026-11-21 installed the guard/helpers,
controller identity and default-deny policy. RDS/reservation migration and VPN
cutover subsequently completed for nine existing real profiles; backend startup
and real two-player acceptance remain pending. See
[live-otp-recovery.md](live-otp-recovery.md). Drain existing sessions and
VPN connections before rollout; do not roll out mixed old/new backend workers.

## Access contract

- Each real certificate has a stable IPv4 reservation in `vpn_address_reservations`.
  Database uniqueness covers address, user, and certificate identity, including
  concurrent API workers. Reservations are persisted before certificate/CCD work,
  so a failed operation cannot give that address to a different certificate.
- Reservations are not recycled on certificate revocation. Before deleting a user
  and its cascading reservation, revoke the certificate, disconnect the client,
  remove its CCD and drain its sessions. Do not reuse an address while an old
  certificate/connection can still use it.
- OpenVPN uses `topology subnet`, `nopool`, `ccd-exclusive`, no `client-to-client`,
  and no `duplicate-cn`. The root-owned learn-address hook accepts only the IP in
  the authenticated certificate's CCD. Extra source IPs, routed client subnets,
  symlink CCDs and IPv6 addresses are rejected. DCO is disabled so this path and
  the `tun0` firewall boundary remain explicit.
- Every pod is pinned to `K8S_SESSION_NODE_NAME`, the node named in the root guard
  configuration. A missing configured kubeconfig fails instead of falling back
  to the node's administrator credentials.
- A namespace-wide default-deny policy selects all pods. The API installs a
  per-session policy **before** creating the pod. It selects both session and user
  labels and allows only the owner's `/32` into TCP 22, 80 and 2222.
- Pod-initiated outbound traffic is limited to the owner's IPv4 address on TCP
  callback ports (default 4444). Set `SESSION_CALLBACK_PORTS=[]` to disable callbacks.
  DNS/internet egress is denied by default. Replies to allowed requests work.
- The provisioner refuses broad or unknown additive NetworkPolicies. It will not
  silently keep the previous whole-VPN-subnet policy or replace it on a live cluster.
- The root gateway guard independently allows only active `(VPN IP, pod IP)` pairs.
  It blocks VPN access to host services, peer VPN clients and unrelated destinations,
  and blocks registered sandboxes from initiating host/other-network connections.
  It drops IPv6 entering the VPN and pod bridge; bridge netfilter must be enabled.
- Over the VPN, a player can run `ping -c 4 <assigned-pod-ip>` while their lease
  is active. The gateway allows IPv4 echo traffic to the assigned pod at two
  requests per second with an initial burst of four, capped at 576 bytes per
  IPv4 packet. Only replies to those requests can return to the player. Verify
  echo forwarding when changing the cluster network plugin.
- nftables set elements expire automatically at the committed session deadline.
  This does not depend on browser polling or the cleanup worker being alive.

The backend still uses the three shared flags described in [shared-flags.md](shared-flags.md).
IP routing and route advertisements alone do not enforce this access contract.

## Session lifecycle

1. Reserve the player's VPN address and write the private CCD atomically (0640).
2. Reserve a session slot and persist the deterministic pod name before creation.
3. Verify the namespace guard, install the owner policy, create the pod and wait.
4. Install a time-limited gateway binding, then commit `READY` and return the target.
5. On stop/expiry/failure, mark `STOPPING`, revoke the gateway pair, confirm the pod
   is gone, remove its policy and forget its gateway record. Only then release the slot.

Cleanup failures remain `STOPPING`, hide target addresses and retain capacity;
the worker retries. Source blocking for an orphaned pod remains after revocation.
The policy also has a pod owner reference for Kubernetes garbage collection.
An interrupted initial provisioning is cleaned after its three-minute deadline;
status polling cannot promote it to `READY` before the first gateway grant.

Extension commits the later database deadline before renewing the kernel lease.
`renew` cannot recreate revoked/expired access, and out-of-order renewals cannot
shorten a newer lease. This prevents stop/renew races and a kernel lease longer
than the persisted session after a controller crash. Failed/ambiguous renewals
revoke when possible and mark the session for cleanup, rather than reporting success.

## Files and privileges

| Component | Location after installation | Owner/access |
| --- | --- | --- |
| Root helper | `/usr/local/sbin/mirrage-session-access` | root:root 0755 |
| Guard configuration | `/etc/mirrage/player-isolation.json` | root:root 0644 |
| Guard state and lock | `/var/lib/mirrage/player-guard/` | root:root 0700 |
| Learn-address hook | `/usr/local/lib/mirrage/learn_address.py` | root:root 0755 |
| CCD directory | `/var/lib/mirrage/openvpn/ccd/` | Backend writable; OpenVPN readable |
| Backend kubeconfig | Explicit `K8S_KUBECONFIG_PATH` | Dedicated controller identity |

The helper accepts only `check`, `inventory`, `status`, `grant`, `renew`, `revoke`, `forget` and operator
`install`. It validates session IDs, both address ranges, address bindings and lease
duration, calls nft with an argument list/stdin (no shell), and updates only its own
`inet mirrage_player_guard` table. It never flushes the host ruleset or k3s chains.
It uses a root-only file lock and atomically saved state. The backend does not get
general nft/iptables or shell sudo privileges. The example sudoers file permits
only controller operations, not `install` or arbitrary command paths.

The production gateway adapter runs on the EC2 host with systemd. An unprivileged
Docker backend cannot call this host helper without a separately designed broker;
do not give the backend container host networking, privileged mode or NET_ADMIN
as a shortcut. Development/mock Docker usage remains supported.

## Rollout procedure (operator action, not run by implementation)

1. Take database and configuration backups. Keep a separate SSH/admin connection
   that does not depend on the player VPN. Pause new sessions, stop/drain existing
   pods and disconnect old VPN clients. This is necessary when moving from dynamic
   VPN addresses to reserved CCD assignments and replacing the permissive policy.

2. Confirm OpenVPN 2.6+ and the node's actual interface/name/CIDRs:

   ```bash
   openvpn --version
   ip -br link
   kubectl get nodes
   kubectl get networkpolicies -n mirrage-sessions
   ```

   Use the exact k3s node name and the correct pod bridge (normally `cni0`). Do not
   assume that existence of a NetworkPolicy proves its CNI enforcement. No public
   app-server or new EC2 ingress port is needed for this change.

3. Install the helper, configuration and hooks. These examples match the repository's
   backend service user `admin` and an OpenVPN process running as root. If OpenVPN
   drops privileges, use its runtime group for the CCD directory/files and verify
   it can read the hook, CCDs and public CRL without granting access to private keys.

   ```bash
   sudo install -d -o root -g root -m 0755 /etc/mirrage /usr/local/lib/mirrage
   sudo install -d -o root -g root -m 0755 /var/lib/mirrage/openvpn
   sudo install -d -o admin -g root -m 2750 /var/lib/mirrage/openvpn/ccd
   sudo install -o root -g root -m 0755 infrastructure/openvpn/session_access.py /usr/local/sbin/mirrage-session-access
   sudo install -o root -g root -m 0755 infrastructure/openvpn/learn_address.py /usr/local/lib/mirrage/learn_address.py
   sudo install -o root -g root -m 0644 infrastructure/openvpn/player-isolation.example.json /etc/mirrage/player-isolation.json
   sudo install -o root -g root -m 0644 infrastructure/openvpn/99-mirrage-player-guard.conf.example /etc/sysctl.d/99-mirrage-player-guard.conf
   ```

   Edit `/etc/mirrage/player-isolation.json`: replace `node_name`, verify both
   interfaces/CIDRs, callbacks and maximum lease (18000 seconds for five hours).
   The backend settings must match. Do not enable this template on a multi-node or
   dual-stack deployment without designing the equivalent enforcement on every node.

4. Install and validate the restricted sudoers file. Replace `admin` if needed:

   ```bash
   sudo install -o root -g root -m 0440 infrastructure/openvpn/mirrage-player-guard.sudoers.example /etc/sudoers.d/mirrage-player-guard
   sudo visudo -cf /etc/sudoers.d/mirrage-player-guard
   ```

5. Install the guard service, apply sysctls and start it before enabling player VPN:

   ```bash
   sudo install -m 0644 infrastructure/systemd/mirrage-player-guard.service.example /etc/systemd/system/mirrage-player-guard.service
   sudo install -d /etc/systemd/system/openvpn-server@server.service.d
   sudo install -m 0644 infrastructure/systemd/openvpn-player-guard.conf.example /etc/systemd/system/openvpn-server@server.service.d/player-guard.conf
   sudo systemctl daemon-reload
   sudo systemctl enable --now mirrage-player-guard
   sudo /usr/local/sbin/mirrage-session-access check
   ```

   Merge the guard dependency into the backend unit too. The guard clears saved
   permissions on install/restart (pod IPs might have changed), retaining source
   blocking. The API startup/cleanup worker or status polling verifies current pod
   ownership and restores only still-active sessions. Restarting the guard can
   temporarily interrupt connections until that reconciliation runs. Do not use another firewall service that
   subsequently flushes all tables; losing the guard must be treated as an outage.

6. Set these in the private backend environment:

   ```dotenv
   VPN_MODE=production
   K8S_MODE=production
   K8S_SESSION_NODE_NAME=your-exact-k3s-node-name
   K8S_KUBECONFIG_PATH=/private/path/to/controller-kubeconfig
   VPN_CLIENT_CIDR=10.8.0.0/24
   VPN_CLIENT_IP_START=10.8.0.10
   VPN_CLIENT_IP_END=10.8.0.250
   OPENVPN_CCD_DIR=/var/lib/mirrage/openvpn/ccd
   OPENVPN_TUN_INTERFACE=tun0
   SESSION_POD_CIDR=10.42.0.0/16
   SESSION_POD_INTERFACE=cni0
   SESSION_CALLBACK_PORTS=[4444]
   SESSION_GATEWAY_HELPER=/usr/local/sbin/mirrage-session-access
   ```

   Use a controller kubeconfig instead of the k3s administrator config. The supplied
   `infrastructure/kubernetes/backend-isolation-rbac.yaml` grants a User identity
   named `mirrage-backend` the required namespace-scoped rights plus read access to
   that namespace. Create its authentication credentials separately using your
   cluster's certificate/identity process; a RoleBinding does not create credentials.

7. Pre-create the namespace if needed, then apply the **replacement** default-deny
   policy and controller RBAC. Remove any other broad policies in this dedicated
   namespace after review; policies are additive and the new backend refuses them.

   ```bash
   kubectl apply -f infrastructure/kubernetes/network-policy.yaml
   kubectl apply -f infrastructure/kubernetes/backend-isolation-rbac.yaml
   ```

   Do not apply `mirage-ctf-pod.yaml` as a normal player launch: the API adds the
   owner policy, node binding, flag revision and gateway lease as one workflow.

8. While the API is stopped, prepare existing active real profiles. The first
   command is read-only. The second requires the database already migrated to head
   and writes reservations/CCDs;
   it keeps existing real certificate names/profile contents and skips mocks and
   revoked accounts. `K8S_MODE=mock` here only prevents kubeconfig loading for this
   offline management command; real VPN allocation remains enabled.

   ```bash
   K8S_MODE=mock PYTHONPATH=. backend/.venv/bin/python backend/scripts/prepare_vpn_isolation.py
   K8S_MODE=mock PYTHONPATH=. backend/.venv/bin/python backend/scripts/prepare_vpn_isolation.py --apply
   ```

   New verified users get reservations automatically. The default pool has 241
   addresses and is finite; expand the subnet/pool deliberately before capacity is
   exhausted. Changing a user's reservation requires coordinated certificate/CCD,
   client disconnect and session teardown; do not edit it while a session is active.

9. Merge `infrastructure/openvpn/server.conf.example` into the real server config.
   Retain real certificate/key paths. Ensure the TLS-crypt key and a current CRL
   exist at their configured locations and are readable by the server.
   Follow [vpn-revocation.md](vpn-revocation.md) for verified CRL publication,
   targeted disconnects and refresh maintenance; these require separate rollout steps.

   Restart OpenVPN during maintenance, then start the updated backend. Production
   startup refuses a missing/mismatched gateway, mock VPN for real sessions, missing
   node name, or missing controller kubeconfig. Do not restore the old permissive
   policy as a connectivity workaround.

## Required deployment acceptance test

Use two separately issued certificates and two active player sessions:

| Test | Required result |
| --- | --- |
| A -> A target on 22, 80, 2222 | Connects |
| A -> B target, and B -> A target | Blocked |
| A -> B workstation | Blocked |
| A -> EC2 API, SSH, Kubernetes API, database | Blocked through VPN |
| A pod -> A workstation TCP 4444 | Connects if callbacks enabled |
| A pod -> B workstation / internet / metadata / host | Blocked |
| A pod -> B pod, including direct same-bridge traffic | Blocked |
| Spoof B's VPN source address using A's certificate | Rejected by OpenVPN learning hook |
| Reconnect A | Same reserved address; access still owner-only |
| Stop/expire A | Existing and new connections close; B stays connected |
| Concurrent stop and extend | No access resurrection |
| Gateway/helper unavailable | No new READY session; failed cleanup retains slot |
| IPv6/link-local access from player/pod | Blocked |

Confirm packet source addresses and guard counters on the actual node. Check IPv4
and IPv6 bridge filtering sysctls and CNI enforcement; the isolated tests below
cannot prove your deployed routing/NAT, OpenVPN options or CNI configuration.

## Automated validation

Backend tests cover allocation races (including PostgreSQL without a shared process
lock), CCDs, source-learning rejection, policy ordering/cleanup, rejection of broad
policies, grant failures, cleanup retries and renewals. Tests use temporary files,
databases and mock Kubernetes; they never edit the live host firewall.

To test nftables installation and actual packet filtering in disposable containers:

```bash
docker build -t mirrage-ctf:shared-flags-check containers/ctf
docker build -f infrastructure/openvpn/guard-test.Dockerfile -t mirrage-player-guard:check .
docker run --rm --network none --cap-add NET_ADMIN --mount type=bind,source="$PWD/infrastructure/openvpn",target=/checks,readonly --entrypoint python3 mirrage-player-guard:check /checks/check_guard_runtime.py
python3 backend/scripts/check_player_network.py
```

The packet harness creates benchmark-address Docker bridges, disables NAT, removes
all test-container default routes, and cleans up its five containers and two
networks. It simulates the VPN interface, not an authenticated OpenVPN connection.
It does not create or modify the production `mirrage_player_guard` table.

On a running gateway, run the new helper with `sudo /path/to/staged-helper upgrade`
before replacing `/usr/local/sbin/mirrage-session-access`. The upgrade applies the
ping rules in one transaction and leaves the active lease deadlines intact.

Validated on 2026-11-20: 149 backend tests passed with the PostgreSQL cases enabled;
the isolated real-nftables helper checks and two-player packet harness both passed.
The live OpenVPN/CNI acceptance matrix above has not been run.

## Remaining work

Targeted admin certificate revocation, active-client disconnect and CRL publication/expiry
maintenance are implemented in source; see [vpn-revocation.md](vpn-revocation.md). Their
live rollout and acceptance tests remain pending. Namespace resource cleanup now also
finds pods/policies/gateway bindings lacking DB rows; see [orphan-cleanup.md](orphan-cleanup.md).
Multi-node/dual-stack isolation and live acceptance remain separate tasks. Keep the two-client acceptance test as a release gate, not a documentation claim.

References: [OpenVPN server options](https://openvpn.net/community-docs/community-articles/openvpn-2-6-manual/),
[Kubernetes NetworkPolicies](https://kubernetes.io/docs/concepts/services-networking/network-policies/),
[nftables reference](https://netfilter.org/projects/nftables/manpage.html).
