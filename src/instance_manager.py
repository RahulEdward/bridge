"""
MT5 Instance Manager — handles cloning, process spawning, and lifecycle
for isolated per-user MT5 terminal instances on Windows VPS.

Each user gets: C:\\MT5_INSTANCES\\{user_id}\\terminal64.exe
"""

import asyncio
import logging
import os
import shutil
import time
import json
from datetime import datetime
from typing import Dict, Optional, List
from dataclasses import dataclass, field, asdict

import psutil

from src.config import settings

logger = logging.getLogger(__name__)

INSTANCES_BASE = settings.mt5_base_path  # C:\MT5_INSTANCES
TEMPLATE_PATH = settings.mt5_template_path  # C:\MT5Template


@dataclass
class InstanceInfo:
    user_id: str
    instance_dir: str
    terminal_exe: str
    process_id: Optional[int] = None
    status: str = "created"  # created | running | stopped | crashed | error
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_started: Optional[str] = None
    crash_count: int = 0
    last_crash: Optional[str] = None


class MT5InstanceManager:
    """Manages the lifecycle of isolated MT5 terminal instances per user."""

    def __init__(self):
        self._instances: Dict[str, InstanceInfo] = {}
        self._lock = asyncio.Lock()
        self._state_file = os.path.join("data", "instances_state.json")

    async def initialize(self):
        """Load persisted instance state on startup."""
        os.makedirs(INSTANCES_BASE, exist_ok=True)
        os.makedirs("data", exist_ok=True)
        await self._load_state()
        logger.info(f"Instance Manager initialized — {len(self._instances)} instances tracked")

    # ── INSTANCE CREATION ─────────────────────────────────────────────────

    async def create_instance(self, user_id: str) -> InstanceInfo:
        """Clone MT5 template into a unique directory for this user."""
        async with self._lock:
            if user_id in self._instances:
                existing = self._instances[user_id]
                if existing.status in ("running", "created"):
                    logger.info(f"Instance already exists for {user_id}: {existing.status}")
                    return existing

            instance_dir = os.path.join(INSTANCES_BASE, f"MT5_{user_id}")
            terminal_exe = os.path.join(instance_dir, "terminal64.exe")

            if not os.path.exists(terminal_exe):
                template_exe = os.path.join(TEMPLATE_PATH, "terminal64.exe")
                if not os.path.exists(template_exe):
                    raise FileNotFoundError(
                        f"MT5 template not found at {TEMPLATE_PATH}. "
                        "Install MetaTrader 5 there first."
                    )

                logger.info(f"Cloning MT5 template → {instance_dir}")
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(
                    None, lambda: shutil.copytree(TEMPLATE_PATH, instance_dir)
                )

            # Create portable marker — forces MT5 to use local data folder
            portable_marker = os.path.join(instance_dir, "portable")
            if not os.path.exists(portable_marker):
                with open(portable_marker, "w") as f:
                    f.write("")

            info = InstanceInfo(
                user_id=user_id,
                instance_dir=instance_dir,
                terminal_exe=terminal_exe,
            )
            self._instances[user_id] = info
            await self._save_state()

            logger.info(f"Instance created for {user_id}: {instance_dir}")
            return info

    def get_instance(self, user_id: str) -> Optional[InstanceInfo]:
        return self._instances.get(user_id)

    def get_all_instances(self) -> List[InstanceInfo]:
        return list(self._instances.values())

    # ── CONFIG INJECTION ──────────────────────────────────────────────────

    def inject_credentials(
        self, user_id: str, login: int, password: str, server: str
    ):
        """Write login credentials + AutoTrading config into the instance's config files."""
        info = self._instances.get(user_id)
        if not info:
            raise ValueError(f"No instance for user {user_id}")

        ini_content = (
            "[Common]\n"
            f"Login={login}\n"
            f"Password={password}\n"
            f"Server={server}\n"
            "AutoLogin=1\n"
            "NewsEnable=0\n"
            "ProxyEnable=0\n"
            "ExpertAdvisors=1\n"
            "DLLsAllowed=1\n"
            "AutoTrading=1\n"
        )

        # Write to instance config dir (portable mode reads from here)
        config_dir = os.path.join(info.instance_dir, "config")
        os.makedirs(config_dir, exist_ok=True)
        ini_path = os.path.join(config_dir, "common.ini")
        with open(ini_path, "w") as f:
            f.write(ini_content)

        logger.info(f"Credentials injected for {user_id}: login={login} server={server}")

    def inject_autotrading_config(self, user_id: str):
        """Ensure ExpertAdvisors=1 is set in all relevant config locations."""
        info = self._instances.get(user_id)
        if not info:
            return

        paths_to_update = []

        # Instance config dir
        ini = os.path.join(info.instance_dir, "config", "common.ini")
        if os.path.exists(ini):
            paths_to_update.append(ini)

        # AppData config dirs (MT5 sometimes reads from here even in portable mode)
        appdata = os.environ.get("APPDATA", "")
        base = os.path.join(appdata, "MetaQuotes", "Terminal")
        if os.path.exists(base):
            for folder in os.listdir(base):
                origin_file = os.path.join(base, folder, "origin.txt")
                if os.path.exists(origin_file):
                    with open(origin_file, "r") as f:
                        origin = f.read().strip()
                    if os.path.normcase(origin) == os.path.normcase(info.instance_dir):
                        appdata_ini = os.path.join(base, folder, "config", "common.ini")
                        if appdata_ini not in paths_to_update:
                            paths_to_update.append(appdata_ini)

        for path in paths_to_update:
            self._set_ini_value(path, "ExpertAdvisors", "1")
            self._set_ini_value(path, "DLLsAllowed", "1")

        logger.info(f"AutoTrading config injected for {user_id} ({len(paths_to_update)} files)")

    @staticmethod
    def _set_ini_value(ini_path: str, key: str, value: str):
        """Set a key=value in an INI file under [Common] section."""
        if not os.path.exists(ini_path):
            os.makedirs(os.path.dirname(ini_path), exist_ok=True)
            with open(ini_path, "w") as f:
                f.write(f"[Common]\n{key}={value}\n")
            return

        lines = []
        found = False
        with open(ini_path, "r") as f:
            for line in f:
                if line.strip().startswith(f"{key}="):
                    lines.append(f"{key}={value}\n")
                    found = True
                else:
                    lines.append(line)

        if not found:
            new_lines = []
            for line in lines:
                new_lines.append(line)
                if line.strip() == "[Common]":
                    new_lines.append(f"{key}={value}\n")
            lines = new_lines

        with open(ini_path, "w") as f:
            f.writelines(lines)

    # ── PROCESS TRACKING ──────────────────────────────────────────────────

    def update_process(self, user_id: str, pid: int):
        """Record the worker process ID for this instance."""
        info = self._instances.get(user_id)
        if info:
            info.process_id = pid
            info.status = "running"
            info.last_started = datetime.now().isoformat()

    def mark_stopped(self, user_id: str):
        info = self._instances.get(user_id)
        if info:
            info.process_id = None
            info.status = "stopped"

    def mark_crashed(self, user_id: str):
        info = self._instances.get(user_id)
        if info:
            info.process_id = None
            info.status = "crashed"
            info.crash_count += 1
            info.last_crash = datetime.now().isoformat()

    def is_process_alive(self, user_id: str) -> bool:
        """Check if the worker subprocess is still running."""
        info = self._instances.get(user_id)
        if not info or not info.process_id:
            return False
        try:
            proc = psutil.Process(info.process_id)
            return proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False

    # ── CLEANUP ───────────────────────────────────────────────────────────

    async def destroy_instance(self, user_id: str):
        """Remove instance directory and tracking data."""
        async with self._lock:
            info = self._instances.pop(user_id, None)
            if not info:
                return

            # Kill process if running
            if info.process_id:
                try:
                    proc = psutil.Process(info.process_id)
                    proc.terminate()
                    proc.wait(timeout=5)
                except Exception:
                    pass

            # Remove directory
            if os.path.exists(info.instance_dir):
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(
                    None, lambda: shutil.rmtree(info.instance_dir, ignore_errors=True)
                )

            await self._save_state()
            logger.info(f"Instance destroyed for {user_id}")

    # ── STATE PERSISTENCE ─────────────────────────────────────────────────

    async def _save_state(self):
        try:
            data = []
            for info in self._instances.values():
                data.append(asdict(info))
            with open(self._state_file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save instance state: {e}")

    async def _load_state(self):
        if not os.path.exists(self._state_file):
            return
        try:
            with open(self._state_file, "r") as f:
                data = json.load(f)
            for item in data:
                info = InstanceInfo(**item)
                # Reset process tracking — processes don't survive restarts
                info.process_id = None
                if info.status == "running":
                    info.status = "stopped"
                self._instances[info.user_id] = info
            logger.info(f"Loaded {len(self._instances)} instance records")
        except Exception as e:
            logger.error(f"Failed to load instance state: {e}")


# Singleton
instance_manager = MT5InstanceManager()
