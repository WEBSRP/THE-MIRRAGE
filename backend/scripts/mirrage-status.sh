#!/usr/bin/env bash

set -u

# ============================================================
# MIRRAGE Kubernetes / Cluster / VPN Status Diagnostic Script
# Safe for operational inspection and installation under /usr/local/bin
# ============================================================

# Auto-detect kubectl execution method (with sudo fallback for local socket permissions)
KUBECTL="kubectl"
if ! kubectl version --client >/dev/null 2>&1; then
    if command -v sudo >/dev/null 2>&1 && sudo kubectl version --client >/dev/null 2>&1; then
        KUBECTL="sudo kubectl"
    fi
elif ! kubectl get nodes >/dev/null 2>&1; then
    if command -v sudo >/dev/null 2>&1 && sudo kubectl get nodes >/dev/null 2>&1; then
        KUBECTL="sudo kubectl"
    fi
fi

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                    MIRRAGE STATUS                           ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo

# ------------------------------------------------------------
# 1. Kubernetes API & Cluster Nodes
# ------------------------------------------------------------
echo "┌─ KUBERNETES CLUSTER & NODES"
echo "│"

if ! $KUBECTL get nodes >/dev/null 2>&1; then
    echo "│ [!] Kubernetes API is not reachable or permission denied"
else
    $KUBECTL get nodes \
        -o custom-columns='│ NODE:.metadata.name,STATUS:.status.conditions[-1].type,ROLES:.metadata.labels.node-role\.kubernetes\.io/control-plane,INTERNAL-IP:.status.addresses[?(@.type=="InternalIP")].address,VERSION:.status.nodeInfo.kubeletVersion' \
        --no-headers 2>/dev/null | sed 's/^/│ /' || echo "│ Unable to read nodes"
fi

echo "│"
echo "└──────────────────────────────────────────────────────────────"
echo

# ------------------------------------------------------------
# 2. Cluster Resource Metrics (metrics-server)
# ------------------------------------------------------------
echo "┌─ RESOURCE USAGE (METRICS-SERVER)"
echo "│"

if $KUBECTL top nodes >/dev/null 2>&1; then
    $KUBECTL top nodes 2>/dev/null | sed 's/^/│ /'
    echo "│"
    $KUBECTL top pods -A --sort-by=cpu 2>/dev/null | head -n 6 | sed 's/^/│ /'
else
    echo "│ metrics-server not available or still collecting data (informational)"
fi

echo "│"
echo "└──────────────────────────────────────────────────────────────"
echo

# ------------------------------------------------------------
# 3. MIRRAGE Active Player Sessions & Pod Lifecycle
# ------------------------------------------------------------
echo "┌─ MIRRAGE PLAYER SESSIONS & RECONCILIATION"
echo "│"

# 3a. Active Sessions from Database
PYTHON_BIN="/home/admin/THE-MIRRAGE/backend/.venv/bin/python3"
PROJECT_DIR="/home/admin/THE-MIRRAGE"
DB_SESSIONS=""

