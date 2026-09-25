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
echo "┌─ MIRRAGE PLAYER SESSIONS"
echo "│"

SESSION_PODS=$($KUBECTL get pods -A -l app=mirrage-session --no-headers 2>/dev/null || true)
if [ -z "$SESSION_PODS" ]; then
    # Fallback search for player pods by naming pattern
    SESSION_PODS=$($KUBECTL get pods -A --no-headers 2>/dev/null | grep -E "player-" || true)
fi

if [ -z "$SESSION_PODS" ]; then
    echo "│ Zero active player sessions (Cluster idle - Ready for incoming players)"
else
    printf "│ %-14s %-28s %-8s %-12s %-16s %s\n" \
        "NAMESPACE" "POD NAME" "READY" "STATUS" "POD IP" "NODE"
    echo "│ -----------------------------------------------------------------------------------------"

    echo "$SESSION_PODS" | while read -r line; do
        ns=$(echo "$line" | awk '{print $1}')
        name=$(echo "$line" | awk '{print $2}')
        ready=$(echo "$line" | awk '{print $3}')
        status=$(echo "$line" | awk '{print $4}')
        ip=$($KUBECTL get pod "$name" -n "$ns" -o jsonpath='{.status.podIP}' 2>/dev/null || echo "-")
        node=$($KUBECTL get pod "$name" -n "$ns" -o jsonpath='{.spec.nodeName}' 2>/dev/null || echo "-")

        printf "│ %-14s %-28s %-8s %-12s %-16s %s\n" \
            "$ns" "$name" "$ready" "$status" "${ip:-"-"}" "${node:-"-"}"
    done
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
