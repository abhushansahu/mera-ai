#!/usr/bin/env python3
"""Start all self-hosted dependencies for Mera AI.

This script starts:
- PostgreSQL (port 5432)
- Langfuse DB (port 5433)
- Langfuse UI (port 3000)
- Mem0 API Server (port 8001)

It checks for port conflicts and manages all services together.
"""

import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Port configuration
PORTS = {
    "postgres": 5432,
    "clickhouse_http": 8123,
    "clickhouse_native": 9000,
    "langfuse": 3000,
    "mem0": 8001,
}

# Colors for terminal output
class Colors:
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BLUE = "\033[94m"
    RESET = "\033[0m"
    BOLD = "\033[1m"


def check_port(port: int) -> bool:
    """Check if a port is already in use."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("localhost", port))
            return False
        except OSError:
            return True


def check_all_ports() -> Tuple[bool, List[str]]:
    """Check all required ports and return conflicts."""
    conflicts = []
    for service, port in PORTS.items():
        if check_port(port):
            conflicts.append(f"{service} (port {port})")
    return len(conflicts) == 0, conflicts


def check_docker() -> bool:
    """Check if Docker is installed and running."""
    try:
        result = subprocess.run(
            ["docker", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return False

        # Check if Docker daemon is running
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def check_docker_compose() -> bool:
    """Check if docker-compose is available."""
    try:
        # Try docker compose (newer) or docker-compose (older)
        for cmd in [["docker", "compose", "version"], ["docker-compose", "--version"]]:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                return True
        return False
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def get_docker_compose_cmd() -> List[str]:
    """Get the correct docker-compose command."""
    # Try docker compose (newer) first
    result = subprocess.run(
        ["docker", "compose", "version"],
        capture_output=True,
        text=True,
        timeout=5,
    )
    if result.returncode == 0:
        return ["docker", "compose"]
    return ["docker-compose"]


def start_docker_services() -> Optional[subprocess.Popen]:
    """Start Docker services using docker-compose."""
    project_root = Path(__file__).parent.parent
    docker_compose_file = project_root / "docker-compose.yml"

    if not docker_compose_file.exists():
        print(f"{Colors.RED}Error: docker-compose.yml not found at {docker_compose_file}{Colors.RESET}")
        return None

    docker_compose_cmd = get_docker_compose_cmd()
    cmd = docker_compose_cmd + ["-f", str(docker_compose_file), "up", "-d"]

    print(f"{Colors.BLUE}Starting Docker services...{Colors.RESET}")
    try:
        result = subprocess.run(
            cmd,
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            print(f"{Colors.RED}Error starting Docker services:{Colors.RESET}")
            print(result.stderr)
            return None
        print(f"{Colors.GREEN}✓ Docker services started{Colors.RESET}")
        return None  # Docker services run in detached mode
    except subprocess.TimeoutExpired:
        print(f"{Colors.RED}Timeout starting Docker services{Colors.RESET}")
        return None
    except Exception as e:
        print(f"{Colors.RED}Error: {e}{Colors.RESET}")
        return None


def start_mem0_server() -> Optional[subprocess.Popen]:
    """Start Mem0 API server."""
    script_path = Path(__file__).parent / "start_mem0_server.py"

    if not script_path.exists():
        print(f"{Colors.RED}Error: start_mem0_server.py not found at {script_path}{Colors.RESET}")
        return None

    print(f"{Colors.BLUE}Starting Mem0 server...{Colors.RESET}")
    try:
        # Try to use venv Python if available
        project_root = Path(__file__).parent.parent
        venv_python = project_root / "venv" / "bin" / "python"
        if venv_python.exists():
            python_executable = str(venv_python)
        else:
            python_executable = sys.executable

        # Set environment variables for Mem0
        env = os.environ.copy()
        env["MEM0_HOST"] = "0.0.0.0"
        env["MEM0_PORT"] = str(PORTS["mem0"])

        process = subprocess.Popen(
            [python_executable, str(script_path)],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        # Wait a moment to check if it started successfully
        time.sleep(2)
        if process.poll() is not None:
            # Process exited, read output
            output, _ = process.communicate()
            print(f"{Colors.RED}Error starting Mem0 server:{Colors.RESET}")
            print(output)
            return None

        print(f"{Colors.GREEN}✓ Mem0 server started (PID: {process.pid}){Colors.RESET}")
        return process
    except Exception as e:
        print(f"{Colors.RED}Error starting Mem0 server: {e}{Colors.RESET}")
        return None


def wait_for_service(name: str, port: int, url: Optional[str] = None, max_wait: int = 60) -> bool:
    """Wait for a service to become available."""
    print(f"{Colors.BLUE}Waiting for {name} to be ready...{Colors.RESET}", end="", flush=True)
    start_time = time.time()

    while time.time() - start_time < max_wait:
        if url:
            # Check HTTP endpoint
            try:
                import urllib.request

                with urllib.request.urlopen(url, timeout=2) as response:
                    if response.status == 200:
                        print(f" {Colors.GREEN}✓{Colors.RESET}")
                        return True
            except Exception:
                pass
        else:
            # Check TCP port
            if check_port(port):
                print(f" {Colors.GREEN}✓{Colors.RESET}")
                return True

        time.sleep(1)
        print(".", end="", flush=True)

    print(f" {Colors.RED}✗ (timeout){Colors.RESET}")
    return False


def print_status():
    """Print status of all services."""
    print(f"\n{Colors.BOLD}{Colors.BLUE}Service Status:{Colors.RESET}")
    print(f"{'=' * 50}")

    # Check Docker services
    docker_compose_cmd = get_docker_compose_cmd()
    project_root = Path(__file__).parent.parent
    docker_compose_file = project_root / "docker-compose.yml"

    try:
        result = subprocess.run(
            docker_compose_cmd + ["-f", str(docker_compose_file), "ps"],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            print(f"{Colors.GREEN}Docker Services:{Colors.RESET}")
            print(result.stdout)
    except Exception:
        pass

    # Check Mem0
    if check_port(PORTS["mem0"]):
        print(f"{Colors.GREEN}✓ Mem0: Running on port {PORTS['mem0']}{Colors.RESET}")
    else:
        print(f"{Colors.RED}✗ Mem0: Not running{Colors.RESET}")

    # Check ClickHouse
    if check_port(PORTS["clickhouse_http"]):
        print(f"{Colors.GREEN}✓ ClickHouse: Running on port {PORTS['clickhouse_http']}{Colors.RESET}")
    else:
        print(f"{Colors.RED}✗ ClickHouse: Not running{Colors.RESET}")

    print(f"\n{Colors.BOLD}Access URLs:{Colors.RESET}")
    print(f"  - Langfuse UI: {Colors.BLUE}http://localhost:{PORTS['langfuse']}{Colors.RESET}")
    print(f"  - Mem0 API: {Colors.BLUE}http://localhost:{PORTS['mem0']}{Colors.RESET}")
    print(f"  - Mem0 Docs: {Colors.BLUE}http://localhost:{PORTS['mem0']}/docs{Colors.RESET}")
    print(f"  - PostgreSQL: {Colors.BLUE}localhost:{PORTS['postgres']}{Colors.RESET}")
    print(f"  - ClickHouse HTTP: {Colors.BLUE}http://localhost:{PORTS['clickhouse_http']}{Colors.RESET}")


def cleanup(processes: List[subprocess.Popen]):
    """Cleanup processes on exit."""
    print(f"\n{Colors.YELLOW}Shutting down services...{Colors.RESET}")

    # Stop Docker services (includes all services now)
    project_root = Path(__file__).parent.parent
    docker_compose_file = project_root / "docker-compose.yml"
    docker_compose_cmd = get_docker_compose_cmd()

    try:
        subprocess.run(
            docker_compose_cmd + ["-f", str(docker_compose_file), "down"],
            cwd=project_root,
            capture_output=True,
            timeout=30,
        )
    except Exception:
        pass

    print(f"{Colors.GREEN}All services stopped.{Colors.RESET}")


def main():
    """Main entry point."""
    print(f"{Colors.BOLD}{Colors.BLUE}Mera AI - Starting All Services{Colors.RESET}")
    print(f"{'=' * 50}\n")

    # Check prerequisites
    if not check_docker():
        print(f"{Colors.RED}Error: Docker is not installed or not running.{Colors.RESET}")
        print("Please install Docker and ensure the Docker daemon is running.")
        sys.exit(1)

    if not check_docker_compose():
        print(f"{Colors.RED}Error: docker-compose is not available.{Colors.RESET}")
        sys.exit(1)

    # Check for port conflicts
    ports_ok, conflicts = check_all_ports()
    if not ports_ok:
        print(f"{Colors.YELLOW}Warning: Some ports are already in use:{Colors.RESET}")
        for conflict in conflicts:
            print(f"  - {conflict}")
        print(f"\n{Colors.YELLOW}This might be okay if services are already running.{Colors.RESET}")
        response = input("Continue anyway? (y/N): ")
        if response.lower() != "y":
            print("Aborted.")
            sys.exit(1)

    # Start services
    processes: List[subprocess.Popen] = []

    # Start Docker services (includes Mem0 now)
    start_docker_services()

    # Wait for Docker services to be ready
    time.sleep(3)

    # Wait for services to be ready
    print(f"\n{Colors.BLUE}Waiting for services to be ready...{Colors.RESET}")
    wait_for_service("PostgreSQL", PORTS["postgres"])
    wait_for_service(
        "ClickHouse",
        PORTS["clickhouse_http"],
        url=f"http://localhost:{PORTS['clickhouse_http']}/ping",
    )
    wait_for_service(
        "Mem0",
        PORTS["mem0"],
        url=f"http://localhost:{PORTS['mem0']}/health",
    )
    wait_for_service(
        "Langfuse",
        PORTS["langfuse"],
        url=f"http://localhost:{PORTS['langfuse']}/api/public/health",
        max_wait=120,  # Langfuse can take longer to start
    )

    # Print status
    print_status()

    print(f"\n{Colors.GREEN}{Colors.BOLD}All services are running!{Colors.RESET}")
    print(f"{Colors.YELLOW}Press Ctrl+C to stop all services.{Colors.RESET}\n")

    # Set up signal handlers for graceful shutdown
    def signal_handler(sig, frame):
        cleanup(processes)
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Keep script running (all services are in Docker now)
    try:
        while True:
            time.sleep(5)
    except KeyboardInterrupt:
        pass
    finally:
        cleanup(processes)


if __name__ == "__main__":
    main()

