"""
MT5 Terminal Manager — orchestrates the full lifecycle of multi-user MT5 accounts.
Integrates: InstanceManager, MT5Connector, TradingEngine, QueueManager, UserLogger.
"""

import asyncio
import logging
import os
import sys
import json
from datetime import datetime
from typing import Dict, Optional, List
from dataclasses import dataclass, field

from src.config import settings, encrypt_credentials, decrypt_credentials
from src.models import AccountStatus
from src.instance_manager import instance_manager
from src.mt5_connector import MT5Connector
from src.trading_engine import TradingEngine
from src.queue_manager import queue_manager
from src.user_logger import user_logger

logger = logging.getLogger(__name__)

if sys.platform == "win32":
    try:
        import MetaTrader5
        from src.mt5_bridge_windows import MT5Bridge
        _USING_REAL_BRIDGE = True
        logger.info("Using Windows MT5 Bridge with real MetaTrader5 integration")
    except ImportError:
        logger.warning("MetaTrader5 package not installed — falling back to mock bridge")
        from src.mt5_bridge import MT5Bridge
        _USING_REAL_BRIDGE = False
else:
    logger.info("Non-Windows platform — using mock MT5 Bridge for development")
    from src.mt5_bridge import MT5Bridge
    _USING_REAL_BRIDGE = False

from src.mt5_bridge import MT5Connection


@dataclass
class AccountConfig:
    account_id: str
    login: int
    server: str
    encrypted_password: str
    investor_mode: bool = False
    terminal_path: str = ""
    created_at: datetime = field(default_factory=datetime.now)


