#!/usr/bin/env python3
"""
Push rotated secrets from the local .env out to the live fleet.

Usage:
    python admin/rotate_secrets.py              # push GITHUB_TOKEN + admin password
    python admin/rotate_secrets.py --token      # token only
    python admin/rotate_secrets.py --password   # admin password only
    python admin/rotate_secrets.py --dry-run    # show what would change, touch nothing

Reads the new values from .env and updates, on each live VM:
  - ~/.config/cloud-lab/{role}.env          (GITHUB_TOKEN, ADMIN_PASSWORD_HASH)
  - ~/cloud-lab/.git/config                 (token embedded in the clone URL by cloud-init)
then restarts that VM's cloud-lab services.

Secret values are never printed and never passed as command-line arguments
(argv is world-readable via `ps` on the remote host). They are embedded in a
script piped to the remote over stdin.

The worker is not reachable from the laptop — it only trusts management's
fleet.key — so worker updates hop through management.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import secrets
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = REPO_ROOT / ".env"

MANAGEMENT_ROLE = "management"
WORKER_ROLE = "worker"

# Services to restart per role after secrets change. The console is restarted
# last on management so it is not killed mid-update.
ROLE_SERVICES = {
    MANAGEMENT_ROLE: [
        "cloud-lab-orchestrator",
        "cloud-lab-heartbeat",
        "cloud-lab-crosswatch",
        "cloud-lab-console",
    ],
    WORKER_ROLE: [
        "cloud-lab-a1-lottery",
        "cloud-lab-heartbeat",
        "cloud-lab-crosswatch",
    ],
}


def load_env(path: Path) -> dict[str, str]:
    """Parse a KEY=VALUE .env file. Values are never logged."""
    if not path.exists():
        sys.exit(f"ERROR: {path} not found.")
    env: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        env[key.strip()] = value.strip()
    return env


def hash_password(password: str) -> str:
    """Same scheme as admin/hash_password.py — must stay in sync."""
    salt = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 260000).hex()
    return f"sha256:260000:{salt}:{h}"


def build_remote_script(role: str, updates: dict[str, str], repo: str,
                        token: str | None, restart: bool) -> str:
    """
    Build the bash script executed on the remote host.

    Values are interpolated as Python reprs into a python3 heredoc, so quoting,
    special characters and shell metacharacters in a password hash or token
    cannot break out. Nothing here echoes a value.
    """
    env_path = f"$HOME/.config/cloud-lab/{role}.env"
    pairs = ", ".join(f"{k!r}: {v!r}" for k, v in updates.items())

    git_fix = ""
    if token:
        # cloud-init cloned with https://oauth2:<token>@github.com/<repo>.git —
        # rewrite the stored remote so `git pull` uses the new token.
        new_url = f"https://oauth2:{token}@github.com/{repo}.git"
        git_fix = f"""
if [ -d "$HOME/cloud-lab/.git" ]; then
    git -C "$HOME/cloud-lab" remote set-url origin {new_url!r} && echo "OK   git remote url updated"
else
    echo "SKIP no git clone at ~/cloud-lab"
fi
"""

    restart_block = ""
    if restart:
        services = " ".join(ROLE_SERVICES.get(role, []))
        restart_block = f"""
for svc in {services}; do
    if systemctl list-unit-files "$svc.service" >/dev/null 2>&1 && \\
       systemctl cat "$svc.service" >/dev/null 2>&1; then
        sudo systemctl restart "$svc" && echo "OK   restarted $svc" || echo "FAIL restart $svc"
    else
        echo "SKIP $svc not installed"
    fi
done
"""

    return f"""set -u
ENV_FILE="{env_path}"
if [ ! -f "$ENV_FILE" ]; then
    echo "FAIL $ENV_FILE missing"
    exit 1
fi
cp "$ENV_FILE" "$ENV_FILE.bak.$(date +%s)"

python3 - "$ENV_FILE" <<'PYEOF'
import sys

path = sys.argv[1]
updates = {{{pairs}}}

with open(path, encoding="utf-8") as fh:
    lines = fh.read().splitlines()

seen = set()
out = []
for line in lines:
    key = line.split("=", 1)[0].strip() if "=" in line else None
    if key in updates:
        out.append(f"{{key}}={{updates[key]}}")
        seen.add(key)
    else:
        out.append(line)

for key, value in updates.items():
    if key not in seen:
        out.append(f"{{key}}={{value}}")

with open(path, "w", encoding="utf-8") as fh:
    fh.write("\\n".join(out) + "\\n")

for key in updates:
    print(f"OK   {{key}} set in {{path.split('/')[-1]}}")
PYEOF

