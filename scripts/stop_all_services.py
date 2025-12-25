#!/usr/bin/env python3
"""Stop all self-hosted dependencies for Mera AI.

This script stops:
- Docker services (PostgreSQL, Langfuse)
- Mem0 API Server
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


def stop_mem0_server():
    """Stop Mem0 server by finding and killing the process."""
    print(f"{Colors.BLUE}Stopping Mem0 server...{Colors.RESET}")
    
    try:
        # Find Mem0 server process
        result = subprocess.run(
            ["pgrep", "-f", "start_mem0_server.py"],
            capture_output=True,
            text=True,
        )
        
        if result.returncode == 0:
            pids = result.stdout.strip().split("\n")
            for pid in pids:
                if pid:
                    try:
                        subprocess.run(["kill", pid], timeout=5)
                        print(f"{Colors.GREEN}✓ Mem0 server stopped (PID: {pid}){Colors.RESET}")
                    except Exception:
                        pass
            return True
        else:
            print(f"{Colors.YELLOW}No Mem0 server process found{Colors.RESET}")
            return True
    except FileNotFoundError:
        # pgrep not available, try alternative method
        print(f"{Colors.YELLOW}Could not find Mem0 process (pgrep not available){Colors.RESET}")
        return True
    except Exception as e:
        print(f"{Colors.RED}Error stopping Mem0 server: {e}{Colors.RESET}")
        return False


def main():
    """Main entry point."""
    print(f"{Colors.BOLD}{Colors.BLUE}Mera AI - Stopping All Services{Colors.RESET}")
    print(f"{'=' * 50}\n")

    success = True
    success &= stop_mem0_server()
    success &= stop_docker_services()

    if success:
        print(f"\n{Colors.GREEN}{Colors.BOLD}All services stopped successfully!{Colors.RESET}")
        sys.exit(0)
    else:
        print(f"\n{Colors.RED}{Colors.BOLD}Some errors occurred while stopping services.{Colors.RESET}")
        sys.exit(1)


if __name__ == "__main__":
    main()