class MT5TerminalManager:
    def __init__(self):
        self._accounts: Dict[str, AccountConfig] = {}
        self._connections: Dict[str, MT5Connection] = {}
        self._bridges: Dict[str, MT5Bridge] = {}
        self._connectors: Dict[str, MT5Connector] = {}
        self._engines: Dict[str, TradingEngine] = {}
        self._health_task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self):
        self._running = True

        # Initialize sub-systems
        await instance_manager.initialize()
        await queue_manager.start()

        # Register queue handlers
        queue_manager.register_handler("create", self._handle_queue_create)
        queue_manager.register_handler("start", self._handle_queue_start)
        queue_manager.register_handler("stop", self._handle_queue_stop)
        queue_manager.register_handler("restart", self._handle_queue_restart)

        # Start health check loop
        self._health_task = asyncio.create_task(self._health_check_loop())

        logger.info("Terminal Manager started")
        await self._load_accounts()

    async def stop(self):
        self._running = False
        if self._health_task:
            self._health_task.cancel()
            try:
                await self._health_task
            except asyncio.CancelledError:
                pass

        # Stop all engines
        for engine in list(self._engines.values()):
            try:
                await engine.stop()
            except Exception:
                pass

        # Stop all connectors
        for connector in list(self._connectors.values()):
            try:
                await connector.disconnect()
            except Exception:
                pass

        # Stop all bridges (legacy)
        for account_id in list(self._bridges.keys()):
            await self.stop_account(account_id)

        await queue_manager.stop()
        logger.info("Terminal Manager stopped")

    # ── ACCOUNT PERSISTENCE ───────────────────────────────────────────────

    async def _load_accounts(self):
        data_dir = os.path.dirname(settings.db_path)
        accounts_file = os.path.join(data_dir, "accounts.json")

        if os.path.exists(accounts_file):
            try:
                with open(accounts_file, "r") as f:
                    data = json.load(f)
                    for acc_data in data:
                        config = AccountConfig(
                            account_id=acc_data["account_id"],
                            login=acc_data["login"],
                            server=acc_data["server"],
                            encrypted_password=acc_data["encrypted_password"],
                            investor_mode=acc_data.get("investor_mode", False),
                            terminal_path=acc_data.get("terminal_path", ""),
                        )
                        self._accounts[config.account_id] = config
                        logger.info(f"Loaded account config: {config.account_id}")

                    # Auto-start all accounts on startup
                    for acc_data in data:
                        account_id = acc_data["account_id"]
                        logger.info(f"Auto-starting account: {account_id}")
                        asyncio.create_task(self._start_account_async(account_id, password=None))
            except Exception as e:
                logger.error(f"Failed to load accounts: {e}")

    async def _save_accounts(self):
        data_dir = os.path.dirname(settings.db_path)
        os.makedirs(data_dir, exist_ok=True)
        accounts_file = os.path.join(data_dir, "accounts.json")

        try:
            data = []
            for config in self._accounts.values():
                data.append({
                    "account_id": config.account_id,
                    "login": config.login,
                    "server": config.server,
                    "encrypted_password": config.encrypted_password,
                    "investor_mode": config.investor_mode,
                    "terminal_path": config.terminal_path,
                })
            with open(accounts_file, "w") as f:
                json.dump(data, f, indent=2)
            logger.info("Accounts saved successfully")
        except Exception as e:
            logger.error(f"Failed to save accounts: {e}")

    # ── ACCOUNT LIFECYCLE ─────────────────────────────────────────────────

    async def create_account(
        self,
        account_id: str,
        login: int,
        password: str,
        server: str,
        investor_mode: bool = False,
    ) -> MT5Connection:
        # Check duplicate account_id
        if account_id in self._accounts:
            raise ValueError(f"Account ID '{account_id}' already exists")

        # Check duplicate login+server
        for existing in self._accounts.values():
            if existing.login == login and existing.server == server:
                raise ValueError(
                    f"Login {login} on server '{server}' is already connected as '{existing.account_id}'"
                )

        terminal_path = os.path.join(settings.mt5_base_path, f"MT5_{account_id}")
        encrypted_password = encrypt_credentials(password)

        config = AccountConfig(
            account_id=account_id,
            login=login,
            server=server,
            encrypted_password=encrypted_password,
            investor_mode=investor_mode,
            terminal_path=terminal_path,
        )
        self._accounts[account_id] = config

        connection = MT5Connection(
            account_id=account_id,
            login=login,
            server=server,
            status=AccountStatus.PENDING,
        )
        self._connections[account_id] = connection

        await self._save_accounts()

        user_logger.log_event(account_id, "ACCOUNT_CREATED", f"login={login} server={server}")
        logger.info(f"Account created: {account_id}, login={login}, server={server}")

        # Start connection via queue (prevents race conditions)
        asyncio.create_task(self._start_account_async(account_id, password))

        return connection

    async def _start_account_async(self, account_id: str, password: str):
        try:
            await self.start_account(account_id, password)
        except Exception as e:
            logger.error(f"Failed to start account {account_id}: {e}")
            user_logger.log_error(account_id, "START_FAILED", str(e))
            if account_id in self._connections:
                self._connections[account_id].status = AccountStatus.ERROR
                self._connections[account_id].last_error = str(e)

    async def start_account(self, account_id: str, password: Optional[str] = None) -> MT5Connection:
        if account_id not in self._accounts:
            raise ValueError(f"Account {account_id} not found")

        config = self._accounts[account_id]

        if account_id not in self._connections:
            self._connections[account_id] = MT5Connection(
                account_id=account_id,
                login=config.login,
                server=config.server,
            )

        connection = self._connections[account_id]
        connection.status = AccountStatus.STARTING

        if password is None:
            password = decrypt_credentials(config.encrypted_password)

        bridge = MT5Bridge(account_id, config.terminal_path)

        try:
            await bridge.connect(
                login=config.login,
                password=password,
                server=config.server,
                investor_mode=config.investor_mode,
            )

            self._bridges[account_id] = bridge
            connection.status = AccountStatus.CONNECTED
            connection.connected_at = datetime.now()
            connection.last_error = None

            # Create and start trading engine
            engine = TradingEngine(account_id, bridge)
            await engine.start()
            self._engines[account_id] = engine

            user_logger.log_connection(account_id, config.login, config.server, success=True)
            logger.info(f"Account started successfully: {account_id}")

        except Exception as e:
            connection.status = AccountStatus.ERROR
            connection.last_error = str(e)
            user_logger.log_connection(account_id, config.login, config.server, success=False, error=str(e))
            logger.error(f"Failed to start account {account_id}: {e}")
            raise

        return connection

    async def stop_account(self, account_id: str) -> bool:
        # Stop trading engine
        if account_id in self._engines:
            try:
                await self._engines[account_id].stop()
            except Exception:
                pass
            del self._engines[account_id]

        # Disconnect bridge
        if account_id in self._bridges:
            bridge = self._bridges[account_id]
            await bridge.disconnect()
            del self._bridges[account_id]

        if account_id in self._connections:
            self._connections[account_id].status = AccountStatus.STOPPED

        user_logger.log_event(account_id, "ACCOUNT_STOPPED")
        logger.info(f"Account stopped: {account_id}")
        return True

    async def restart_account(self, account_id: str) -> MT5Connection:
        await self.stop_account(account_id)

        if account_id in self._connections:
            conn = self._connections[account_id]
            conn.restart_count += 1
            conn.last_restart = datetime.now()

        user_logger.log_event(account_id, "ACCOUNT_RESTARTING")
        return await self.start_account(account_id)

    # ── QUEUE HANDLERS ────────────────────────────────────────────────────

    async def _handle_queue_create(self, user_id: str, params: dict) -> dict:
        conn = await self.create_account(
            account_id=user_id,
            login=params["login"],
            password=params["password"],
            server=params["server"],
            investor_mode=params.get("investor_mode", False),
        )
        return {"status": conn.status.value}

    async def _handle_queue_start(self, user_id: str, params: dict) -> dict:
        conn = await self.start_account(user_id)
        return {"status": conn.status.value}

    async def _handle_queue_stop(self, user_id: str, params: dict) -> dict:
        await self.stop_account(user_id)
        return {"status": "stopped"}

    async def _handle_queue_restart(self, user_id: str, params: dict) -> dict:
        conn = await self.restart_account(user_id)
        return {"status": conn.status.value}

    # ── ACCESSORS ─────────────────────────────────────────────────────────

    def get_connection(self, account_id: str) -> Optional[MT5Connection]:
        return self._connections.get(account_id)

    def get_bridge(self, account_id: str) -> Optional[MT5Bridge]:
        return self._bridges.get(account_id)

    def get_engine(self, account_id: str) -> Optional[TradingEngine]:
        return self._engines.get(account_id)

    def get_all_connections(self) -> List[MT5Connection]:
        return list(self._connections.values())

    def get_active_count(self) -> int:
        return sum(
            1 for conn in self._connections.values()
            if conn.status == AccountStatus.CONNECTED
        )

    # ── HEALTH CHECK ──────────────────────────────────────────────────────

    async def _health_check_loop(self):
        while self._running:
            try:
                await asyncio.sleep(settings.health_check_interval)
                await self._perform_health_checks()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health check error: {e}")

    async def _perform_health_checks(self):
        for account_id, bridge in list(self._bridges.items()):
            try:
                if not bridge.is_connected():
                    logger.warning(f"Account {account_id} disconnected, attempting restart")
                    user_logger.log_error(account_id, "HEALTH_CHECK", "Connection lost — restarting")
                    conn = self._connections.get(account_id)

                    if conn and conn.restart_count < settings.max_restart_attempts:
                        if conn.last_restart:
                            time_since = (datetime.now() - conn.last_restart).total_seconds()
                            if time_since < settings.restart_cooldown:
                                continue

                        await self.restart_account(account_id)
                    else:
                        logger.error(f"Account {account_id} exceeded max restart attempts")
                        user_logger.log_error(
                            account_id, "MAX_RESTARTS", "Exceeded maximum restart attempts"
                        )
                        if conn:
                            conn.status = AccountStatus.ERROR
                            conn.last_error = "Exceeded maximum restart attempts"
            except Exception as e:
                logger.error(f"Health check failed for {account_id}: {e}")


terminal_manager = MT5TerminalManager()