chmod 600 "$ENV_FILE"
{git_fix}{restart_block}
echo "DONE {role}"
"""


def run_remote(ssh_target: str, key_path: str, script: str,
               hop: tuple[str, str] | None = None) -> int:
    """
    Pipe `script` to bash on the remote host over stdin.

    hop = (inner_user_host, inner_key) routes through ssh_target to a second
    host, with stdin passing straight through both legs.
    """
    if hop:
        inner_host, inner_key = hop
        remote_cmd = (
            f"ssh -i {inner_key} -o BatchMode=yes -o ConnectTimeout=10 "
            f"-o StrictHostKeyChecking=accept-new {inner_host} 'bash -s'"
        )
    else:
        remote_cmd = "bash -s"

    proc = subprocess.run(
        ["ssh", "-i", key_path, "-o", "BatchMode=yes", "-o", "ConnectTimeout=15",
         ssh_target, remote_cmd],
        input=script.encode("utf-8"),
        capture_output=True,
    )
    for stream in (proc.stdout, proc.stderr):
        text = stream.decode("utf-8", "replace").strip()
        if text:
            for line in text.splitlines():
                print(f"    {line}")
    return proc.returncode


def main() -> None:
    parser = argparse.ArgumentParser(description="Push rotated secrets to the fleet.")
    parser.add_argument("--token", action="store_true", help="push GITHUB_TOKEN only")
    parser.add_argument("--password", action="store_true", help="push admin password only")
    parser.add_argument("--dry-run", action="store_true", help="report only, change nothing")
    parser.add_argument("--no-restart", action="store_true", help="skip service restarts")
    args = parser.parse_args()

    do_token = args.token or not (args.token or args.password)
    do_password = args.password or not (args.token or args.password)

    env = load_env(ENV_FILE)

    key_path = os.path.expandvars(
        env.get("OCI_SSH_PRIVATE_KEY_PATH", "%USERPROFILE%\\.ssh\\oracle_mda.key")
    )
    ssh_user = env.get("OCI_SSH_USER", "ubuntu")
    mgmt_host = env.get("OCI_MANAGEMENT_HOST", "").strip()
    repo = env.get("FLEET_REPO", "").strip()

    if not mgmt_host:
        sys.exit("ERROR: OCI_MANAGEMENT_HOST not set in .env")

    token = env.get("GITHUB_TOKEN", "").strip() if do_token else None
    if do_token and not token:
        sys.exit("ERROR: GITHUB_TOKEN is empty in .env")
    if do_token and not re.match(r"^(github_pat_|ghp_)", token or ""):
        sys.exit("ERROR: GITHUB_TOKEN does not look like a GitHub token")

    pw_hash = None
    if do_password:
        password = env.get("ADMIN_PASSWORD", "")
        if not password:
            sys.exit("ERROR: ADMIN_PASSWORD is empty in .env")
        pw_hash = hash_password(password)

    print(f"Fleet secret rotation — repo {repo}")
    print(f"  token:    {'yes' if do_token else 'no'}")
    print(f"  password: {'yes' if do_password else 'no'}")
    if args.dry_run:
        print("\nDRY RUN — nothing will be changed.")
        print(f"  would update {ssh_user}@{mgmt_host}:~/.config/cloud-lab/management.env")
        print(f"  would update worker (via management):~/.config/cloud-lab/worker.env")
        return

    restart = not args.no_restart
    failures = 0

    # ---- management -------------------------------------------------------
    mgmt_updates: dict[str, str] = {}
    if do_token:
        mgmt_updates["GITHUB_TOKEN"] = token  # type: ignore[assignment]
    if do_password:
        mgmt_updates["ADMIN_PASSWORD_HASH"] = pw_hash  # type: ignore[assignment]

    print(f"\n[management] {mgmt_host}")
    script = build_remote_script(MANAGEMENT_ROLE, mgmt_updates, repo, token, restart)
    if run_remote(f"{ssh_user}@{mgmt_host}", key_path, script) != 0:
        failures += 1
        print("    ERROR: management update failed")

    # ---- worker (hop through management) ----------------------------------
    # The worker never serves the admin console, so it only needs the token.
    if do_token:
        worker_ip = env.get("FLEET_WORKER_PRIVATE_IP", "10.0.0.251").strip()
        print(f"\n[worker] {worker_ip} (via management)")
        script = build_remote_script(WORKER_ROLE, {"GITHUB_TOKEN": token},  # type: ignore[dict-item]
                                     repo, token, restart)
        rc = run_remote(
            f"{ssh_user}@{mgmt_host}", key_path, script,
            hop=(f"{ssh_user}@{worker_ip}", "~/.ssh/fleet.key"),
        )
        if rc != 0:
            failures += 1
            print("    ERROR: worker update failed")

    print()
    if failures:
        sys.exit(f"{failures} host(s) failed — see output above.")
    print("All hosts updated. No secret values were printed.")


if __name__ == "__main__":
    main()
