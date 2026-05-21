#!/usr/bin/env bash
# laboratory role setup (the A1 Flex instance).
# Installs: heartbeat timer, crosswatch timer, self-update timer, MDA dashboard service.
# Safe to re-run.
#
# The laboratory is your big compute canvas. For MDA it immediately hosts the dashboard.
set -euo pipefail

TOOLS_DIR="${TOOLS_DIR:-$HOME/cloud-lab}"
ENV_FILE="${ENV_FILE:-$HOME/.config/cloud-lab/laboratory.env}"
PYTHON="${PYTHON:-python3}"

SRC="$TOOLS_DIR/fleet/laboratory"

is_real_value() {
    local value="${1:-}"
    [[ -n "$value" && "$value" != *'${'* ]]
}

# ── heartbeat timer (→ management console, every 4 h) ────────────────────────
cat > /tmp/cloud-lab-heartbeat.service <<SERVICE
[Unit]
Description=Cloud Lab laboratory heartbeat — POSTs liveness to management console

[Service]
User=ubuntu
Type=oneshot
EnvironmentFile=${ENV_FILE}
WorkingDirectory=${TOOLS_DIR}
ExecStart=${PYTHON} ${SRC}/heartbeat.py
Environment=PYTHONUNBUFFERED=1
SERVICE

cat > /tmp/cloud-lab-heartbeat.timer <<TIMER
[Unit]
Description=Cloud Lab laboratory heartbeat — every 4 hours

[Timer]
OnBootSec=5min
OnUnitActiveSec=4h
Persistent=true

[Install]
WantedBy=timers.target
TIMER
sudo mv /tmp/cloud-lab-heartbeat.service /etc/systemd/system/cloud-lab-heartbeat.service
sudo mv /tmp/cloud-lab-heartbeat.timer   /etc/systemd/system/cloud-lab-heartbeat.timer

# ── cross-watch timer (every 6 h) ─────────────────────────────────────────────
cat > /tmp/cloud-lab-crosswatch.service <<SERVICE
[Unit]
Description=Cloud Lab cross-watch — checks peer VMs, reports anomalies to management

[Service]
User=ubuntu
Type=oneshot
EnvironmentFile=${ENV_FILE}
Environment=OCI_AUTH_MODE=instance_principal
WorkingDirectory=${TOOLS_DIR}
ExecStart=${PYTHON} ${SRC}/crosswatch.py
Environment=PYTHONUNBUFFERED=1
SERVICE

cat > /tmp/cloud-lab-crosswatch.timer <<TIMER
[Unit]
Description=Cloud Lab cross-watch — every 6 hours

[Timer]
OnBootSec=12min
OnUnitActiveSec=6h
Persistent=true

[Install]
WantedBy=timers.target
TIMER
sudo mv /tmp/cloud-lab-crosswatch.service /etc/systemd/system/cloud-lab-crosswatch.service
sudo mv /tmp/cloud-lab-crosswatch.timer   /etc/systemd/system/cloud-lab-crosswatch.timer

# ── nightly self-update ───────────────────────────────────────────────────────
cat > /tmp/cloud-lab-update.service <<SERVICE
[Unit]
Description=Cloud Lab self-update — git pull fleet repo

[Service]
User=ubuntu
Type=oneshot
WorkingDirectory=$HOME/cloud-lab
ExecStart=/usr/bin/git pull --ff-only
SERVICE

cat > /tmp/cloud-lab-update.timer <<TIMER
[Unit]
Description=Cloud Lab self-update — nightly at 04:00

[Timer]
OnCalendar=04:00
Persistent=true

[Install]
WantedBy=timers.target
TIMER
sudo mv /tmp/cloud-lab-update.service /etc/systemd/system/cloud-lab-update.service
sudo mv /tmp/cloud-lab-update.timer   /etc/systemd/system/cloud-lab-update.timer

# ── MDA dashboard workload ───────────────────────────────────────────────────
set -a
source "${ENV_FILE}"
set +a

DASHBOARD_REPO="${DASHBOARD_REPO:-MountDiabloAdvisors/dashboard}"
DASHBOARD_DIR="${DASHBOARD_DIR:-$HOME/mda-dashboard}"
DASHBOARD_HOST="${DASHBOARD_HOST:-127.0.0.1}"
DASHBOARD_PORT="${DASHBOARD_PORT:-8700}"
DASHBOARD_DB_PATH="${DASHBOARD_DB_PATH:-$HOME/mda-dashboard-data/dashboard.db}"

echo "[laboratory] Installing uv for dashboard workload..."
if ! command -v uv >/dev/null 2>&1 && [ ! -x "$HOME/.local/bin/uv" ]; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
fi
UV_BIN="$(command -v uv || true)"
if [ -z "$UV_BIN" ] && [ -x "$HOME/.local/bin/uv" ]; then
    UV_BIN="$HOME/.local/bin/uv"
fi
if [ -z "$UV_BIN" ]; then
    echo "uv install failed; dashboard service cannot be installed." >&2
    exit 1
fi

