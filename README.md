# Oracle Free Cloud Lab Starter

Commandeer Oracle Cloud's Always Free tier — 2 micro VMs + 1 A1 Flex (4 OCPU / 24 GB) —
and keep them alive indefinitely. Includes a secure web admin console, push notifications,
cross-VM health monitoring, and a self-healing fleet orchestrator.

This is a **starter**, not a finished product. Once your fleet is running, layer your
own workloads on top (see `payload/`).

---

## What you get

- **3 VMs provisioned and kept alive** — management, worker, lab-vm (A1 Flex)
- **Admin console** — HTTPS web UI at your DuckDNS domain, password-protected
- **Fleet orchestrator** — management VM watches `fleet.json` and relaunches any VM that goes down
- **Cross-watch** — each VM monitors peers and alerts if any go missing
- **ntfy push alerts** — heartbeats, daily fleet report, and anomaly alerts to your phone
- **Keepalive payload** — cron jobs that produce enough real CPU activity to satisfy Oracle's idle-reclamation policy

---

## 5-step setup

### 1. Prerequisites

- Oracle Cloud account (free tier)
- OCI CLI installed and configured (`oci setup config`)
- Python 3.10+
- SSH key pair for fleet VMs

### 2. Configure

```bash
cp .env.example .env
# Edit .env — fill in OCI credentials, FLEET_REPO, GITHUB_TOKEN, ADMIN_PASSWORD_HASH
python admin/hash_password.py   # generates ADMIN_PASSWORD_HASH
```

### 3. Create network resources

```
admin/setup-oci-network
```

Fills in `OCI_VCN_ID`, `OCI_SUBNET_ID` in `.env`.

### 4. Launch the management VM

```
admin/launch-management
```

Cloud-init does everything: clones the repo, installs systemd services, starts the
admin console, orchestrator, and keepalive cron jobs. Takes ~5 minutes.

After it's up, SSH in to verify:

```
admin/ssh-vm management
```

### 5. Let the orchestrator do the rest

The fleet orchestrator reads `fleet.json` and launches `worker` and `lab-vm`
automatically. Check status any time:

```
admin/check-all-vms
```

---

## Admin scripts

All scripts live in `admin/`. `.bat` wrappers are provided for Windows.

| Script | What it does |
|---|---|
| `setup-oci-network` | Create VCN, subnet, security rules (run once) |
| `launch-management` | Launch the management VM |
| `check-all-vms` | Query OCI state + SSH probe all fleet VMs |
| `ssh-vm <name>` | SSH into any fleet VM (management / worker / lab-vm) |
| `bootstrap-mgmt-vm` | Re-apply config to a running management VM |
| `terminate-vm` | Terminate a VM by name |

---

## Fleet layout

```
management   VM.Standard.E2.1.Micro   Fleet orchestrator, admin console, heartbeat
worker       VM.Standard.E2.1.Micro   General compute, available for your workloads
lab-vm       VM.Standard.A1.Flex      4 OCPU / 24 GB — your primary compute resource
```

VM names and shapes are configured in `fleet.json`. Each role's cloud-init and
setup scripts live in `fleet/<role>/`.

---

## Payload layer

`payload/keepalive/` runs on every VM by default (cron, no sudo). To add your own
workload, create a directory under `payload/` and add an `install.sh`. See
[payload/README.md](payload/README.md).

---

## Handing off to your own project

Once the fleet is running, your downstream project needs only three values from
the admin console's `/export` endpoint:

- `OCI_MANAGEMENT_HOST` / `OCI_WORKER_HOST` / `OCI_LAB_VM_HOST` — public IPs
- `FLEET_MANAGEMENT_PRIVATE_IP` / `FLEET_WORKER_PRIVATE_IP` / `FLEET_LAB_VM_PRIVATE_IP` — internal IPs

Copy those into your project's `.env`. The fleet continues managing itself;
your project just uses the VMs.

---

## Security notes

- `.env` is gitignored — never committed
- `ADMIN_PASSWORD_HASH` is pre-computed on your laptop; plaintext never reaches the VM
- VMs authenticate to OCI via instance-principal (no API key on the VM)
- `vm-profiles/` snapshots are gitignored (contain IP addresses)
- Admin console is behind Caddy with a real TLS cert via DuckDNS
