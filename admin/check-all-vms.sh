#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "$SCRIPT_DIR/check_oci_vm_status.py" --ping "$@"
echo ""
echo "Exit code: $?"
