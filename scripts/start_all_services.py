#!/usr/bin/env python3
"""Start all services for Mera AI.

This script starts:
- PostgreSQL (port 5432) - Main database
- Mera AI Application (port 8000) - Main API server
- Frontend UI (port 3000) - Next.js web interface

Docker services run in containers via docker-compose.
Frontend runs as a local Node.js process.
It checks for prerequisites, port conflicts, and manages all services together.
"""

import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Check if running in interactive mode
def is_interactive() -> bool:
    """Check if stdin is a TTY (interactive mode)."""
    return sys.stdin.isatty()

# Port configuration
PORTS = {
    "postgres": 5432,
    "app": 8000,
    "frontend": 3000,
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


def check_docker_services_running() -> bool:
    """Check if Docker services are already running."""
    project_root = Path(__file__).parent.parent
    docker_compose_file = project_root / "docker-compose.yml"
    docker_compose_cmd = get_docker_compose_cmd()
    
    try:
        result = subprocess.run(
            docker_compose_cmd + ["-f", str(docker_compose_file), "ps", "--format", "json"],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            # Check if any services are running
            lines = [line for line in result.stdout.strip().split('\n') if line.strip()]
            return len(lines) > 0
        return False
    except Exception:
        return False


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


def check_env_file() -> bool:
    """Check if .env file exists."""
    project_root = Path(__file__).parent.parent
    env_file = project_root / ".env"
    env_example = project_root / "env.example"
    
    if not env_file.exists():
        print(f"{Colors.YELLOW}Warning: .env file not found.{Colors.RESET}")
        if env_example.exists():
            print(f"{Colors.BLUE}Creating .env from env.example...{Colors.RESET}")
            try:
                import shutil
                shutil.copy(env_example, env_file)
                print(f"{Colors.YELLOW}Please edit .env and add your OPENROUTER_API_KEY before continuing.{Colors.RESET}")
                if is_interactive():
                    response = input("Continue anyway? (y/N): ")
                    if response.lower() != "y":
                        return False
                else:
                    print(f"{Colors.YELLOW}Non-interactive mode: Continuing, but you must set OPENROUTER_API_KEY in .env{Colors.RESET}")
            except Exception as e:
                print(f"{Colors.RED}Error creating .env: {e}{Colors.RESET}")
                return False
        else:
            print(f"{Colors.RED}Error: .env file not found and env.example is missing.{Colors.RESET}")
            return False
    return True


def start_docker_services() -> Optional[subprocess.Popen]:
    """Start Docker services using docker-compose."""
    project_root = Path(__file__).parent.parent
    docker_compose_file = project_root / "docker-compose.yml"

    if not docker_compose_file.exists():
        print(f"{Colors.RED}Error: docker-compose.yml not found at {docker_compose_file}{Colors.RESET}")
        return None

    docker_compose_cmd = get_docker_compose_cmd()
    cmd = docker_compose_cmd + ["-f", str(docker_compose_file), "up", "-d", "--build"]

    print(f"{Colors.BLUE}Starting Docker services (this may take a minute on first run)...{Colors.RESET}")
    try:
        result = subprocess.run(
            cmd,
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=300,  # Increased timeout for building
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


def check_node() -> bool:
    """Check if Node.js is installed."""
    try:
        result = subprocess.run(
            ["node", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def check_npm() -> bool:
    """Check if npm is installed."""
    try:
        result = subprocess.run(
            ["npm", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def install_frontend_dependencies(project_root: Path) -> bool:
    """Install frontend dependencies if needed."""
    frontend_dir = project_root / "frontend"
    node_modules = frontend_dir / "node_modules"
    
    if node_modules.exists():
        return True
    
    print(f"{Colors.BLUE}Installing frontend dependencies (this may take a few minutes)...{Colors.RESET}")
    try:
        result = subprocess.run(
            ["npm", "install"],
            cwd=frontend_dir,
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode != 0:
            print(f"{Colors.RED}Error installing frontend dependencies:{Colors.RESET}")
            print(result.stderr)
            return False
        print(f"{Colors.GREEN}✓ Frontend dependencies installed{Colors.RESET}")
        return True
    except subprocess.TimeoutExpired:
        print(f"{Colors.RED}Timeout installing frontend dependencies{Colors.RESET}")
        return False
    except Exception as e:
        print(f"{Colors.RED}Error: {e}{Colors.RESET}")
        return False


def start_frontend(project_root: Path) -> Optional[subprocess.Popen]:
    """Start the Next.js frontend development server."""
    frontend_dir = project_root / "frontend"
    
    if not frontend_dir.exists():
        print(f"{Colors.YELLOW}Warning: frontend directory not found. Skipping frontend.{Colors.RESET}")
        return None
    
    # Check if dependencies are installed
    if not (frontend_dir / "node_modules").exists():
        if not install_frontend_dependencies(project_root):
            print(f"{Colors.YELLOW}Warning: Failed to install frontend dependencies. Skipping frontend.{Colors.RESET}")
            return None
    
    # Set environment variable for API URL
    env = os.environ.copy()
    env["NEXT_PUBLIC_API_URL"] = "http://localhost:8000"
    
    print(f"{Colors.BLUE}Starting frontend development server...{Colors.RESET}")
    try:
        process = subprocess.Popen(
            ["npm", "run", "dev"],
            cwd=frontend_dir,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        print(f"{Colors.GREEN}✓ Frontend server started (PID: {process.pid}){Colors.RESET}")
        return process
    except Exception as e:
        print(f"{Colors.RED}Error starting frontend: {e}{Colors.RESET}")
        return None




def wait_for_service(name: str, port: int, url: Optional[str] = None, max_wait: int = 120) -> bool:
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

        time.sleep(2)
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

    print(f"\n{Colors.BOLD}Access URLs:{Colors.RESET}")
    print(f"  - PostgreSQL: {Colors.BLUE}localhost:{PORTS['postgres']}{Colors.RESET}")
    print(f"  - Mera AI API: {Colors.BLUE}http://localhost:8000{Colors.RESET}")
    print(f"  - API Documentation: {Colors.BLUE}http://localhost:8000/docs{Colors.RESET}")
    print(f"  - API Status: {Colors.BLUE}http://localhost:8000/status{Colors.RESET}")
    print(f"  - Frontend UI: {Colors.BLUE}http://localhost:3000{Colors.RESET}")


def cleanup(processes: List[subprocess.Popen]):
    """Cleanup processes on exit."""
    print(f"\n{Colors.YELLOW}Shutting down services...{Colors.RESET}")

    # Stop frontend process
    for process in processes:
        if process and process.poll() is None:
            try:
                process.terminate()
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
            except Exception:
                pass

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
    
    # Check Node.js and npm for frontend
    project_root = Path(__file__).parent.parent
    frontend_dir = project_root / "frontend"
    if frontend_dir.exists():
        if not check_node():
            print(f"{Colors.YELLOW}Warning: Node.js is not installed. Frontend will not start.{Colors.RESET}")
        elif not check_npm():
            print(f"{Colors.YELLOW}Warning: npm is not installed. Frontend will not start.{Colors.RESET}")

    # Check if services are already running
    if check_docker_services_running():
        print(f"{Colors.GREEN}Docker services are already running.{Colors.RESET}")
        print_status()
        print(f"\n{Colors.BLUE}To restart services, run: {Colors.RESET}./stop.sh && ./start.sh")
        sys.exit(0)
    
    # Check for port conflicts
    ports_ok, conflicts = check_all_ports()
    if not ports_ok:
        print(f"{Colors.YELLOW}Warning: Some ports are already in use:{Colors.RESET}")
        for conflict in conflicts:
            print(f"  - {conflict}")
        print(f"\n{Colors.YELLOW}This might be okay if services are already running.{Colors.RESET}")
        
        if is_interactive():
            response = input("Continue anyway? (y/N): ")
            if response.lower() != "y":
                print("Aborted.")
                sys.exit(1)
        else:
            print(f"{Colors.YELLOW}Non-interactive mode: Continuing anyway...{Colors.RESET}")

    # Check for .env file
    if not check_env_file():
        print(f"{Colors.RED}Aborted. Please create .env file with required configuration.{Colors.RESET}")
        sys.exit(1)

    # Start services
    processes: List[subprocess.Popen] = []

    # Start Docker services (includes PostgreSQL + App)
    start_docker_services()

    # Wait for Docker services to be ready
    print(f"\n{Colors.BLUE}Waiting for services to be ready...{Colors.RESET}")
    wait_for_service("PostgreSQL", PORTS["postgres"])
    wait_for_service("Mera AI Application", PORTS["app"], url="http://localhost:8000/status")
    
    # Start frontend
    project_root = Path(__file__).parent.parent
    frontend_process = start_frontend(project_root)
    if frontend_process:
        processes.append(frontend_process)
        # Wait for frontend to be ready
        wait_for_service("Frontend", PORTS["frontend"], url="http://localhost:3000")

    # Print status
    print_status()

    print(f"\n{Colors.GREEN}{Colors.BOLD}✓ All services are running!{Colors.RESET}")
    print(f"\n{Colors.BOLD}Next steps:{Colors.RESET}")
    print(f"  - Open UI: {Colors.BLUE}http://localhost:3000{Colors.RESET}")
    print(f"  - Test the API: {Colors.BLUE}curl http://localhost:8000/status{Colors.RESET}")
    print(f"  - View API docs: {Colors.BLUE}http://localhost:8000/docs{Colors.RESET}")
    print(f"  - View logs: {Colors.BLUE}docker-compose logs -f app{Colors.RESET}")
    print(f"\n{Colors.YELLOW}Press Ctrl+C to stop all services.{Colors.RESET}\n")

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

