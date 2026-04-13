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
    try:
        info = mt5.terminal_info()
        if info and info.trade_allowed:
            logger.info("AutoTrading already ON")
            return
        # Ctrl+E via win32
        import win32api, win32con
        win32api.keybd_event(0x11, 0, 0, 0)
        win32api.keybd_event(0x45, 0, 0, 0)
        time.sleep(0.1)
        win32api.keybd_event(0x45, 0, win32con.KEYEVENTF_KEYUP, 0)
        win32api.keybd_event(0x11, 0, win32con.KEYEVENTF_KEYUP, 0)
        time.sleep(0.5)
        logger.info("AutoTrading Ctrl+E sent")
    except Exception as e:
        logger.warning(f"AutoTrading enable: {e}")


# ─────────────────────────────────────────────
# CONNECT
# ─────────────────────────────────────────────

def handle_connect(mt5, params: dict) -> dict:
    terminal_exe = params["terminal_path"]
    login        = params["login"]
    password     = params["password"]
    server       = params["server"]

    # Resolve exe path
    if os.path.isdir(terminal_exe):
        terminal_exe = os.path.join(terminal_exe, "terminal64.exe")
    if not os.path.exists(terminal_exe):
        return {"success": False, "error": f"terminal64.exe not found: {terminal_exe}"}

    # Clean any previous state
    try:
        mt5.shutdown()
    except Exception:
        pass

    logger.info(f"Connecting: login={login} server={server} path={terminal_exe}")

    # ── KEY INSIGHT ──────────────────────────────────────────────────────────
    # Pass login/password/server directly to mt5.initialize().
    # MT5 Python API will:
    #   1. Launch terminal64.exe internally (same process session — no IPC issue)
    #   2. Auto-login with the provided credentials
    #   3. Handle server discovery automatically for ANY broker
    # No need to manually launch terminal, write ini files, or handle popups.
    # ─────────────────────────────────────────────────────────────────────────

    for attempt in range(1, 13):
        logger.info(f"initialize() attempt {attempt}/12 ...")
        ok = mt5.initialize(
            path=terminal_exe,
            login=login,
            password=password,
            server=server,
            timeout=60000,   # 60s per attempt — enough for server discovery
        )
        if ok:
            logger.info("mt5.initialize() success!")
            break
        err = mt5.last_error()
        logger.warning(f"Attempt {attempt} failed: {err}")
        # First launch: terminal needs time to compile MQL5 scripts (~2-3 min)
        # Give more wait time on early attempts
        wait = 15 if attempt <= 4 else 5
        time.sleep(wait)
    else:
        return {"success": False, "error": f"initialize() failed: {mt5.last_error()}"}

    # Verify account
    info = mt5.account_info()
    if info is None:
        # Try explicit login (some brokers need this after initialize)
        logger.info("account_info None — trying explicit mt5.login()...")
        for attempt in range(1, 4):
            if mt5.login(login, password=password, server=server):
                logger.info("Explicit login OK")
                break
            logger.warning(f"Login attempt {attempt}: {mt5.last_error()}")
            time.sleep(3)
        info = mt5.account_info()

    if info:
        logger.info(f"Connected: login={info.login} server={info.server} balance={info.balance}")
    else:
        logger.warning("Connected but account_info still None — proceeding anyway")

    # Enable AutoTrading
    _enable_autotrading(mt5)

    return {"success": True}


def handle_disconnect(mt5, params: dict) -> dict:
    mt5.shutdown()
    return {"success": True}


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
    return {"success": True, "data": {
        "login": info.login, "server": info.server,
        "balance": info.balance, "equity": info.equity,
        "margin": info.margin, "free_margin": info.margin_free,
        "margin_level": info.margin_level if info.margin > 0 else None,
        "currency": info.currency, "leverage": info.leverage,
        "trade_allowed": info.trade_allowed,
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
    tf = TIMEFRAME_MAP.get(params["timeframe"], 16385)
    rates = mt5.copy_rates_from_pos(params["symbol"], tf, 0, params["count"])
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
