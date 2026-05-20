#!/usr/bin/env bash
# Install keepalive cron jobs for this VM.
# Called during setup (cloud-init or bootstrap) with the VM's env file as $1.
#
# These run as user crontab jobs (no sudo needed) and provide:
#   - Every 4h:  health_check.py — system stats + ntfy heartbeat
#   - Daily 2:30: log_rotate.sh  — compress/prune logs (CPU activity)
#   - Daily 6:00: fleet_report.py — full fleet status via ntfy (management only)
#
# The regular CPU bursts from these jobs satisfy Oracle's Always Free
# idle-reclamation policy without fake load.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${1:-}"

echo "[keepalive] Installing cron jobs from $SCRIPT_DIR"
mkdir -p "$HOME/cloud-lab/logs"

# Helper: add a crontab entry if not already present (idempotent).
add_cron() {
    local entry="$1"
    ( crontab -l 2>/dev/null; echo "$entry" ) | sort -u | crontab -
}

add_cron "0 */4 * * * python3 $SCRIPT_DIR/health_check.py >> $HOME/cloud-lab/logs/keepalive.log 2>&1"
add_cron "30 2 * * * bash $SCRIPT_DIR/log_rotate.sh >> $HOME/cloud-lab/logs/keepalive.log 2>&1"
add_cron "0 6 * * * python3 $SCRIPT_DIR/fleet_report.py >> $HOME/cloud-lab/logs/keepalive.log 2>&1"

echo "[keepalive] Cron jobs installed:"
crontab -l | grep "cloud-lab"
