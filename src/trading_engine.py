"""
Trading Engine — per-user trading bot that connects to an MT5 bridge instance.
Provides: market data fetching, order execution, position management, and risk controls.
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List

from src.models import OrderType, TimeFrame, Position, Order, CandleData, TickData

logger = logging.getLogger(__name__)


class TradingEngine:
    """
    Per-user trading engine. Wraps an MT5 bridge with:
    - Order execution with validation
    - Position management (close, modify, close-all)
    - Risk controls (max positions, max volume, drawdown limit)
    - Market data access
    """

    def __init__(self, account_id: str, bridge):
        self.account_id = account_id
        self._bridge = bridge
        self.is_active = False

        # Risk parameters (configurable per user)
        self.max_positions = 20
        self.max_volume_per_trade = 10.0
        self.max_total_volume = 50.0
        self.max_drawdown_percent = 30.0

        # Stats
        self.trades_executed = 0
        self.started_at: Optional[datetime] = None

    async def start(self):
        """Activate the trading engine."""
        if not self._bridge or not self._bridge.is_connected():
            raise ConnectionError(f"Bridge not connected for {self.account_id}")
        self.is_active = True
        self.started_at = datetime.now()
        logger.info(f"[{self.account_id}] Trading engine started")

    async def stop(self):
        """Deactivate the trading engine."""
        self.is_active = False
        logger.info(f"[{self.account_id}] Trading engine stopped")

    # ── MARKET DATA ───────────────────────────────────────────────────────

    async def get_tick(self, symbol: str) -> TickData:
        self._check_active()
        return await self._bridge.get_tick(symbol)

    async def get_candles(
        self, symbol: str, timeframe: TimeFrame, count: int = 100
    ) -> List[CandleData]:
        self._check_active()
        return await self._bridge.get_candles(symbol, timeframe, count)

    async def get_account_info(self) -> Dict[str, Any]:
        self._check_active()
        return await self._bridge.get_account_info()

    # ── ORDER EXECUTION ───────────────────────────────────────────────────

    async def buy(
        self,
        symbol: str,
        volume: float,
        sl: Optional[float] = None,
        tp: Optional[float] = None,
        comment: str = "",
    ) -> Dict[str, Any]:
        return await self.place_order(
            symbol=symbol,
            order_type=OrderType.BUY,
            volume=volume,
            sl=sl,
            tp=tp,
            comment=comment,
        )

    async def sell(
        self,
        symbol: str,
        volume: float,
        sl: Optional[float] = None,
        tp: Optional[float] = None,
        comment: str = "",
    ) -> Dict[str, Any]:
        return await self.place_order(
            symbol=symbol,
            order_type=OrderType.SELL,
            volume=volume,
            sl=sl,
            tp=tp,
            comment=comment,
        )

    async def place_order(
        self,
        symbol: str,
        order_type: OrderType,
        volume: float,
        price: Optional[float] = None,
        sl: Optional[float] = None,
        tp: Optional[float] = None,
        deviation: int = 20,
        magic: int = 0,
        comment: str = "",
    ) -> Dict[str, Any]:
        """Place an order with risk validation."""
        self._check_active()

        # Risk checks
        await self._validate_risk(volume)

        result = await self._bridge.place_order(
            symbol=symbol,
            order_type=order_type,
            volume=volume,
            price=price,
            sl=sl,
            tp=tp,
            deviation=deviation,
            magic=magic,
            comment=comment,
        )

        if result.get("success"):
            self.trades_executed += 1
            logger.info(
                f"[{self.account_id}] Order placed: {order_type.value} {volume} {symbol} "
                f"ticket={result.get('order_ticket')}"
            )
        else:
            logger.warning(
                f"[{self.account_id}] Order failed: {result.get('message')} "
                f"retcode={result.get('retcode')}"
            )

        return result

    # ── POSITION MANAGEMENT ───────────────────────────────────────────────

    async def get_positions(self) -> List[Position]:
        self._check_active()
        return await self._bridge.get_positions()

    async def get_orders(self) -> List[Order]:
        self._check_active()
        return await self._bridge.get_orders()

    async def close_position(
        self, ticket: int, volume: Optional[float] = None
    ) -> Dict[str, Any]:
        self._check_active()
        result = await self._bridge.close_position(ticket, volume)
        if result.get("success"):
            logger.info(f"[{self.account_id}] Position closed: ticket={ticket}")
        return result

    async def modify_position(
        self, ticket: int, sl: Optional[float] = None, tp: Optional[float] = None
    ) -> Dict[str, Any]:
        self._check_active()
        result = await self._bridge.modify_position(ticket, sl, tp)
        if result.get("success"):
            logger.info(f"[{self.account_id}] Position modified: ticket={ticket} sl={sl} tp={tp}")
        return result

    async def close_all_positions(self) -> Dict[str, Any]:
        """Close all open positions for this account."""
        self._check_active()
        positions = await self._bridge.get_positions()
        results = []
        for pos in positions:
            try:
                r = await self._bridge.close_position(pos.ticket)
                results.append({"ticket": pos.ticket, **r})
            except Exception as e:
                results.append({"ticket": pos.ticket, "success": False, "message": str(e)})

        closed = sum(1 for r in results if r.get("success"))
        logger.info(f"[{self.account_id}] Close all: {closed}/{len(positions)} closed")
        return {"total": len(positions), "closed": closed, "results": results}

    # ── RISK MANAGEMENT ───────────────────────────────────────────────────

    async def _validate_risk(self, volume: float):
        """Pre-trade risk checks."""
        # Volume limit
        if volume > self.max_volume_per_trade:
            raise ValueError(
                f"Volume {volume} exceeds max per trade ({self.max_volume_per_trade})"
            )

        # Position count limit
        positions = await self._bridge.get_positions()
        if len(positions) >= self.max_positions:
            raise ValueError(
                f"Max positions reached ({self.max_positions})"
            )

        # Total volume limit
        total_volume = sum(p.volume for p in positions) + volume
        if total_volume > self.max_total_volume:
            raise ValueError(
                f"Total volume {total_volume} would exceed limit ({self.max_total_volume})"
            )

        # Drawdown check
        try:
            info = await self._bridge.get_account_info()
            balance = info.get("balance", 0)
            equity = info.get("equity", 0)
            if balance > 0:
                drawdown = ((balance - equity) / balance) * 100
                if drawdown > self.max_drawdown_percent:
                    raise ValueError(
                        f"Drawdown {drawdown:.1f}% exceeds limit ({self.max_drawdown_percent}%)"
                    )
        except (ConnectionError, KeyError):
            pass  # Don't block trades if account info temporarily unavailable

    def _check_active(self):
        if not self.is_active:
            raise RuntimeError(f"Trading engine not active for {self.account_id}")
        if not self._bridge or not self._bridge.is_connected():
            raise ConnectionError(f"Bridge not connected for {self.account_id}")

    # ── STATUS ────────────────────────────────────────────────────────────

    def get_status(self) -> Dict[str, Any]:
        return {
            "account_id": self.account_id,
            "is_active": self.is_active,
            "trades_executed": self.trades_executed,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "max_positions": self.max_positions,
            "max_volume_per_trade": self.max_volume_per_trade,
        }
