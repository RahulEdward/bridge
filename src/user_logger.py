"""
Per-User Logger — creates isolated log files for each MT5 account.
Logs: login status, trades, errors, connection events.
"""

import logging
import os
from datetime import datetime
from typing import Dict

LOGS_DIR = "logs"


class UserLoggerManager:
    """Manages per-user log files."""

    def __init__(self):
        self._loggers: Dict[str, logging.Logger] = {}
        os.makedirs(LOGS_DIR, exist_ok=True)

    def get_logger(self, user_id: str) -> logging.Logger:
        """Get or create a logger for a specific user."""
        if user_id in self._loggers:
            return self._loggers[user_id]

        logger_name = f"mt5.user.{user_id}"
        user_logger = logging.getLogger(logger_name)
        user_logger.setLevel(logging.DEBUG)

        # Prevent duplicate handlers
        if not user_logger.handlers:
            # File handler — per user
            log_file = os.path.join(LOGS_DIR, f"{user_id}.log")
            fh = logging.FileHandler(log_file, encoding="utf-8")
            fh.setLevel(logging.DEBUG)
            fh.setFormatter(logging.Formatter(
                "%(asctime)s | %(levelname)-8s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            ))
            user_logger.addHandler(fh)

            # Don't propagate to root logger
            user_logger.propagate = False

        self._loggers[user_id] = user_logger
        return user_logger

    def log_connection(self, user_id: str, login: int, server: str, success: bool, error: str = None):
        lg = self.get_logger(user_id)
        if success:
            lg.info(f"CONNECTED | login={login} server={server}")
        else:
            lg.error(f"CONNECTION FAILED | login={login} server={server} error={error}")

    def log_trade(self, user_id: str, action: str, symbol: str, volume: float,
                  ticket: int = None, success: bool = True, message: str = ""):
        lg = self.get_logger(user_id)
        status = "OK" if success else "FAIL"
        lg.info(f"TRADE {status} | {action} {volume} {symbol} ticket={ticket} {message}")

    def log_error(self, user_id: str, context: str, error: str):
        lg = self.get_logger(user_id)
        lg.error(f"ERROR | {context}: {error}")

    def log_event(self, user_id: str, event: str, details: str = ""):
        lg = self.get_logger(user_id)
        lg.info(f"EVENT | {event} {details}")


# Singleton
user_logger = UserLoggerManager()
