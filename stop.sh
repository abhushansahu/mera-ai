#!/bin/bash
# Convenience wrapper script to stop all services

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "$SCRIPT_DIR/scripts/stop_all_services.py" "$@"

