"""
Gateway Routes — high-level endpoints for SaaS integration.
POST /connect_mt5, /start_trading, /stop_trading, GET /status/{user_id}
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any

from src.security import security_check
from src.terminal_manager import terminal_manager
from src.queue_manager import queue_manager
from src.user_logger import user_logger

router = APIRouter(prefix="/gateway", tags=["Gateway"])


# ── REQUEST MODELS ────────────────────────────────────────────────────────

class ConnectMT5Request(BaseModel):
    user_id: str = Field(..., description="Unique user ID from SaaS app")
    login: int = Field(..., description="MT5 account login number")
    password: str = Field(..., description="MT5 account password")
    server: str = Field(..., description="Broker server (e.g., ICMarkets-Demo)")
    investor_mode: bool = Field(default=False, description="Read-only mode")


class StartTradingRequest(BaseModel):
    user_id: str
    max_positions: Optional[int] = Field(default=20, description="Max open positions")
    max_volume_per_trade: Optional[float] = Field(default=10.0, description="Max lot size per trade")
    max_drawdown_percent: Optional[float] = Field(default=30.0, description="Max drawdown % before blocking trades")


class StopTradingRequest(BaseModel):
    user_id: str
    close_all_positions: bool = Field(default=False, description="Close all open positions before stopping")


# ── ENDPOINTS ─────────────────────────────────────────────────────────────

@router.post("/connect_mt5")
async def connect_mt5(request: ConnectMT5Request, auth: dict = Depends(security_check)):
    """
    Connect a user's MT5 account to the gateway.
    Creates an isolated MT5 instance, logs in, enables AutoTrading.
    """
    try:
        connection = await terminal_manager.create_account(
            account_id=request.user_id,
            login=request.login,
            password=request.password,
            server=request.server,
            investor_mode=request.investor_mode,
        )
        return {
            "success": True,
            "user_id": request.user_id,
            "status": connection.status.value,
            "message": "MT5 instance created and connection initiated",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        user_logger.log_error(request.user_id, "CONNECT_MT5", str(e))
        raise HTTPException(status_code=500, detail=f"Failed to connect: {str(e)}")


@router.post("/start_trading")
async def start_trading(request: StartTradingRequest, auth: dict = Depends(security_check)):
    """
    Activate the trading engine for a connected user.
    Optionally configure risk parameters.
    """
    engine = terminal_manager.get_engine(request.user_id)
    if not engine:
        # Check if account exists but engine not yet created
        bridge = terminal_manager.get_bridge(request.user_id)
        if not bridge:
            raise HTTPException(status_code=404, detail="User not connected. Call /connect_mt5 first.")

        # Create engine on the fly
        from src.trading_engine import TradingEngine
        engine = TradingEngine(request.user_id, bridge)
        terminal_manager._engines[request.user_id] = engine

    # Apply risk parameters
    if request.max_positions is not None:
        engine.max_positions = request.max_positions
    if request.max_volume_per_trade is not None:
        engine.max_volume_per_trade = request.max_volume_per_trade
    if request.max_drawdown_percent is not None:
        engine.max_drawdown_percent = request.max_drawdown_percent

    try:
        await engine.start()
        user_logger.log_event(request.user_id, "TRADING_STARTED", f"max_pos={engine.max_positions}")
        return {
            "success": True,
            "user_id": request.user_id,
            "trading_active": True,
            "risk_params": {
                "max_positions": engine.max_positions,
                "max_volume_per_trade": engine.max_volume_per_trade,
                "max_drawdown_percent": engine.max_drawdown_percent,
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start trading: {str(e)}")


@router.post("/stop_trading")
async def stop_trading(request: StopTradingRequest, auth: dict = Depends(security_check)):
    """
    Stop the trading engine for a user.
    Optionally close all open positions.
    """
    engine = terminal_manager.get_engine(request.user_id)
    if not engine:
        raise HTTPException(status_code=404, detail="No active trading engine for this user")

    close_results = None
    if request.close_all_positions:
        try:
            close_results = await engine.close_all_positions()
        except Exception as e:
            user_logger.log_error(request.user_id, "CLOSE_ALL", str(e))

    await engine.stop()
    user_logger.log_event(request.user_id, "TRADING_STOPPED")

    return {
        "success": True,
        "user_id": request.user_id,
        "trading_active": False,
        "positions_closed": close_results,
    }


@router.get("/status/{user_id}")
async def get_status(user_id: str, auth: dict = Depends(security_check)):
    """
    Get full status for a user: connection, trading engine, account info.
    """
    connection = terminal_manager.get_connection(user_id)
    if not connection:
        raise HTTPException(status_code=404, detail="User not found")

    result: Dict[str, Any] = {
        "user_id": user_id,
        "connection": {
            "status": connection.status.value,
            "login": connection.login,
            "server": connection.server,
            "connected_at": connection.connected_at.isoformat() if connection.connected_at else None,
            "last_error": connection.last_error,
            "restart_count": connection.restart_count,
        },
    }

    # Trading engine status
    engine = terminal_manager.get_engine(user_id)
    if engine:
        result["trading_engine"] = engine.get_status()
    else:
        result["trading_engine"] = {"is_active": False}

    # Account info (if connected)
    bridge = terminal_manager.get_bridge(user_id)
    if bridge and bridge.is_connected():
        try:
            info = await bridge.get_account_info()
            positions = await bridge.get_positions()
            result["account"] = {
                "balance": info.get("balance"),
                "equity": info.get("equity"),
                "margin": info.get("margin"),
                "free_margin": info.get("free_margin"),
                "currency": info.get("currency"),
                "leverage": info.get("leverage"),
                "trade_allowed": info.get("trade_allowed"),
                "open_positions": len(positions),
            }
        except Exception:
            result["account"] = None

    return result


@router.post("/disconnect/{user_id}")
async def disconnect_user(user_id: str, auth: dict = Depends(security_check)):
    """Disconnect and stop everything for a user."""
    try:
        await terminal_manager.stop_account(user_id)
        user_logger.log_event(user_id, "DISCONNECTED")
        return {"success": True, "user_id": user_id, "message": "Disconnected"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── DIRECT TRADING SHORTCUTS ──────────────────────────────────────────────

class QuickTradeRequest(BaseModel):
    user_id: str
    symbol: str
    volume: float
    sl: Optional[float] = None
    tp: Optional[float] = None
    comment: str = ""


@router.post("/buy")
async def quick_buy(request: QuickTradeRequest, auth: dict = Depends(security_check)):
    """Quick buy endpoint — /buy with user_id, symbol, volume."""
    engine = terminal_manager.get_engine(request.user_id)
    if not engine or not engine.is_active:
        raise HTTPException(status_code=400, detail="Trading engine not active. Call /start_trading first.")

    try:
        result = await engine.buy(
            symbol=request.symbol,
            volume=request.volume,
            sl=request.sl,
            tp=request.tp,
            comment=request.comment,
        )
        user_logger.log_trade(
            request.user_id, "BUY", request.symbol, request.volume,
            ticket=result.get("order_ticket"), success=result.get("success"),
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sell")
async def quick_sell(request: QuickTradeRequest, auth: dict = Depends(security_check)):
    """Quick sell endpoint — /sell with user_id, symbol, volume."""
    engine = terminal_manager.get_engine(request.user_id)
    if not engine or not engine.is_active:
        raise HTTPException(status_code=400, detail="Trading engine not active. Call /start_trading first.")

    try:
        result = await engine.sell(
            symbol=request.symbol,
            volume=request.volume,
            sl=request.sl,
            tp=request.tp,
            comment=request.comment,
        )
        user_logger.log_trade(
            request.user_id, "SELL", request.symbol, request.volume,
            ticket=result.get("order_ticket"), success=result.get("success"),
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/positions/{user_id}")
async def get_positions(user_id: str, auth: dict = Depends(security_check)):
    """Get open positions for a user."""
    engine = terminal_manager.get_engine(user_id)
    if not engine or not engine.is_active:
        # Fall back to bridge directly
        bridge = terminal_manager.get_bridge(user_id)
        if not bridge:
            raise HTTPException(status_code=404, detail="User not connected")
        positions = await bridge.get_positions()
    else:
        positions = await engine.get_positions()

    return {
        "user_id": user_id,
        "positions": [p.model_dump() for p in positions],
    }


@router.get("/balance/{user_id}")
async def get_balance(user_id: str, auth: dict = Depends(security_check)):
    """Get account balance/equity for a user."""
    bridge = terminal_manager.get_bridge(user_id)
    if not bridge:
        raise HTTPException(status_code=404, detail="User not connected")

    try:
        info = await bridge.get_account_info()
        return {
            "user_id": user_id,
            "balance": info.get("balance"),
            "equity": info.get("equity"),
            "margin": info.get("margin"),
            "free_margin": info.get("free_margin"),
            "currency": info.get("currency"),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