echo "[laboratory] Cloning/updating MDA dashboard..."
if [ -z "${GITHUB_TOKEN:-}" ]; then
    echo "GITHUB_TOKEN missing; cannot clone private dashboard repo." >&2
    exit 1
fi
DASHBOARD_CLONE_URL="https://oauth2:${GITHUB_TOKEN}@github.com/${DASHBOARD_REPO}.git"
if [ -d "${DASHBOARD_DIR}/.git" ]; then
    git -C "${DASHBOARD_DIR}" pull --ff-only
else
    git clone "${DASHBOARD_CLONE_URL}" "${DASHBOARD_DIR}"
fi

mkdir -p "$(dirname "${DASHBOARD_DB_PATH}")"
cat > "${DASHBOARD_DIR}/.env" <<DASHENV
DB_PATH=${DASHBOARD_DB_PATH}
SCHWAB_CALLBACK_URL=http://${DASHBOARD_HOST}:${DASHBOARD_PORT}/api/schwab/accounts/callback
SCHWAB_MARKET_CALLBACK_URL=http://${DASHBOARD_HOST}:${DASHBOARD_PORT}/api/schwab/market/callback
PLAID_ENV=sandbox
DASHENV
chmod 600 "${DASHBOARD_DIR}/.env"

append_dashboard_secret() {
    local source_key="$1" target_key="$2"
    local value="${!source_key:-}"
    if is_real_value "$value"; then
        printf '%s=%s\n' "$target_key" "$value" >> "${DASHBOARD_DIR}/.env"
    fi
}

append_dashboard_secret DASHBOARD_DATABASE_URL DATABASE_URL
append_dashboard_secret DASHBOARD_SCHWAB_APP_KEY SCHWAB_APP_KEY
append_dashboard_secret DASHBOARD_SCHWAB_APP_SECRET SCHWAB_APP_SECRET
append_dashboard_secret DASHBOARD_SCHWAB_MARKET_APP_KEY SCHWAB_MARKET_APP_KEY
append_dashboard_secret DASHBOARD_SCHWAB_MARKET_APP_SECRET SCHWAB_MARKET_APP_SECRET
append_dashboard_secret DASHBOARD_PLAID_CLIENT_ID PLAID_CLIENT_ID
append_dashboard_secret DASHBOARD_PLAID_SECRET PLAID_SECRET
append_dashboard_secret DASHBOARD_PLAID_ENV PLAID_ENV
append_dashboard_secret DASHBOARD_COINGECKO_API_KEY COINGECKO_API_KEY

echo "[laboratory] Syncing dashboard dependencies..."
cd "${DASHBOARD_DIR}"
"${UV_BIN}" sync

cat > /tmp/mda-dashboard.service <<SERVICE
[Unit]
Description=MDA Dashboard — private finance dashboard on laboratory
After=network-online.target
Wants=network-online.target

[Service]
User=ubuntu
Type=simple
WorkingDirectory=${DASHBOARD_DIR}
Environment=PATH=/home/ubuntu/.local/bin:/usr/local/bin:/usr/bin:/bin
ExecStart=${UV_BIN} run uvicorn backend.app:app --host ${DASHBOARD_HOST} --port ${DASHBOARD_PORT}
Restart=always
RestartSec=15
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
SERVICE
sudo mv /tmp/mda-dashboard.service /etc/systemd/system/mda-dashboard.service

cat > /tmp/mda-dashboard-ping.service <<SERVICE
[Unit]
Description=MDA Dashboard health ping — exercises the local dashboard workload

[Service]
User=ubuntu
Type=oneshot
ExecStart=/usr/bin/curl -fsS http://${DASHBOARD_HOST}:${DASHBOARD_PORT}/api/summary
SERVICE

cat > /tmp/mda-dashboard-ping.timer <<TIMER
[Unit]
Description=MDA Dashboard health ping — every 30 minutes

[Timer]
OnBootSec=10min
OnUnitActiveSec=30min
Persistent=true

[Install]
WantedBy=timers.target
TIMER
sudo mv /tmp/mda-dashboard-ping.service /etc/systemd/system/mda-dashboard-ping.service
sudo mv /tmp/mda-dashboard-ping.timer   /etc/systemd/system/mda-dashboard-ping.timer

# ── enable and start ──────────────────────────────────────────────────────────
sudo systemctl daemon-reload
sudo systemctl enable cloud-lab-heartbeat.timer cloud-lab-crosswatch.timer cloud-lab-update.timer mda-dashboard-ping.timer mda-dashboard
sudo systemctl restart mda-dashboard
sudo systemctl start  cloud-lab-heartbeat.timer cloud-lab-crosswatch.timer cloud-lab-update.timer mda-dashboard-ping.timer

echo ""
echo "laboratory role installed."
echo "Timers: cloud-lab-heartbeat (4h -> management), cloud-lab-crosswatch (6h -> management), cloud-lab-update (nightly), mda-dashboard-ping (30m)"
echo "Services: mda-dashboard at http://${DASHBOARD_HOST}:${DASHBOARD_PORT}"
echo ""
echo "Access dashboard with: ssh -L 8700:${DASHBOARD_HOST}:${DASHBOARD_PORT} ubuntu@<laboratory-public-ip>"
