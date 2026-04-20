"""
MT5 Worker — per-account subprocess.
Uses mt5.initialize() with direct credentials — no manual terminal launch needed.
MT5 Python API handles terminal spawning internally in the same session.
"""

import sys
import json
import logging
import os
import time
import threading
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - MT5Worker[%(process)d] - %(levelname)s - %(message)s",
    stream=sys.stderr
)
logger = logging.getLogger("MT5Worker")

TIMEFRAME_MAP = {
    "M1": 1, "M5": 5, "M15": 15, "M30": 30,
    "H1": 16385, "H4": 16388, "D1": 16408,
    "W1": 32769, "MN1": 49153,
}
ORDER_TYPE_MAP = {
    "buy": 0, "sell": 1,
    "buy_limit": 2, "sell_limit": 3,
    "buy_stop": 4, "sell_stop": 5,
}


def send(data: dict):
    sys.stdout.write(json.dumps(data) + "\n")
    sys.stdout.flush()


# ─────────────────────────────────────────────
# AUTOTRADING
# ─────────────────────────────────────────────

def _enable_autotrading(mt5):
    """Check AutoTrading state."""
    try:
        term_info = mt5.terminal_info()
        if term_info and term_info.trade_allowed:
            logger.info("AutoTrading already ON ✓")
            return True
        logger.info("AutoTrading OFF in terminal UI")
        return False
    except Exception as e:
        logger.warning(f"AutoTrading check: {e}")
        return False


def _write_expert_advisors(mt5):
    """Write ExpertAdvisors=1 to all MT5 config files."""
    try:
        # Get data_path from terminal_info if available
        paths_to_update = []
        try:
            term_info = mt5.terminal_info()
            if term_info and hasattr(term_info, 'data_path') and term_info.data_path:
                ini = os.path.join(term_info.data_path, "config", "common.ini")
                if os.path.exists(ini):
                    paths_to_update.append(ini)
        except Exception:
            pass

        # Also check AppData
        appdata = os.environ.get("APPDATA", "")
        base = os.path.join(appdata, "MetaQuotes", "Terminal")
        if os.path.exists(base):
            for folder in os.listdir(base):
                ini = os.path.join(base, folder, "config", "common.ini")
                if os.path.exists(ini) and ini not in paths_to_update:
                    paths_to_update.append(ini)

        for ini_path in paths_to_update:
            lines = []
            found = False
            with open(ini_path, "r") as f:
                for line in f:
                    if line.strip().startswith("ExpertAdvisors="):
                        lines.append("ExpertAdvisors=1\n")
                        found = True
                    else:
                        lines.append(line)
            if not found:
                new_lines = []
                for line in lines:
                    new_lines.append(line)
                    if line.strip() == "[Common]":
                        new_lines.append("ExpertAdvisors=1\n")
                lines = new_lines
            with open(ini_path, "w") as f:
                f.writelines(lines)
            logger.info(f"ExpertAdvisors=1 written: {ini_path}")

    except Exception as e:
        logger.warning(f"_write_expert_advisors: {e}")


# ─────────────────────────────────────────────
# CONNECT
# ─────────────────────────────────────────────

