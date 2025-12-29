#!/usr/bin/env python3
"""Stop all services for Mera AI.

This script stops:
- Docker services (PostgreSQL + Mera AI Application)

All services are stopped via docker-compose.
"""

import subprocess
import sys
from pathlib import Path

# Colors for terminal output
class Colors:
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BLUE = "\033[94m"
    RESET = "\033[0m"
    BOLD = "\033[1m"


def get_docker_compose_cmd():
    """Get the correct docker-compose command."""
    result = subprocess.run(
        ["docker", "compose", "version"],
        capture_output=True,
        text=True,
        timeout=5,
    )
    if result.returncode == 0:
        return ["docker", "compose"]
    return ["docker-compose"]


def stop_docker_services():
    """Stop Docker services."""
    project_root = Path(__file__).parent.parent
    docker_compose_file = project_root / "docker-compose.yml"

    if not docker_compose_file.exists():
        print(f"{Colors.RED}Error: docker-compose.yml not found{Colors.RESET}")
        return False

    docker_compose_cmd = get_docker_compose_cmd()
    cmd = docker_compose_cmd + ["-f", str(docker_compose_file), "down"]

    print(f"{Colors.BLUE}Stopping Docker services...{Colors.RESET}")
    try:
        result = subprocess.run(
            cmd,
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode == 0:
            print(f"{Colors.GREEN}✓ Docker services stopped{Colors.RESET}")
            return True
        else:
            print(f"{Colors.RED}Error stopping Docker services:{Colors.RESET}")
            print(result.stderr)
            return False
    except Exception as e:
        print(f"{Colors.RED}Error: {e}{Colors.RESET}")
        return False


def main():
    """Main entry point."""
    print(f"{Colors.BOLD}{Colors.BLUE}Mera AI - Stopping All Services{Colors.RESET}")
    print(f"{'=' * 50}\n")

    success = stop_docker_services()

    if success:
        print(f"\n{Colors.GREEN}{Colors.BOLD}All services stopped successfully!{Colors.RESET}")
        sys.exit(0)
    else:
        print(f"\n{Colors.RED}{Colors.BOLD}Some errors occurred while stopping services.{Colors.RESET}")
        sys.exit(1)


if __name__ == "__main__":
    main()

