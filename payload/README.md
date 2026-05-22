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
| `health_check.py` | Every 4h | System stats + ntfy heartbeat; alerts if disk >80%, RAM <10%, or load >2× CPU |
| `log_rotate.sh` | Daily 02:30 | Compress/prune `~/cloud-lab/logs/` |
| `fleet_report.py` | Daily 06:00 | OCI instance states + ntfy summary |

Install manually: `bash payload/keepalive/install.sh`

These jobs use real CPU (gzip, Python subprocess, OCI API calls) which satisfies
Oracle's idle-reclamation threshold without fake load.

Resource threshold alerts fire via ntfy with a 12-hour cooldown per condition —
so a temporarily full disk won't spam you, but a persistent problem will resurface.

---

## payload/queue/ — job queue runner (optional, all VMs)

A 60-second systemd timer that picks and runs the next queued job on a VM.
Jobs are stored in `~/cloud-lab/queue.json` (JSON, priority-ordered).

| File | Purpose |
|---|---|
| `queue_runner.py` | Reads the queue, runs the next pending job, writes results back |
| `install.sh` | Installs `cloud-lab-queue.timer` (fires every 60 s) |

Submit a job from the command line:
```bash
python3 ~/cloud-lab/payload/queue/queue_runner.py \
  --enqueue --label "My task" --command "bash -c 'echo hello'" --priority 3
```

Or submit remotely via the admin console: `POST /enqueue` with a JSON body and either
a session cookie or `Authorization: Bearer <QUEUE_API_KEY>`.

Install manually: `bash payload/queue/install.sh`

---

## Adding your own payload

1. Create a directory under `payload/` for your project.
2. Add a `install.sh` that idempotently sets up whatever your payload needs
   (cron jobs, systemd units, application files).
3. Call your `install.sh` from `fleet/<role>/setup.sh` at the bottom of the
   "Payload layer" section, or run it manually after SSH-ing into the VM.

The keepalive payload stays in place regardless of what else you install — it
is the baseline that keeps your fleet alive and monitored.