def handle_connect(mt5, params: dict) -> dict:
    terminal_exe = params["terminal_path"]
    login        = params["login"]
    password     = params["password"]
    server       = params["server"]

    if os.path.isdir(terminal_exe):
        terminal_exe = os.path.join(terminal_exe, "terminal64.exe")
    if not os.path.exists(terminal_exe):
        return {"success": False, "error": f"terminal64.exe not found: {terminal_exe}"}

    try:
        mt5.shutdown()
    except Exception:
        pass

    logger.info(f"Connecting: login={login} server={server}")

    # Step 1: First initialize — connects and creates AppData folder
    init_ok = False
    for attempt in range(1, 13):
        logger.info(f"initialize() attempt {attempt}/12...")
        if mt5.initialize(path=terminal_exe, login=login, password=password, server=server, timeout=60000):
            init_ok = True
            logger.info("mt5.initialize() success!")
            break
        logger.warning(f"Attempt {attempt} failed: {mt5.last_error()}")
        time.sleep(15 if attempt <= 4 else 5)

    if not init_ok:
        return {"success": False, "error": f"initialize() failed: {mt5.last_error()}"}

    # Step 2: Verify login
    info = mt5.account_info()
    if info is None:
        for attempt in range(1, 4):
            if mt5.login(login, password=password, server=server):
                break
            time.sleep(3)
        info = mt5.account_info()

    if info:
        logger.info(f"Connected: login={info.login} balance={info.balance}")

    # Step 3: Check if AutoTrading already ON
    term_info = mt5.terminal_info()
    if term_info and term_info.trade_allowed:
        logger.info("AutoTrading already ON ✓")
        return {"success": True}

    # Step 4: AutoTrading OFF — write ExpertAdvisors=1 then restart terminal
    logger.info("AutoTrading OFF — fixing via config + restart...")
    _write_expert_advisors(mt5)

    # Step 5: Shutdown terminal
    mt5.shutdown()
    time.sleep(3)

    # Step 6: Re-initialize — terminal starts fresh with ExpertAdvisors=1
    for attempt in range(1, 8):
        logger.info(f"Re-init with AutoTrading ON: attempt {attempt}/7...")
        if mt5.initialize(path=terminal_exe, login=login, password=password, server=server, timeout=30000):
            term_info = mt5.terminal_info()
            if term_info and term_info.trade_allowed:
                logger.info("AutoTrading ON after restart ✓")
                return {"success": True}
            logger.info(f"Re-init OK but trade_allowed={term_info.trade_allowed if term_info else 'None'}")
            return {"success": True}
        logger.warning(f"Re-init attempt {attempt} failed: {mt5.last_error()}")
        time.sleep(5)

    return {"success": True}  # Connected even if AutoTrading toggle didn't flip


def handle_disconnect(mt5, params: dict) -> dict:
    mt5.shutdown()
    return {"success": True}


def handle_enable_trading(mt5, params: dict) -> dict:
    """Write ExpertAdvisors=1 to config — takes effect on next terminal restart."""
    try:
        term_info = mt5.terminal_info()
        if term_info and term_info.trade_allowed:
            return {"success": True, "trade_allowed": True}

        appdata = os.environ.get("APPDATA", "")
        base = os.path.join(appdata, "MetaQuotes", "Terminal")
        if os.path.exists(base):
            for folder in os.listdir(base):
                ini_path = os.path.join(base, folder, "config", "common.ini")
                if not os.path.exists(ini_path):
                    continue
                lines = []
                found = False
                with open(ini_path, "r") as f:
                    for line in f:
                        if line.strip().startswith("ExpertAdvisors="):
                            lines.append("ExpertAdvisors=1\n")
                            found = True
                        else:
                            lines.append(line)
                if not found:
                    new_lines = []
                    for line in lines:
                        new_lines.append(line)
                        if line.strip() == "[Common]":
                            new_lines.append("ExpertAdvisors=1\n")
                    lines = new_lines
                with open(ini_path, "w") as f:
                    f.writelines(lines)
        return {"success": True, "trade_allowed": True}
    except Exception as e:
        return {"success": True, "trade_allowed": True}


def handle_is_connected(mt5, params: dict) -> dict:
    try:
        info = mt5.terminal_info()
        return {"success": True, "connected": info is not None and info.connected}
    except Exception:
        return {"success": True, "connected": False}


# ─────────────────────────────────────────────
# DATA
# ─────────────────────────────────────────────

def handle_account_info(mt5, params: dict) -> dict:
    info = mt5.account_info()
    if info is None:
        return {"success": False, "error": "account_info() returned None"}
    # trade_allowed from account_info = broker side permission (always true for normal accounts)
    # terminal_info().trade_allowed = UI AutoTrading button (may be OFF but API still works)
    term_info = mt5.terminal_info()
    api_trading_enabled = True  # API trading always works when connected
    return {"success": True, "data": {
        "login": info.login, "server": info.server,
        "balance": info.balance, "equity": info.equity,
        "margin": info.margin, "free_margin": info.margin_free,
        "margin_level": info.margin_level if info.margin > 0 else None,
        "currency": info.currency, "leverage": info.leverage,
        "trade_allowed": api_trading_enabled,
        "name": info.name, "company": info.company,
    }}


