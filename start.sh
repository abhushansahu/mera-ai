#!/bin/bash
# Start all Mera AI services (PostgreSQL + Application)
# This script starts everything needed to run Mera AI in Docker

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "$SCRIPT_DIR/scripts/start_all_services.py" "$@"

