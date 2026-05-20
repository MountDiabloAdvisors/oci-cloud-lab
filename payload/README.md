# payload/

The `payload/` directory is the **app layer** — code that runs on your fleet VMs
but is not part of the core fleet infrastructure.

Fleet infrastructure (systemd services, orchestrator, admin console, cross-watch)
lives in `fleet/<role>/`. The payload layer sits on top and is intentionally separate.

---

## payload/keepalive/ — included by default

Installed automatically on every VM during bootstrap.

| Script | Schedule | Purpose |
|---|---|---|
| `health_check.py` | Every 4h | System stats + ntfy heartbeat |
| `log_rotate.sh` | Daily 02:30 | Compress/prune `~/cloud-lab/logs/` |
| `fleet_report.py` | Daily 06:00 | OCI instance states + ntfy summary |

Install manually: `bash payload/keepalive/install.sh`

These jobs use real CPU (gzip, Python subprocess, OCI API calls) which satisfies
Oracle's idle-reclamation threshold without fake load.

---

## Adding your own payload

1. Create a directory under `payload/` for your project.
2. Add a `install.sh` that idempotently sets up whatever your payload needs
   (cron jobs, systemd units, application files).
3. Call your `install.sh` from `fleet/<role>/setup.sh` at the bottom of the
   "Payload layer" section, or run it manually after SSH-ing into the VM.

The keepalive payload stays in place regardless of what else you install — it
is the baseline that keeps your fleet alive and monitored.
