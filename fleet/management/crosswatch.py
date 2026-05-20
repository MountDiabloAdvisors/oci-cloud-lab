#!/usr/bin/env python3
"""
Management cross-watch — runs as a systemd timer on the management VM.
Checks OCI state of peer VMs every 6 hours.
Sends a direct ntfy alert if any expected-RUNNING VM is TERMINATED or missing.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import urllib.request
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parent.parent.parent   # repo root
ENV_FILE  = Path.home() / ".config" / "cloud-lab" / "management.env"
THIS_ROLE = "management"


def parse_env_file(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip(); v = v.strip().strip('"').strip("'")
        if k:
            out[k] = v
    return out


def oci_instance_states(compartment_id: str) -> dict[str, str]:
    oci = shutil.which("oci") or "/home/ubuntu/bin/oci"
    child_env = os.environ.copy()
    child_env["OCI_CLI_AUTH"] = "instance_principal"
    child_env["OCI_CLI_SUPPRESS_FILE_PERMISSIONS_WARNING"] = "True"
    result = subprocess.run(
        [oci, "compute", "instance", "list",
         "--compartment-id", compartment_id, "--all"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", timeout=60,
        env=child_env,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip())
    data = json.loads(result.stdout)
    return {
        item["display-name"]: item.get("lifecycle-state", "UNKNOWN")
        for item in data.get("data", [])
        if item.get("display-name")
    }


def ntfy_alert(topic: str, title: str, message: str, server: str = "https://ntfy.sh") -> None:
    if not topic:
        return
    try:
        req = urllib.request.Request(
            f"{server.rstrip('/')}/{topic}",
            data=message.encode("utf-8"),
            headers={"Title": title, "Tags": "warning,red_circle", "Priority": "high"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=10).read()
    except Exception as exc:
        print(f"[crosswatch] ntfy failed: {exc}", flush=True)


def main() -> None:
    env = parse_env_file(ENV_FILE)
    env.update(os.environ)

    compartment_id = env.get("OCI_COMPARTMENT_ID", "")
    topic       = env.get("NOTIFY_NTFY_TOPIC", "")
    ntfy_server = env.get("NOTIFY_NTFY_SERVER", "https://ntfy.sh")
    fleet_name  = env.get("FLEET_NAME", "Cloud Lab")
    this_vm     = env.get("FLEET_VM_NAME", THIS_ROLE)

    if not compartment_id:
        print("[crosswatch] OCI_COMPARTMENT_ID not set — skipping.", flush=True)
        return

    fleet_file = TOOLS_DIR / "fleet.json"
    fleet = json.loads(fleet_file.read_text(encoding="utf-8")).get("vms", [])

    print("[crosswatch] Querying OCI instance states...", flush=True)
    try:
        states = oci_instance_states(compartment_id)
    except Exception as exc:
        print(f"[crosswatch] OCI query failed: {exc}", flush=True)
        ntfy_alert(topic, f"{fleet_name} Cross-Watch Error",
                   f"{this_vm} could not query OCI: {exc}", ntfy_server)
        return

    for vm in fleet:
        name = vm["name"]
        if name == this_vm:
            continue
        if vm.get("expected_state") != "RUNNING":
            continue

        state = states.get(name, "NOT FOUND")
        print(f"[crosswatch] {name}: {state}", flush=True)

        if state not in ("RUNNING", "STARTING", "PROVISIONING"):
            ntfy_alert(
                topic,
                f"{fleet_name} Alert: {name} is {state}",
                f"{name} expected RUNNING but is {state}. Fleet orchestrator will attempt recovery.",
                ntfy_server,
            )

    print("[crosswatch] Done.", flush=True)


if __name__ == "__main__":
    main()
