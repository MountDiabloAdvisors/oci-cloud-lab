#!/usr/bin/env python3
"""
Laboratory lottery — runs on the worker VM.

Checks if laboratory (A1.Flex) is active. If not, launches the A1 capacity lottery
(retries until Oracle grants capacity). Once the VM is up, sleeps 6 hours and
checks again — so if it's ever terminated, the lottery restarts automatically.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


TOOLS_DIR      = Path(os.environ.get("TOOLS_DIR", Path.home() / "cloud-lab"))
LAUNCHER       = TOOLS_DIR / "admin" / "oci_launch_until_available.py"
PROFILE        = TOOLS_DIR / "admin" / "profiles" / "laboratory.json"
CHECK_INTERVAL = 6 * 3600   # re-check every 6 h once VM is confirmed running


def ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def log(msg: str) -> None:
    print(f"[{ts()}] [laboratory-lottery] {msg}", flush=True)


def laboratory_active() -> bool:
    oci = shutil.which("oci") or str(Path.home() / "bin" / "oci")
    compartment_id = os.environ.get("OCI_COMPARTMENT_ID", "")
    env = os.environ.copy()
    env["OCI_CLI_AUTH"] = "instance_principal"
    env["OCI_CLI_SUPPRESS_FILE_PERMISSIONS_WARNING"] = "True"
    env["PYTHONWARNINGS"] = "ignore::FutureWarning"
    try:
        result = subprocess.run(
            [oci, "compute", "instance", "list",
             "--compartment-id", compartment_id,
             "--display-name", "laboratory",
             "--all"],
            capture_output=True, text=True, timeout=30, env=env,
        )
        if result.returncode != 0:
            log(f"OCI status check failed: {result.stderr.strip()}")
            return False
        data = json.loads(result.stdout) if result.stdout.strip() else {"data": []}
        for item in data.get("data", []):
            state = item.get("lifecycle-state", "")
            if state not in ("TERMINATING", "TERMINATED"):
                log(f"laboratory found in state: {state}")
                return True
        return False
    except Exception as exc:
        log(f"Status check error: {exc}")
        return False


def main() -> None:
    log("Laboratory lottery starting.")
    if not LAUNCHER.exists():
        log(f"ERROR: launcher not found at {LAUNCHER}")
        sys.exit(1)
    if not PROFILE.exists():
        log(f"ERROR: profile not found at {PROFILE}")
        sys.exit(1)

    while True:
        if laboratory_active():
            log(f"laboratory is running. Next check in {CHECK_INTERVAL}s.")
            time.sleep(CHECK_INTERVAL)
        else:
            log("laboratory not found — entering A1 capacity lottery.")
            subprocess.run(
                [sys.executable, str(LAUNCHER), "--profile", str(PROFILE)],
                env={**os.environ, "OCI_CLI_AUTH": "instance_principal"},
            )
            log("Lottery exited. Rechecking immediately.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("Stopped.")
        sys.exit(0)