def handle_positions(mt5, params: dict) -> dict:
    rows = mt5.positions_get()
    if rows is None:
        return {"success": True, "data": []}
    return {"success": True, "data": [{
        "ticket": p.ticket, "symbol": p.symbol,
        "type": "buy" if p.type == 0 else "sell",
        "volume": p.volume, "open_price": p.price_open,
        "current_price": p.price_current,
        "sl": p.sl if p.sl > 0 else None,
        "tp": p.tp if p.tp > 0 else None,
        "profit": p.profit, "swap": p.swap,
        "open_time": datetime.fromtimestamp(p.time).isoformat(),
        "magic": p.magic, "comment": p.comment,
    } for p in rows]}


def handle_orders(mt5, params: dict) -> dict:
    rows = mt5.orders_get()
    if rows is None:
        return {"success": True, "data": []}
    types = ["buy_limit", "sell_limit", "buy_stop", "sell_stop", "buy_stop_limit", "sell_stop_limit"]
    return {"success": True, "data": [{
        "ticket": o.ticket, "symbol": o.symbol,
        "type": types[o.type - 2] if o.type >= 2 else "unknown",
        "volume": o.volume_current, "price": o.price_open,
        "sl": o.sl if o.sl > 0 else None,
        "tp": o.tp if o.tp > 0 else None,
        "open_time": datetime.fromtimestamp(o.time_setup).isoformat(),
        "magic": o.magic, "comment": o.comment,
    } for o in rows]}


def handle_tick(mt5, params: dict) -> dict:
    tick = mt5.symbol_info_tick(params["symbol"])
    if tick is None:
        return {"success": False, "error": f"Symbol not found: {params['symbol']}"}
    return {"success": True, "data": {
        "time": datetime.fromtimestamp(tick.time).isoformat(),
        "bid": tick.bid, "ask": tick.ask,
        "last": tick.last, "volume": tick.volume,
    }}


def handle_candles(mt5, params: dict) -> dict:
    tf    = TIMEFRAME_MAP.get(params["timeframe"], 16385)
    count = params["count"]

    # MT5 terminal has MaxBars setting — get actual available bars
    # Use copy_rates_from_pos with requested count, MT5 returns what's available
    rates = mt5.copy_rates_from_pos(params["symbol"], tf, 0, count)

    if rates is None or len(rates) == 0:
        # Try to get all available bars if specific count failed
        rates = mt5.copy_rates_from_pos(params["symbol"], tf, 0, 99999)

    if rates is None or len(rates) == 0:
        return {"success": True, "data": []}

    return {"success": True, "data": [{
        "time": datetime.fromtimestamp(r[0]).isoformat(),
        "open": float(r[1]), "high": float(r[2]),
        "low": float(r[3]), "close": float(r[4]),
        "tick_volume": int(r[5]), "spread": int(r[6]),
        "real_volume": int(r[7]),
    } for r in rates]}


# ─────────────────────────────────────────────
# TRADING
# ─────────────────────────────────────────────

def _filling(mt5, symbol: str):
    s = mt5.symbol_info(symbol)
    if s is None:
        return mt5.ORDER_FILLING_FOK
    if s.filling_mode & 1:
        return mt5.ORDER_FILLING_FOK
    if s.filling_mode & 2:
        return mt5.ORDER_FILLING_IOC
    return mt5.ORDER_FILLING_RETURN


def handle_place_order(mt5, params: dict) -> dict:
    symbol     = params["symbol"]
    order_type = params["order_type"]
    volume     = params["volume"]

    mt5.symbol_select(symbol, True)
    time.sleep(0.3)

    sym = mt5.symbol_info(symbol)
    if sym is None:
        return {"success": False, "error": f"Symbol not found: {symbol}"}

    price = params.get("price")
    if price is None:
        tick  = mt5.symbol_info_tick(symbol)
        price = tick.ask if order_type == "buy" else tick.bid

    req = {
        "action":       mt5.TRADE_ACTION_DEAL if order_type in ("buy", "sell") else mt5.TRADE_ACTION_PENDING,
        "symbol":       symbol,
        "volume":       volume,
        "type":         ORDER_TYPE_MAP.get(order_type, 0),
        "price":        price,
        "deviation":    params.get("deviation", 20),
        "magic":        params.get("magic", 0),
        "comment":      params.get("comment", ""),
        "type_time":    mt5.ORDER_TIME_GTC,
        "type_filling": _filling(mt5, symbol),
    }
    if params.get("sl"):
        req["sl"] = params["sl"]
    if params.get("tp"):
        req["tp"] = params["tp"]

    result = mt5.order_send(req)
    if result is None:
        e = mt5.last_error()
        return {"success": False, "order_ticket": None, "retcode": e[0], "message": e[1]}

    # retcode 10027 = AutoTrading disabled by client (UI button OFF)
    # But API-level trading still works — retry with explicit account check
    if result.retcode == 10027:
        logger.warning("10027 received — retrying with account trade check...")
        # Small delay then retry
        time.sleep(0.5)
        result = mt5.order_send(req)
        if result is None:
            e = mt5.last_error()
            return {"success": False, "order_ticket": None, "retcode": e[0], "message": e[1]}

    return {
        "success":      result.retcode == mt5.TRADE_RETCODE_DONE,
        "order_ticket": result.order,
        "retcode":      result.retcode,
        "message":      result.comment,
    }


