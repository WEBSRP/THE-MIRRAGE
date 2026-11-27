#!/bin/bash
set -euo pipefail

pids=()

stop_services() {
    if ((${#pids[@]})); then
        kill -- "${pids[@]}" 2>/dev/null || true
        wait "${pids[@]}" 2>/dev/null || true
    fi
}

trap stop_services EXIT
trap 'exit 0' TERM INT

# SSH is available to developers who provision a public key at deployment.
developer_key=${CTF_DEVELOPER_SSH_PUBLIC_KEY:-}
unset CTF_DEVELOPER_SSH_PUBLIC_KEY
if [[ -n $developer_key ]]; then
    if [[ $developer_key = *$'\n'* || $developer_key = *$'\r'* ]] ||
        [[ ! $developer_key =~ ^[a-zA-Z0-9@._+-]+[[:blank:]]+[a-zA-Z0-9+/]+=*([[:blank:]]|$) ]]; then
        printf '%s\n' 'Expected one OpenSSH public key for developer access' >&2
        exit 1
    fi
    install -d -m 0755 /run/sshd /etc/ssh/authorized_keys
    printf '%s\n' "$developer_key" > /etc/ssh/authorized_keys/player
    chmod 0644 /etc/ssh/authorized_keys/player
    ssh-keygen -lf /etc/ssh/authorized_keys/player >/dev/null
    ssh-keygen -A
    /usr/sbin/sshd -t -f /etc/ssh/sshd_config.mirrage
    /usr/sbin/sshd -D -e -f /etc/ssh/sshd_config.mirrage &
    pids+=("$!")
fi

cron -f &
pids+=("$!")
setpriv --reuid www-data --regid www-data --init-groups python3 -u /opt/ctf/backend/server.py &
pids+=("$!")
nginx -g 'daemon off;' &
pids+=("$!")

wait -n -p stopped "${pids[@]}" || status=$?
printf 'Required CTF service (PID %s) exited with status %s\n' "${stopped:-unknown}" "${status:-0}" >&2
exit 1
