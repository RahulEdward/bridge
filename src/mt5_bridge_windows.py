"""
Windows MT5 Bridge — per-account subprocess worker.
Worker uses mt5.initialize(path, login, password, server) directly.
No manual terminal launch — MT5 API handles it internally.
"""

import asyncio
import json
import logging
import os
import shutil
import sys
from typing import Optional, Dict, List, Any

from src.models import Position, Order, CandleData, TickData, OrderType, TimeFrame
from src.config import settings

logger = logging.getLogger(__name__)

PYTHON_EXE   = sys.executable
WORKER_SCRIPT = os.path.join(os.path.dirname(__file__), "mt5_worker.py")


class MT5Bridge:
    def __init__(self, account_id: str, terminal_path: str):
        self.account_id    = account_id
        self.terminal_path = terminal_path
        self._process      = None
        self._connected    = False
        self._req_counter  = 0
        self._pending: Dict[int, asyncio.Future] = {}
        self._reader_task  = None
        self._lock         = asyncio.Lock()

    # ── INSTANCE SETUP ────────────────────────────────────────────────────────

    def _prepare_instance(self) -> str:
        """Clone template if needed. Returns terminal64.exe path."""
        instance_dir = self.terminal_path
        terminal_exe = os.path.join(instance_dir, "terminal64.exe")

        if not os.path.exists(terminal_exe):
            template = settings.mt5_template_path
            if not os.path.exists(os.path.join(template, "terminal64.exe")):
                raise FileNotFoundError(f"MT5 template not found: {template}")
            logger.info(f"Cloning template → {instance_dir}")
            shutil.copytree(template, instance_dir)

        # Portable marker
        portable = os.path.join(instance_dir, "portable")
        if not os.path.exists(portable):
            open(portable, "w").close()

        logger.info(f"Instance ready: {instance_dir}")
        return terminal_exe

    def _write_all_credentials(self, terminal_exe: str, login: int, password: str, server: str):
        """Write credentials to instance dir AND AppData dir (MT5 reads from both)."""
        instance_dir = os.path.dirname(terminal_exe)
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

        # Write to instance config dir
        config_dir = os.path.join(instance_dir, "config")
        os.makedirs(config_dir, exist_ok=True)
        with open(os.path.join(config_dir, "common.ini"), "w") as f:
            f.write(ini_content)

        # Write to AppData config dir (MT5 uses this in non-portable mode)
        try:
            appdata_base = os.path.join(os.environ.get("APPDATA", ""), "MetaQuotes", "Terminal")
            if os.path.exists(appdata_base):
                for folder in os.listdir(appdata_base):
                    origin_file = os.path.join(appdata_base, folder, "origin.txt")
                    if not os.path.exists(origin_file):
                        continue
                    with open(origin_file, "r") as f:
                        origin = f.read().strip()
                    if os.path.normcase(origin) == os.path.normcase(instance_dir):
                        appdata_config = os.path.join(appdata_base, folder, "config")
                        os.makedirs(appdata_config, exist_ok=True)
                        with open(os.path.join(appdata_config, "common.ini"), "w") as f:
                            f.write(ini_content)
                        logger.info(f"Credentials written to AppData for {self.account_id}")
                        break
        except Exception as e:
            logger.warning(f"AppData credentials write: {e}")

        logger.info(f"Credentials written for {self.account_id}: login={login} server={server}")

    # ── WORKER SUBPROCESS ─────────────────────────────────────────────────────

    async def _start_worker(self):
        import subprocess
        self._process = subprocess.Popen(
            [PYTHON_EXE, WORKER_SCRIPT],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, bufsize=1,
        )
        logger.info(f"Worker started for {self.account_id} (PID: {self._process.pid})")
        self._reader_task = asyncio.create_task(self._read_responses())

        ready = asyncio.get_running_loop().create_future()
        self._pending[-1] = ready
        try:
            await asyncio.wait_for(ready, timeout=30)
        except asyncio.TimeoutError:
            raise ConnectionError("Worker failed to start")

    async def _read_responses(self):
        loop = asyncio.get_running_loop()
        try:
            while self._process and self._process.poll() is None:
                line = await loop.run_in_executor(None, self._process.stdout.readline)
                if not line:
                    break
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    if data.get("type") == "ready":
                        if -1 in self._pending:
                            self._pending[-1].set_result(data)
                            del self._pending[-1]
                        continue
                    req_id = data.get("id", 0)
                    if req_id in self._pending:
                        self._pending[req_id].set_result(data)
                        del self._pending[req_id]
                except json.JSONDecodeError:
                    pass
        except Exception as e:
            logger.error(f"Reader error for {self.account_id}: {e}")
        finally:
            for f in list(self._pending.values()):
                if not f.done():
                    f.set_exception(ConnectionError("Worker died"))
            self._pending.clear()

    async def _send(self, cmd: str, params: dict = None, timeout: float = 30) -> dict:
        if not self._process or self._process.poll() is not None:
            raise ConnectionError("Worker not running")
        async with self._lock:
            self._req_counter += 1
            req_id = self._req_counter
        loop   = asyncio.get_running_loop()
        future = loop.create_future()
        self._pending[req_id] = future
        msg = json.dumps({"id": req_id, "cmd": cmd, "params": params or {}}) + "\n"
        try:
            self._process.stdin.write(msg)
            self._process.stdin.flush()
        except (BrokenPipeError, OSError) as e:
            self._pending.pop(req_id, None)
            raise ConnectionError(f"Pipe broken: {e}")
        try:
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            self._pending.pop(req_id, None)
            raise ConnectionError(f"'{cmd}' timed out ({timeout}s)")

    async def _kill_worker(self):
        if self._reader_task:
            self._reader_task.cancel()
            try:
                await asyncio.shield(asyncio.sleep(0))
            except Exception:
                pass
            self._reader_task = None
        if self._process:
            try:
                self._process.terminate()
                self._process.wait(timeout=5)
            except Exception:
                try:
                    self._process.kill()
                except Exception:
                    pass
            self._process = None

    # ── PUBLIC API ────────────────────────────────────────────────────────────

    async def connect(self, login: int, password: str, server: str, investor_mode: bool = False) -> bool:
        try:
            terminal_exe = self._prepare_instance()
            # Write credentials to BOTH instance dir AND AppData dir before connecting
            self._write_all_credentials(terminal_exe, login, password, server)
            await self._start_worker()
            result = await self._send("connect", {
                "terminal_path": terminal_exe,
                "login":         login,
                "password":      password,
                "server":        server,
            }, timeout=900)   # 15 min — first launch: compile (3min) + server discovery
            if not result.get("success"):
                raise ConnectionError(result.get("error", "Unknown error"))
            self._connected = True
            logger.info(f"Connected: {self.account_id}")
            # Auto-enable AutoTrading after connect
            try:
                await self._send("enable_trading", timeout=10)
                logger.info(f"AutoTrading enabled for {self.account_id}")
            except Exception as e:
                logger.warning(f"AutoTrading enable warning: {e}")
            return True
        except Exception as e:
            logger.error(f"Connect failed for {self.account_id}: {e}")
            self._connected = False
            await self._kill_worker()
            raise

    async def disconnect(self) -> bool:
        try:
            if self._process and self._process.poll() is None:
                try:
                    await self._send("disconnect", timeout=5)
                except Exception:
                    pass
            await self._kill_worker()
            self._connected = False
            return True
        except Exception as e:
            logger.error(f"Disconnect error: {e}")
            return False

    def is_connected(self) -> bool:
        return self._connected and self._process is not None and self._process.poll() is None

    async def get_account_info(self) -> Dict[str, Any]:
        r = await self._send("account_info")
        if not r.get("success"):
            raise ConnectionError(r.get("error"))
        return r["data"]

    async def get_positions(self) -> List[Position]:
        r = await self._send("positions")
        if not r.get("success"):
            raise ConnectionError(r.get("error"))
        return [Position(**p) for p in r["data"]]

    async def get_orders(self) -> List[Order]:
        r = await self._send("orders")
        if not r.get("success"):
            raise ConnectionError(r.get("error"))
        return [Order(**o) for o in r["data"]]

    async def get_candles(self, symbol: str, timeframe: TimeFrame, count: int) -> List[CandleData]:
        r = await self._send("candles", {"symbol": symbol, "timeframe": timeframe.value, "count": count})
        if not r.get("success"):
            raise ConnectionError(r.get("error"))
        return [CandleData(**c) for c in r["data"]]

    async def get_tick(self, symbol: str) -> TickData:
        r = await self._send("tick", {"symbol": symbol})
        if not r.get("success"):
            raise ValueError(r.get("error"))
        return TickData(**r["data"])

    async def place_order(self, symbol: str, order_type: OrderType, volume: float,
                          price=None, sl=None, tp=None, deviation=20, magic=0, comment="") -> Dict[str, Any]:
        r = await self._send("place_order", {
            "symbol": symbol, "order_type": order_type.value,
            "volume": volume, "price": price, "sl": sl, "tp": tp,
            "deviation": deviation, "magic": magic, "comment": comment,
        })
        return {"success": r.get("success", False), "order_ticket": r.get("order_ticket"),
                "retcode": r.get("retcode"), "message": r.get("message", r.get("error", ""))}

    async def close_position(self, ticket: int, volume=None) -> Dict[str, Any]:
        r = await self._send("close_position", {"ticket": ticket, "volume": volume})
        return {"success": r.get("success", False), "order_ticket": r.get("order_ticket"),
                "retcode": r.get("retcode"), "message": r.get("message", r.get("error", ""))}

    async def modify_position(self, ticket: int, sl=None, tp=None) -> Dict[str, Any]:
        r = await self._send("modify_position", {"ticket": ticket, "sl": sl, "tp": tp})
        return {"success": r.get("success", False), "order_ticket": r.get("order_ticket"),
                "retcode": r.get("retcode"), "message": r.get("message", r.get("error", ""))}

    async def modify_order(self, ticket: int, price=None, sl=None, tp=None) -> Dict[str, Any]:
        r = await self._send("modify_position", {"ticket": ticket, "sl": sl, "tp": tp})
        return {"success": r.get("success", False), "order_ticket": r.get("order_ticket"),
                "retcode": r.get("retcode"), "message": r.get("message", r.get("error", ""))}