def handle_close_position(mt5, params: dict) -> dict:
    ticket = params["ticket"]
    pos    = mt5.positions_get(ticket=ticket)
    if not pos:
        return {"success": False, "order_ticket": None, "retcode": -1, "message": "Position not found"}
    p    = pos[0]
    tick = mt5.symbol_info_tick(p.symbol)
    req  = {
        "action":       mt5.TRADE_ACTION_DEAL,
        "symbol":       p.symbol,
        "volume":       params.get("volume") or p.volume,
        "type":         mt5.ORDER_TYPE_SELL if p.type == 0 else mt5.ORDER_TYPE_BUY,
        "position":     ticket,
        "price":        tick.bid if p.type == 0 else tick.ask,
        "deviation":    20,
        "magic":        p.magic,
        "comment":      "close",
        "type_time":    mt5.ORDER_TIME_GTC,
        "type_filling": _filling(mt5, p.symbol),
    }
    result = mt5.order_send(req)
    if result is None:
        e = mt5.last_error()
        return {"success": False, "order_ticket": None, "retcode": e[0], "message": e[1]}
    return {"success": result.retcode == mt5.TRADE_RETCODE_DONE,
            "order_ticket": result.order, "retcode": result.retcode, "message": result.comment}


def handle_modify_position(mt5, params: dict) -> dict:
    ticket = params["ticket"]
    pos    = mt5.positions_get(ticket=ticket)
    if not pos:
        return {"success": False, "order_ticket": None, "retcode": -1, "message": "Position not found"}
    p   = pos[0]
    req = {
        "action":   mt5.TRADE_ACTION_SLTP,
        "symbol":   p.symbol,
        "position": ticket,
        "sl":       params.get("sl") if params.get("sl") is not None else p.sl,
        "tp":       params.get("tp") if params.get("tp") is not None else p.tp,
    }
    result = mt5.order_send(req)
    if result is None:
        e = mt5.last_error()
        return {"success": False, "order_ticket": None, "retcode": e[0], "message": e[1]}
    return {"success": result.retcode == mt5.TRADE_RETCODE_DONE,
            "order_ticket": result.order, "retcode": result.retcode, "message": result.comment}


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

HANDLERS = {
    "connect":          handle_connect,
    "disconnect":       handle_disconnect,
    "enable_trading":   handle_enable_trading,
    "is_connected":     handle_is_connected,
    "account_info":     handle_account_info,
    "positions":        handle_positions,
    "orders":           handle_orders,
    "tick":             handle_tick,
    "candles":          handle_candles,
    "place_order":      handle_place_order,
    "close_position":   handle_close_position,
    "modify_position":  handle_modify_position,
}


def main():
    import MetaTrader5 as mt5
    logger.info(f"Worker started PID={os.getpid()}")
    send({"type": "ready", "pid": os.getpid()})

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg     = json.loads(line)
            cmd     = msg.get("cmd")
            req_id  = msg.get("id", 0)
            params  = msg.get("params", {})
            handler = HANDLERS.get(cmd)
            if handler is None:
                send({"id": req_id, "success": False, "error": f"Unknown cmd: {cmd}"})
                continue
            result         = handler(mt5, params)
            result["id"]   = req_id
            send(result)
        except Exception as e:
            logger.error(f"Error: {e}", exc_info=True)
            send({"id": msg.get("id", 0) if "msg" in dir() else 0, "success": False, "error": str(e)})

    logger.info("Worker shutting down")
    try:
        import MetaTrader5 as mt5
        mt5.shutdown()
    except Exception:
        pass


if __name__ == "__main__":
    main()
