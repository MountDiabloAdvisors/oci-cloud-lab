#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "$SCRIPT_DIR/oci_launch_until_available.py" --profile "$SCRIPT_DIR/profiles/management.json" "$@"
echo ""
echo "Exit code: $?"
