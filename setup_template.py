"""
One-time Golden Template Setup Script.

This script:
1. Launches MT5 template terminal in portable mode
2. Logs in with a demo account to generate config files
3. Saves the credentials so future copies won't show login popup
4. Shuts down the terminal

Run this ONCE after creating the template folder.
After this, all cloned instances will start without popups.
"""

import subprocess
import time
import sys
import os

# Use the demo account to seed the template
LOGIN = 5049085762
PASSWORD = "*l8xHbPn"
SERVER = "MetaQuotes-Demo"
TEMPLATE_PATH = r"C:\MT5_TEMPLATE"
TERMINAL_EXE = os.path.join(TEMPLATE_PATH, "terminal64.exe")


def main():
    print("=" * 50)
    print("MT5 Golden Template Setup")
    print("=" * 50)

    if not os.path.exists(TERMINAL_EXE):
        print(f"ERROR: terminal64.exe not found at {TEMPLATE_PATH}")
        sys.exit(1)

    # Step 1: Launch terminal in portable mode
    print(f"\n[1] Launching MT5 terminal: {TERMINAL_EXE} /portable")
    proc = subprocess.Popen(
        [TERMINAL_EXE, "/portable"],
        creationflags=0x00000008,  # DETACHED_PROCESS
    )
    print(f"    Terminal PID: {proc.pid}")
    print("    Waiting 15 seconds for terminal to start...")
    time.sleep(15)

    # Step 2: Connect via Python API and login
    print("\n[2] Connecting Python API...")
    import MetaTrader5 as mt5

    if not mt5.initialize(path=TERMINAL_EXE):
        error = mt5.last_error()
        print(f"    ERROR: MT5 init failed: {error}")
        print("    >>> A login popup may have appeared.")
        print("    >>> Please login manually in the MT5 window,")
        print("    >>> check 'Save Password', then run this script again.")
        proc.terminate()
        sys.exit(1)

    print("    MT5 API connected!")

    # Step 3: Login
    print(f"\n[3] Logging in: login={LOGIN}, server={SERVER}")
    if not mt5.login(LOGIN, password=PASSWORD, server=SERVER):
        error = mt5.last_error()
        print(f"    ERROR: Login failed: {error}")
        mt5.shutdown()
        proc.terminate()
        sys.exit(1)

    # Step 4: Verify
    info = mt5.account_info()
    if info:
        print(f"    Login successful!")
        print(f"    Account: {info.login}")
        print(f"    Server: {info.server}")
        print(f"    Balance: {info.balance} {info.currency}")
    else:
        print("    WARNING: Could not get account info")

    # Step 5: Shutdown cleanly — this saves the config
    print("\n[4] Shutting down MT5 (saving config)...")
    mt5.shutdown()
    time.sleep(3)

    # Kill the terminal process
    try:
        proc.terminate()
        proc.wait(timeout=10)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass

    time.sleep(2)

    # Step 6: Verify config files were created
    print("\n[5] Verifying template config files...")
    config_dir = os.path.join(TEMPLATE_PATH, "config")
    if not os.path.exists(config_dir):
        # Check Config (capital C) too
        config_dir = os.path.join(TEMPLATE_PATH, "Config")

    required_files = ["terminal.ini", "servers.dat"]
    all_good = True
    for f in required_files:
        path = os.path.join(config_dir, f)
        if os.path.exists(path):
            size = os.path.getsize(path)
            print(f"    OK: {f} ({size} bytes)")
        else:
            print(f"    MISSING: {f}")
            all_good = False

    # Check for accounts.dat (saved credentials)
    accounts_dat = os.path.join(config_dir, "accounts.dat")
    if os.path.exists(accounts_dat):
        print(f"    OK: accounts.dat ({os.path.getsize(accounts_dat)} bytes) — credentials saved!")
    else:
        print("    WARNING: accounts.dat not found — credentials may not be saved")

    if all_good:
        print("\n" + "=" * 50)
        print("TEMPLATE SETUP COMPLETE!")
        print("Golden template is ready at:", TEMPLATE_PATH)
        print("All future cloned instances will start WITHOUT popups.")
        print("=" * 50)
    else:
        print("\n WARNING: Some config files missing.")
        print("You may need to login manually once in the template terminal.")


if __name__ == "__main__":
    main()
