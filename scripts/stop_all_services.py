#!/usr/bin/env python3
"""Stop all services for Mera AI.

This script stops:
- Frontend UI (Next.js process)
- Docker services (PostgreSQL + Mera AI Application)

Frontend is stopped by killing the process on port 3000.
Docker services are stopped via docker-compose.
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


def stop_frontend():
    """Stop frontend process by finding and killing Node.js processes on port 3000."""
    try:
        # Try to find process using port 3000 with lsof (works on macOS and Linux)
        result = subprocess.run(
            ["lsof", "-ti:3000"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        
        if result.returncode == 0 and result.stdout.strip():
            pids = result.stdout.strip().split('\n')
            for pid in pids:
                if pid:
                    try:
                        subprocess.run(["kill", pid], timeout=5)
                    except Exception:
                        pass
            return True
    except FileNotFoundError:
        # lsof not available, try alternative method
        try:
            # Try using pkill for Next.js processes
            subprocess.run(["pkill", "-f", "next dev"], timeout=5, capture_output=True)
            return True
        except Exception:
            pass
    except Exception:
        # If lsof fails, try pkill as fallback
        try:
            subprocess.run(["pkill", "-f", "next dev"], timeout=5, capture_output=True)
            return True
        except Exception:
            pass
    return False


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

    # Stop frontend
    print(f"{Colors.BLUE}Stopping frontend...{Colors.RESET}")
    if stop_frontend():
        print(f"{Colors.GREEN}✓ Frontend stopped{Colors.RESET}")
    else:
        print(f"{Colors.YELLOW}Frontend may not have been running{Colors.RESET}")

    # Stop Docker services
    success = stop_docker_services()

    if success:
        print(f"\n{Colors.GREEN}{Colors.BOLD}All services stopped successfully!{Colors.RESET}")
        sys.exit(0)
    else:
        print(f"\n{Colors.RED}{Colors.BOLD}Some errors occurred while stopping services.{Colors.RESET}")
        sys.exit(1)


if __name__ == "__main__":
    main()

