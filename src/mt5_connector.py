"""
MT5 Connector — handles the connection lifecycle for a single MT5 account.
Wraps the bridge layer with retry logic, auto-trading enablement, and health monitoring.
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional, Dict, Any

from src.config import settings, encrypt_credentials, decrypt_credentials
from src.models import AccountStatus
from src.instance_manager import instance_manager

logger = logging.getLogger(__name__)


class MT5Connector:
    """
    High-level connector for a single MT5 account.
    Manages: instance creation → credential injection → bridge connection → auto-trading.
    """

    def __init__(self, account_id: str, login: int, server: str):
        self.account_id = account_id
        self.login = login
        self.server = server
        self.status = AccountStatus.PENDING
        self.connected_at: Optional[datetime] = None
        self.last_error: Optional[str] = None
        self.restart_count = 0
        self.last_restart: Optional[datetime] = None
        self._bridge = None

    async def connect(self, password: str, investor_mode: bool = False) -> bool:
        """
        Full connection flow:
        1. Create/verify MT5 instance
        2. Inject credentials + AutoTrading config
        3. Start worker subprocess
        4. Connect via MT5 Python API
        5. Enable AutoTrading
        """
        self.status = AccountStatus.STARTING
        logger.info(f"[{self.account_id}] Starting connection: login={self.login} server={self.server}")

        try:
            # Step 1: Create instance
            instance = await instance_manager.create_instance(self.account_id)

            # Step 2: Inject credentials
            instance_manager.inject_credentials(
                self.account_id, self.login, password, self.server
            )
            instance_manager.inject_autotrading_config(self.account_id)

            # Step 3: Create bridge and connect
            bridge = self._create_bridge(instance.terminal_exe)
            connected = await bridge.connect(
                login=self.login,
                password=password,
                server=self.server,
                investor_mode=investor_mode,
            )

            if not connected:
                raise ConnectionError("Bridge connect returned False")

            self._bridge = bridge
            self.status = AccountStatus.CONNECTED
            self.connected_at = datetime.now()
            self.last_error = None

            # Track process
            if hasattr(bridge, '_process') and bridge._process:
                instance_manager.update_process(self.account_id, bridge._process.pid)

            logger.info(f"[{self.account_id}] Connected successfully")
            return True

        except Exception as e:
            self.status = AccountStatus.ERROR
            self.last_error = str(e)
            logger.error(f"[{self.account_id}] Connection failed: {e}")
            raise

    async def disconnect(self) -> bool:
        """Gracefully disconnect and stop the worker."""
        try:
            if self._bridge:
                await self._bridge.disconnect()
                self._bridge = None
            instance_manager.mark_stopped(self.account_id)
            self.status = AccountStatus.STOPPED
            logger.info(f"[{self.account_id}] Disconnected")
            return True
        except Exception as e:
            logger.error(f"[{self.account_id}] Disconnect error: {e}")
            return False

    async def reconnect(self, password: str, investor_mode: bool = False) -> bool:
        """Disconnect then reconnect with retry."""
        self.restart_count += 1
        self.last_restart = datetime.now()
        logger.info(f"[{self.account_id}] Reconnecting (attempt #{self.restart_count})")

        await self.disconnect()
        await asyncio.sleep(2)

        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                return await self.connect(password, investor_mode)
            except Exception as e:
                logger.warning(f"[{self.account_id}] Reconnect attempt {attempt}/{max_retries} failed: {e}")
                if attempt < max_retries:
                    await asyncio.sleep(5 * attempt)

        self.status = AccountStatus.ERROR
        self.last_error = "Exceeded max reconnect attempts"
        instance_manager.mark_crashed(self.account_id)
        return False

    def is_connected(self) -> bool:
        return (
            self._bridge is not None
            and self._bridge.is_connected()
            and self.status == AccountStatus.CONNECTED
        )

    @property
    def bridge(self):
        return self._bridge

    def _create_bridge(self, terminal_path: str):
        """Create the appropriate bridge based on platform."""
        import sys
        if sys.platform == "win32":
            try:
                from src.mt5_bridge_windows import MT5Bridge
                return MT5Bridge(self.account_id, terminal_path)
            except ImportError:
                logger.warning("MetaTrader5 not installed — using mock bridge")
                from src.mt5_bridge import MT5Bridge
                return MT5Bridge(self.account_id, terminal_path)
        else:
            from src.mt5_bridge import MT5Bridge
            return MT5Bridge(self.account_id, terminal_path)
