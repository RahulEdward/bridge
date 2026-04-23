"""
Windows Service Installer — installs the MT5 Gateway as a Windows service using NSSM.

Usage:
    python scripts/install_service.py install
    python scripts/install_service.py uninstall
    python scripts/install_service.py start
    python scripts/install_service.py stop
    python scripts/install_service.py restart
"""

import os
import sys
import subprocess
import shutil

SERVICE_NAME = "MT5Gateway"
DISPLAY_NAME = "MT5 Execution Gateway"
DESCRIPTION = "Production MT5 trading gateway for multi-user SaaS integration"


def find_nssm() -> str:
    """Find nssm.exe in PATH or common locations."""
    nssm = shutil.which("nssm")
    if nssm:
        return nssm

    common_paths = [
        r"C:\nssm\nssm.exe",
        r"C:\tools\nssm\nssm.exe",
        r"C:\Program Files\nssm\nssm.exe",
        os.path.join(os.path.dirname(__file__), "nssm.exe"),
    ]
    for path in common_paths:
        if os.path.exists(path):
            return path

    print("ERROR: nssm.exe not found!")
    print("Download from: https://nssm.cc/download")
    print("Place nssm.exe in PATH or in the scripts/ directory")
    sys.exit(1)


def get_project_dir() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def install():
    nssm = find_nssm()
    project_dir = get_project_dir()
    python_exe = sys.executable

    print(f"Installing {SERVICE_NAME}...")
    print(f"  Python: {python_exe}")
    print(f"  Project: {project_dir}")

    # Install service
    subprocess.run([nssm, "install", SERVICE_NAME, python_exe, "main.py"], check=True)

    # Configure service
    subprocess.run([nssm, "set", SERVICE_NAME, "AppDirectory", project_dir], check=True)
    subprocess.run([nssm, "set", SERVICE_NAME, "DisplayName", DISPLAY_NAME], check=True)
    subprocess.run([nssm, "set", SERVICE_NAME, "Description", DESCRIPTION], check=True)
    subprocess.run([nssm, "set", SERVICE_NAME, "Start", "SERVICE_AUTO_START"], check=True)

    # Set environment
    env_extra = f"PYTHONPATH={project_dir}"
    subprocess.run([nssm, "set", SERVICE_NAME, "AppEnvironmentExtra", env_extra], check=True)

    # Logging
    logs_dir = os.path.join(project_dir, "logs")
    os.makedirs(logs_dir, exist_ok=True)
    subprocess.run([nssm, "set", SERVICE_NAME, "AppStdout", os.path.join(logs_dir, "service_stdout.log")], check=True)
    subprocess.run([nssm, "set", SERVICE_NAME, "AppStderr", os.path.join(logs_dir, "service_stderr.log")], check=True)
    subprocess.run([nssm, "set", SERVICE_NAME, "AppRotateFiles", "1"], check=True)
    subprocess.run([nssm, "set", SERVICE_NAME, "AppRotateBytes", "10485760"], check=True)  # 10MB

    # Restart on failure
    subprocess.run([nssm, "set", SERVICE_NAME, "AppExit", "Default", "Restart"], check=True)
    subprocess.run([nssm, "set", SERVICE_NAME, "AppRestartDelay", "5000"], check=True)

    print(f"\n{SERVICE_NAME} installed successfully!")
    print(f"Start with: python scripts/install_service.py start")
    print(f"Or: nssm start {SERVICE_NAME}")


def uninstall():
    nssm = find_nssm()
    print(f"Uninstalling {SERVICE_NAME}...")
    subprocess.run([nssm, "stop", SERVICE_NAME], check=False)
    subprocess.run([nssm, "remove", SERVICE_NAME, "confirm"], check=True)
    print(f"{SERVICE_NAME} uninstalled.")


def start():
    nssm = find_nssm()
    subprocess.run([nssm, "start", SERVICE_NAME], check=True)
    print(f"{SERVICE_NAME} started.")


def stop():
    nssm = find_nssm()
    subprocess.run([nssm, "stop", SERVICE_NAME], check=True)
    print(f"{SERVICE_NAME} stopped.")


def restart():
    nssm = find_nssm()
    subprocess.run([nssm, "restart", SERVICE_NAME], check=True)
    print(f"{SERVICE_NAME} restarted.")


def status():
    nssm = find_nssm()
    result = subprocess.run([nssm, "status", SERVICE_NAME], capture_output=True, text=True)
    print(f"{SERVICE_NAME}: {result.stdout.strip()}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/install_service.py [install|uninstall|start|stop|restart|status]")
        sys.exit(1)

    commands = {
        "install": install,
        "uninstall": uninstall,
        "start": start,
        "stop": stop,
        "restart": restart,
        "status": status,
    }

    cmd = sys.argv[1].lower()
    if cmd not in commands:
        print(f"Unknown command: {cmd}")
        print(f"Available: {', '.join(commands.keys())}")
        sys.exit(1)

    commands[cmd]()
