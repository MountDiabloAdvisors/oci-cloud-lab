#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -z "${1:-}" ]; then
    echo "Usage: ssh-vm.sh <vm-name> [-- command]"
    echo "  e.g.: ssh-vm.sh management"
    echo "  e.g.: ssh-vm.sh worker -- uptime"
    exit 1
fi
python3 "$SCRIPT_DIR/ssh_vm.py" "$@"
