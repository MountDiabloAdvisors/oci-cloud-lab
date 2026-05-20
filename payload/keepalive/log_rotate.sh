#!/usr/bin/env bash
# Log rotation and compression — runs daily at 02:30 via user crontab.
#
# Compresses old log files in ~/cloud-lab/logs/ and clears stale journal entries.
# The gzip/find CPU activity helps satisfy Oracle's idle-reclamation threshold.
set -euo pipefail

LOG_DIR="$HOME/cloud-lab/logs"
mkdir -p "$LOG_DIR"

echo "[log_rotate] Starting at $(date -u '+%Y-%m-%d %H:%M UTC')"

# Compress any uncompressed logs older than 1 day.
find "$LOG_DIR" -name "*.log" -mtime +1 -not -name "*.gz" | while read -r f; do
    echo "[log_rotate] Compressing $f"
    gzip -f "$f"
done

# Delete compressed logs older than 30 days.
find "$LOG_DIR" -name "*.log.gz" -mtime +30 -delete && \
    echo "[log_rotate] Pruned logs older than 30 days."

# Vacuum systemd journal (keep last 7 days).
if command -v journalctl > /dev/null 2>&1; then
    sudo journalctl --vacuum-time=7d 2>/dev/null || true
fi

echo "[log_rotate] Done."
