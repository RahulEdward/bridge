"""
MT5 Popup Killer — runs as a background thread in the main gateway process.

Continuously monitors for MT5 login/account popups and closes them immediately.
This runs in the MAIN process (not worker) so it has full desktop access.
"""

import threading
import time
import logging

logger = logging.getLogger(__name__)

_running = False
_thread = None

POPUP_TITLES = [
    "open an account",
    "login",
    "authorization",
    "create an account",
    "connect to trade account",
    "trading account login",
    "sign in",
    "new account",
    "welcome to",
    "update",
    "restart",
    "live update",
]


def _killer_loop():
    global _running
    try:
        import win32gui
        import win32con
    except ImportError:
        logger.warning("win32gui not available — popup killer disabled")
        return

    logger.info("Popup killer started")

    while _running:
        try:
            found = []

            def enum_callback(hwnd, results):
                if win32gui.IsWindowVisible(hwnd):
                    title = win32gui.GetWindowText(hwnd)
                    if title:
                        title_lower = title.lower()
                        for popup in POPUP_TITLES:
                            if popup in title_lower:
                                results.append((hwnd, title))
                return True

            win32gui.EnumWindows(enum_callback, found)

            for hwnd, title in found:
                logger.warning(f"Popup detected: '{title}' — closing")
                try:
                    win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
                except Exception:
                    pass

        except Exception as e:
            logger.error(f"Popup killer error: {e}")

        time.sleep(0.5)

    logger.info("Popup killer stopped")


def start():
    global _running, _thread
    if _running:
        return
    _running = True
    _thread = threading.Thread(target=_killer_loop, daemon=True)
    _thread.start()


def stop():
    global _running
    _running = False