if [ -x "$PYTHON_BIN" ]; then
    DB_SESSIONS=$(PYTHONPATH="$PROJECT_DIR" "$PYTHON_BIN" -c "
import asyncio
from backend.app.core.database import AsyncSessionLocal
from backend.app.models.session import GameSession, SessionStatus
from sqlalchemy import select

async def main():
    try:
        async with AsyncSessionLocal() as db:
            res = await db.execute(select(GameSession).where(GameSession.status.in_([
                SessionStatus.PENDING, SessionStatus.INITIALIZING, SessionStatus.PROVISIONING, SessionStatus.READY
            ])))
            sessions = res.scalars().all()
            for s in sessions:
                print(f'{s.id}|{s.user_id}|{s.status.value}|{s.pod_name or \"-\"}|{s.mirage_ip or \"-\"}')
    except Exception as e:
        pass

asyncio.run(main())
" 2>/dev/null || true)
fi

echo "│ • Database Sessions (Active in DB):"
if [ -z "$DB_SESSIONS" ]; then
    echo "│   No active sessions recorded in database."
else
    printf "│   %-18s %-14s %-28s %-16s\n" "SESSION ID" "STATUS" "POD NAME" "TARGET IP"
    echo "│   ---------------------------------------------------------------------------------"
    echo "$DB_SESSIONS" | while IFS='|' read -r sid uid status pod ip; do
        printf "│   %-18s %-14s %-28s %-16s\n" "$sid" "$status" "$pod" "$ip"
    done
fi

echo "│"
echo "│ • Kubernetes Session Pods (Live on Cluster):"
SESSION_PODS=$($KUBECTL get pods -A -l app=mirrage-session --no-headers 2>/dev/null || true)
if [ -z "$SESSION_PODS" ]; then
    SESSION_PODS=$($KUBECTL get pods -A --no-headers 2>/dev/null | grep -E "player-" || true)
fi

POD_NAMES=""
if [ -z "$SESSION_PODS" ]; then
    echo "│   Zero active player pods (Cluster idle - Ready for incoming players)"
else
    printf "│   %-14s %-28s %-8s %-12s %-16s %s\n" \
        "NAMESPACE" "POD NAME" "READY" "STATUS" "POD IP" "NODE"
    echo "│   ---------------------------------------------------------------------------------"

    echo "$SESSION_PODS" | while read -r line; do
        ns=$(echo "$line" | awk '{print $1}')
        name=$(echo "$line" | awk '{print $2}')
        ready=$(echo "$line" | awk '{print $3}')
        status=$(echo "$line" | awk '{print $4}')
        ip=$($KUBECTL get pod "$name" -n "$ns" -o jsonpath='{.status.podIP}' 2>/dev/null || echo "-")
        node=$($KUBECTL get pod "$name" -n "$ns" -o jsonpath='{.spec.nodeName}' 2>/dev/null || echo "-")

        printf "│   %-14s %-28s %-8s %-12s %-16s %s\n" \
            "$ns" "$name" "$ready" "$status" "${ip:-"-"}" "${node:-"-"}"
    done
fi

# 3c. Consistency & Reconciliation Analysis
echo "│"
echo "│ • State Consistency Analysis:"
INCONSISTENCY_FOUND=0

if [ -n "$DB_SESSIONS" ]; then
    while IFS='|' read -r sid uid status pod ip; do
        [ -z "$sid" ] && continue
        if [ "$pod" = "-" ] || [ -z "$pod" ]; then
            echo "│   [!] INCONSISTENCY: Session $sid has DB status '$status' but no Kubernetes pod allocated."
            INCONSISTENCY_FOUND=1
        else
            pod_exists=$(echo "$SESSION_PODS" | awk '{print $2}' | grep -Fx "$pod" || true)
            if [ -z "$pod_exists" ]; then
                pod_exists=$($KUBECTL get pods -A --no-headers 2>/dev/null | awk '{print $2}' | grep -Fx "$pod" || true)
            fi
            if [ -z "$pod_exists" ]; then
                if [ "$status" = "ready" ]; then
                    echo "│   [!] STALE SESSION: DB says READY for session $sid ($ip) but pod $pod DOES NOT EXIST in Kubernetes!"
                else
                    echo "│   [!] ORPHANED DB SESSION: DB says '$status' for session $sid but pod $pod does not exist in Kubernetes."
                fi
                INCONSISTENCY_FOUND=1
            fi
        fi
    done <<< "$DB_SESSIONS"
fi

if [ -n "$SESSION_PODS" ]; then
    while read -r line; do
        [ -z "$line" ] && continue
        pname=$(echo "$line" | awk '{print $2}')
        if [ -n "$DB_SESSIONS" ]; then
            matched=$(echo "$DB_SESSIONS" | grep -F "$pname" || true)
        else
            matched=""
        fi
        if [ -z "$matched" ]; then
            echo "│   [!] ORPHANED KUBERNETES RESOURCE: Pod $pname is running on cluster but has no active DB session."
            INCONSISTENCY_FOUND=1
        fi
    done <<< "$SESSION_PODS"
fi

if [ -z "$DB_SESSIONS" ] && [ -z "$SESSION_PODS" ]; then
    echo "│   [✓] Consistent: No active DB sessions and no active K8s pods. Cluster is cleanly idle."
elif [ "$INCONSISTENCY_FOUND" -eq 0 ]; then
    echo "│   [✓] Consistent: Database active sessions match live Kubernetes resources."
fi

echo "│"
echo "└──────────────────────────────────────────────────────────────"
echo

# ------------------------------------------------------------
# 4. EC2 → Pod Connectivity & Application TCP Ports
# ------------------------------------------------------------
echo "┌─ NETWORK & APPLICATION PORT CONNECTIVITY"
echo "│"

ACTIVE_IPS=$($KUBECTL get pods -A -l app=mirrage-session -o jsonpath='{range .items[?(@.status.phase=="Running")]}{.status.podIP}{" "}{.metadata.name}{"\n"}{end}' 2>/dev/null || true)
if [ -z "$ACTIVE_IPS" ]; then
    # Fallback to any running player pods
    ACTIVE_IPS=$($KUBECTL get pods -A -o jsonpath='{range .items[?(@.status.phase=="Running")]}{.status.podIP}{" "}{.metadata.name}{"\n"}{end}' 2>/dev/null | grep -E "player-" || true)
fi

if [ -z "$ACTIVE_IPS" ]; then
    echo "│ No running session pods to probe (TCP checks will run once a player starts an environment)"
else
    echo "$ACTIVE_IPS" | while read -r pod_ip pod_name; do
        [ -z "$pod_ip" ] && continue
        echo "│ Probing Pod: $pod_name ($pod_ip)"

        # Check TCP 22 (Mirage Honeypot SSH)
        tcp_22="FAIL"
        if command -v nc >/dev/null 2>&1; then
            if nc -z -w 2 "$pod_ip" 22 >/dev/null 2>&1; then tcp_22="OK (Listening)"; fi
        elif timeout 2 bash -c "</dev/tcp/$pod_ip/22" >/dev/null 2>&1; then
            tcp_22="OK (Listening)"
        fi
        echo "│   • Port 22   (Mirage Honeypot SSH): $tcp_22"

        # Check TCP 2222 (CTF Core Target)
        tcp_2222="FAIL"
        if command -v nc >/dev/null 2>&1; then
            if nc -z -w 2 "$pod_ip" 2222 >/dev/null 2>&1; then tcp_2222="OK (Listening)"; fi
        elif timeout 2 bash -c "</dev/tcp/$pod_ip/2222" >/dev/null 2>&1; then
            tcp_2222="OK (Listening)"
        fi
        echo "│   • Port 2222 (CTF Core Target):    $tcp_2222"

        # ICMP check (informational only; TCP above is authoritative)
        if command -v ping >/dev/null 2>&1; then
            if ping -c 1 -W 1 "$pod_ip" >/dev/null 2>&1; then
                echo "│   • ICMP Ping: REACHABLE"
            else
                echo "│   • ICMP Ping: UNREACHABLE (Note: TCP port checks above are authoritative)"
            fi
        fi
    done
fi

echo "│"
echo "└──────────────────────────────────────────────────────────────"
echo

# ------------------------------------------------------------
# 5. OpenVPN Gateway & Telemetry Status
# ------------------------------------------------------------
echo "┌─ OPENVPN GATEWAY & TELEMETRY"
echo "│"

# Check OpenVPN service
if command -v systemctl >/dev/null 2>&1; then
    vpn_unit=$(systemctl list-units --type=service 2>/dev/null | grep -oE "openvpn[-@a-zA-Z0-9_\.]*" | head -n 1 || true)
    if [ -n "$vpn_unit" ]; then
        vpn_state=$(systemctl is-active "$vpn_unit" 2>/dev/null || echo "inactive")
        echo "│ OpenVPN Service: $vpn_unit ($vpn_state)"
    else
        echo "│ OpenVPN Service: not found in systemd units"
    fi
else
    echo "│ systemctl not available"
fi

# Check OpenVPN status.log
STATUS_LOG="/var/log/openvpn/status.log"
if [ -r "$STATUS_LOG" ]; then
    CLIENT_COUNT=$(grep "^CLIENT_LIST," "$STATUS_LOG" 2>/dev/null | wc -l | tr -d ' ')
    [ -z "$CLIENT_COUNT" ] && CLIENT_COUNT=0
    echo "│ Active Connected VPN Clients: $CLIENT_COUNT"
    if [ "$CLIENT_COUNT" -gt 0 ]; then
        grep "^CLIENT_LIST," "$STATUS_LOG" 2>/dev/null | awk -F',' '{printf "│   • %s (Virtual: %s, Real: %s, Sent: %s bytes, Recv: %s bytes)\n", $2, $4, $3, $6, $5}'
    fi
elif [ -f "$STATUS_LOG" ]; then
    echo "│ OpenVPN Status Log: present but unreadable (check group permissions)"
else
    echo "│ OpenVPN Status Log: $STATUS_LOG not found"
fi

echo "│"
echo "└──────────────────────────────────────────────────────────────"
echo

# ------------------------------------------------------------
# 6. Recent Pod Events (Errors / Warnings)
# ------------------------------------------------------------
echo "┌─ RECENT CLUSTER & POD EVENTS"
echo "│"

RECENT_EVENTS=$($KUBECTL get events -A --sort-by='.lastTimestamp' 2>/dev/null | tail -n 8 | sed 's/^/│ /' || true)
if [ -n "$RECENT_EVENTS" ]; then
    echo "$RECENT_EVENTS"
else
    echo "│ No recent cluster events"
fi

echo "│"
echo "└──────────────────────────────────────────────────────────────"
echo

# ------------------------------------------------------------
# 7. Local Docker Status (if installed)
# ------------------------------------------------------------
echo "┌─ LOCAL DOCKER ENGINE"
echo "│"

if command -v docker >/dev/null 2>&1; then
    if docker ps >/dev/null 2>&1; then
        DOCKER_OUT=$(docker ps --format '│ {{.Names}}\t{{.Status}}\t{{.Ports}}' 2>/dev/null | column -t -s $'\t' || true)
        if [ -n "$DOCKER_OUT" ]; then
            echo "$DOCKER_OUT"
        else
            echo "│ No running Docker containers"
        fi
    else
        echo "│ Docker daemon not accessible by current user"
    fi
else
    echo "│ Docker CLI not installed (K3s runs containerd natively)"
fi

echo "│"
echo "└──────────────────────────────────────────────────────────────"
echo

echo "Status check completed at: $(date -u '+%Y-%m-%d %H:%M:%SZ')"
exit 0
