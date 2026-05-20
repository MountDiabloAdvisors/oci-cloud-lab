#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "$SCRIPT_DIR/bootstrap_mgmt_vm.py" "$@"
echo ""
echo "Exit code: $?"
