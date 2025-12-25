#!/bin/bash
# Convenience wrapper script to start all services

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "$SCRIPT_DIR/scripts/start_all_services.py" "$@"

