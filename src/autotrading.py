"""
AutoTrading Enabler — ensures the MT5 AutoTrading button is ON.

Strategy (in order of preference):
1. Config file injection: Write ExpertAdvisors=1 to common.ini (done during instance setup)
2. pywinauto automation: Click the AutoTrading button in the MT5 toolbar
3. Keyboard shortcut: Send Ctrl+E to toggle AutoTrading

This module provides the pywinauto fallback for cases where config injection alone
doesn't enable AutoTrading (some broker builds ignore the config).
"""

import logging
import time
import os
from typing import Optional

logger = logging.getLogger(__name__)


def enable_autotrading_via_ui(terminal_exe: str, timeout: int = 30) -> bool:
    """
    Use pywinauto to find the MT5 window and click the AutoTrading button.
    Falls back to Ctrl+E keyboard shortcut if button not found.
    Returns True if successful.
    """
    try:
        from pywinauto import Application, Desktop
        from pywinauto.keyboard import send_keys
    except ImportError:
        logger.warning("pywinauto not installed — UI automation unavailable")
        return False

    try:
        # Find the MT5 window by process
        instance_dir = os.path.dirname(terminal_exe)
        instance_name = os.path.basename(instance_dir)

        # Try to connect to existing MT5 process
        app = None
        for attempt in range(timeout // 2):
            try:
                app = Application(backend="uia").connect(
                    path=terminal_exe, timeout=2
                )
                break
            except Exception:
                time.sleep(2)

        if not app:
            logger.warning(f"Could not find MT5 window for {instance_name}")
            return False

        # Get the main window
        main_window = app.top_window()
        main_window.wait("ready", timeout=10)

        # Method 1: Try to find and click the AutoTrading toolbar button
        try:
            auto_trading_btn = main_window.child_window(
                title="AutoTrading", control_type="Button"
            )
            if auto_trading_btn.exists(timeout=3):
                auto_trading_btn.click()
                logger.info(f"AutoTrading button clicked for {instance_name}")
                time.sleep(1)
                return True
        except Exception:
            pass

        # Method 2: Try toolbar button by position (AutoTrading is usually in the Standard toolbar)
        try:
            toolbar = main_window.child_window(
                title="Standard", control_type="ToolBar"
            )
            if toolbar.exists(timeout=3):
                # AutoTrading button is typically the last button in Standard toolbar
                buttons = toolbar.children()
                for btn in buttons:
                    try:
                        if "auto" in btn.window_text().lower() or "trading" in btn.window_text().lower():
                            btn.click()
                            logger.info(f"AutoTrading toolbar button clicked for {instance_name}")
                            time.sleep(1)
                            return True
                    except Exception:
                        continue
        except Exception:
            pass

        # Method 3: Keyboard shortcut Ctrl+E (toggles AutoTrading in MT5)
        try:
            main_window.set_focus()
            time.sleep(0.5)
            send_keys("^e")  # Ctrl+E
            logger.info(f"Sent Ctrl+E to toggle AutoTrading for {instance_name}")
            time.sleep(1)
            return True
        except Exception as e:
            logger.warning(f"Keyboard shortcut failed: {e}")

        return False

    except Exception as e:
        logger.error(f"AutoTrading UI automation failed: {e}")
        return False


def write_autotrading_config(instance_dir: str) -> bool:
    """
    Write ExpertAdvisors=1 and related settings to the instance config.
    This is the primary method — called during instance setup.
    """
    config_dir = os.path.join(instance_dir, "config")
    os.makedirs(config_dir, exist_ok=True)
    ini_path = os.path.join(config_dir, "common.ini")

    settings_to_ensure = {
        "ExpertAdvisors": "1",
        "DLLsAllowed": "1",
        "AutoTrading": "1",
    }

    if os.path.exists(ini_path):
        with open(ini_path, "r") as f:
            lines = f.readlines()

        for key, value in settings_to_ensure.items():
            found = False
            new_lines = []
            for line in lines:
                if line.strip().startswith(f"{key}="):
                    new_lines.append(f"{key}={value}\n")
                    found = True
                else:
                    new_lines.append(line)
            if not found:
                # Add after [Common] section header
                final_lines = []
                for line in new_lines:
                    final_lines.append(line)
                    if line.strip() == "[Common]":
                        final_lines.append(f"{key}={value}\n")
                new_lines = final_lines
            lines = new_lines

        with open(ini_path, "w") as f:
            f.writelines(lines)
    else:
        content = "[Common]\n"
        for key, value in settings_to_ensure.items():
            content += f"{key}={value}\n"
        with open(ini_path, "w") as f:
            f.write(content)

    logger.info(f"AutoTrading config written to {ini_path}")
    return True
