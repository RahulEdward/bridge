"""
Windows-specific MT5 Bridge implementation.

This module provides the actual MetaTrader5 integration for Windows VPS deployment.
It uses the official MetaTrader5 Python package which only works on Windows.

On Windows VPS, replace the import in terminal_manager.py:
    from src.mt5_bridge_windows import MT5Bridge
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional, Dict, List, Any
from concurrent.futures import ThreadPoolExecutor

from src.models import (
    AccountStatus, Position, Order, CandleData, TickData,
    OrderType, TimeFrame
)

logger = logging.getLogger(__name__)

TIMEFRAME_MAP = {
    TimeFrame.M1: 1,
    TimeFrame.M5: 5,
    TimeFrame.M15: 15,
    TimeFrame.M30: 30,
    TimeFrame.H1: 16385,
    TimeFrame.H4: 16388,
    TimeFrame.D1: 16408,
    TimeFrame.W1: 32769,
    TimeFrame.MN1: 49153,
}

ORDER_TYPE_MAP = {
    OrderType.BUY: 0,
    OrderType.SELL: 1,
    OrderType.BUY_LIMIT: 2,
    OrderType.SELL_LIMIT: 3,
    OrderType.BUY_STOP: 4,
    OrderType.SELL_STOP: 5,
}


class MT5Bridge:
    """
    Production MT5 Bridge for Windows VPS.
    
    Uses the official MetaTrader5 Python package for direct terminal communication.
    Each instance manages a single MT5 terminal connection.
    """
    
    def __init__(self, account_id: str, terminal_path: str):
        self.account_id = account_id
        self.terminal_path = terminal_path
        self._connected = False
        self._executor = ThreadPoolExecutor(max_workers=2)
        self._mt5 = None
        
    def _run_sync(self, func, *args):
        """Run synchronous MT5 function in thread pool."""
        loop = asyncio.get_event_loop()
        return loop.run_in_executor(self._executor, func, *args)
    
    async def connect(self, login: int, password: str, server: str, investor_mode: bool = False) -> bool:
        """
        Connect to MT5 terminal with specified account.
        
        On Windows, this initializes the MT5 terminal and logs in with credentials.
        """
        try:
            import MetaTrader5 as mt5
            self._mt5 = mt5
            
            logger.info(f"Initializing MT5 terminal at: {self.terminal_path}")
            
            init_result = await self._run_sync(
                mt5.initialize,
                self.terminal_path
            )
            
            if not init_result:
                error = mt5.last_error()
                raise ConnectionError(f"MT5 initialization failed: {error}")
            
            logger.info(f"Logging into MT5: login={login}, server={server}")
            
            login_result = await self._run_sync(
                mt5.login,
                login,
                password=password,
                server=server
            )
            
            if not login_result:
                error = mt5.last_error()
                raise ConnectionError(f"MT5 login failed: {error}")
            
            self._connected = True
            logger.info(f"MT5 connection established for account {self.account_id}")
            return True
            
        except ImportError:
            logger.error("MetaTrader5 package not available - this bridge requires Windows")
            raise RuntimeError("MetaTrader5 package requires Windows OS")
        except Exception as e:
            logger.error(f"MT5 connection failed for account {self.account_id}: {e}")
            self._connected = False
            raise
    
    async def disconnect(self) -> bool:
        """Disconnect from MT5 terminal."""
        try:
            if self._mt5 and self._connected:
                await self._run_sync(self._mt5.shutdown)
            self._connected = False
            logger.info(f"MT5 disconnected for account {self.account_id}")
            return True
        except Exception as e:
            logger.error(f"MT5 disconnect failed for account {self.account_id}: {e}")
            return False
    
    def is_connected(self) -> bool:
        """Check if connected to MT5."""
        if not self._connected or not self._mt5:
            return False
        try:
            info = self._mt5.terminal_info()
            return info is not None and info.connected
        except:
            return False
    
    async def get_account_info(self) -> Dict[str, Any]:
        """Get account information from MT5."""
        if not self._connected:
            raise ConnectionError("MT5 not connected")
        
        info = await self._run_sync(self._mt5.account_info)
        if info is None:
            raise ConnectionError("Failed to get account info")
        
        return {
            "login": info.login,
            "server": info.server,
            "balance": info.balance,
            "equity": info.equity,
            "margin": info.margin,
            "free_margin": info.margin_free,
            "margin_level": info.margin_level if info.margin > 0 else None,
            "currency": info.currency,
            "leverage": info.leverage,
            "trade_allowed": info.trade_allowed,
            "name": info.name,
            "company": info.company
        }
    
    async def get_positions(self) -> List[Position]:
        """Get all open positions."""
        if not self._connected:
            raise ConnectionError("MT5 not connected")
        
        positions = await self._run_sync(self._mt5.positions_get)
        if positions is None:
            return []
        
        result = []
        for p in positions:
            result.append(Position(
                ticket=p.ticket,
                symbol=p.symbol,
                type="buy" if p.type == 0 else "sell",
                volume=p.volume,
                open_price=p.price_open,
                current_price=p.price_current,
                sl=p.sl if p.sl > 0 else None,
                tp=p.tp if p.tp > 0 else None,
                profit=p.profit,
                swap=p.swap,
                open_time=datetime.fromtimestamp(p.time),
                magic=p.magic,
                comment=p.comment
            ))
        
        return result
    
    async def get_orders(self) -> List[Order]:
        """Get all pending orders."""
        if not self._connected:
            raise ConnectionError("MT5 not connected")
        
        orders = await self._run_sync(self._mt5.orders_get)
        if orders is None:
            return []
        
        result = []
        order_types = ["buy_limit", "sell_limit", "buy_stop", "sell_stop", 
                       "buy_stop_limit", "sell_stop_limit"]
        
        for o in orders:
            result.append(Order(
                ticket=o.ticket,
                symbol=o.symbol,
                type=order_types[o.type - 2] if o.type >= 2 else "unknown",
                volume=o.volume_current,
                price=o.price_open,
                sl=o.sl if o.sl > 0 else None,
                tp=o.tp if o.tp > 0 else None,
                open_time=datetime.fromtimestamp(o.time_setup),
                magic=o.magic,
                comment=o.comment
            ))
        
        return result
    
    async def get_candles(self, symbol: str, timeframe: TimeFrame, count: int) -> List[CandleData]:
        """Get historical candle data."""
        if not self._connected:
            raise ConnectionError("MT5 not connected")
        
        mt5_tf = TIMEFRAME_MAP.get(timeframe, 16385)
        
        rates = await self._run_sync(
            self._mt5.copy_rates_from_pos,
            symbol,
            mt5_tf,
            0,
            count
        )
        
        if rates is None or len(rates) == 0:
            return []
        
        candles = []
        for r in rates:
            candles.append(CandleData(
                time=datetime.fromtimestamp(r[0]),
                open=r[1],
                high=r[2],
                low=r[3],
                close=r[4],
                tick_volume=r[5],
                spread=r[6],
                real_volume=r[7]
            ))
        
        return candles
    
    async def get_tick(self, symbol: str) -> TickData:
        """Get current tick data for symbol."""
        if not self._connected:
            raise ConnectionError("MT5 not connected")
        
        tick = await self._run_sync(self._mt5.symbol_info_tick, symbol)
        if tick is None:
            raise ValueError(f"Symbol not found: {symbol}")
        
        return TickData(
            time=datetime.fromtimestamp(tick.time),
            bid=tick.bid,
            ask=tick.ask,
            last=tick.last,
            volume=tick.volume
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
        comment: str = ""
    ) -> Dict[str, Any]:
        """Place a new order."""
        if not self._connected:
            raise ConnectionError("MT5 not connected")
        
        symbol_info = await self._run_sync(self._mt5.symbol_info, symbol)
        if symbol_info is None:
            raise ValueError(f"Symbol not found: {symbol}")
        
        if not symbol_info.visible:
            await self._run_sync(self._mt5.symbol_select, symbol, True)
        
        mt5_type = ORDER_TYPE_MAP.get(order_type, 0)
        
        if price is None:
            tick = await self._run_sync(self._mt5.symbol_info_tick, symbol)
            if order_type in [OrderType.BUY]:
                price = tick.ask
            else:
                price = tick.bid
        
        request = {
            "action": self._mt5.TRADE_ACTION_DEAL if order_type in [OrderType.BUY, OrderType.SELL] else self._mt5.TRADE_ACTION_PENDING,
            "symbol": symbol,
            "volume": volume,
            "type": mt5_type,
            "price": price,
            "deviation": deviation,
            "magic": magic,
            "comment": comment,
            "type_time": self._mt5.ORDER_TIME_GTC,
            "type_filling": self._mt5.ORDER_FILLING_IOC,
        }
        
        if sl:
            request["sl"] = sl
        if tp:
            request["tp"] = tp
        
        logger.info(f"Placing order: {request}")
        
        result = await self._run_sync(self._mt5.order_send, request)
        
        if result is None:
            error = self._mt5.last_error()
            return {
                "success": False,
                "order_ticket": None,
                "retcode": error[0],
                "message": error[1]
            }
        
        return {
            "success": result.retcode == self._mt5.TRADE_RETCODE_DONE,
            "order_ticket": result.order,
            "retcode": result.retcode,
            "message": result.comment
        }
    
    async def close_position(self, ticket: int, volume: Optional[float] = None) -> Dict[str, Any]:
        """Close an open position."""
        if not self._connected:
            raise ConnectionError("MT5 not connected")
        
        position = await self._run_sync(self._mt5.positions_get, ticket=ticket)
        if not position:
            return {
                "success": False,
                "order_ticket": None,
                "retcode": -1,
                "message": "Position not found"
            }
        
        position = position[0]
        
        close_type = self._mt5.ORDER_TYPE_SELL if position.type == 0 else self._mt5.ORDER_TYPE_BUY
        
        tick = await self._run_sync(self._mt5.symbol_info_tick, position.symbol)
        price = tick.bid if position.type == 0 else tick.ask
        
        close_volume = volume if volume else position.volume
        
        request = {
            "action": self._mt5.TRADE_ACTION_DEAL,
            "symbol": position.symbol,
            "volume": close_volume,
            "type": close_type,
            "position": ticket,
            "price": price,
            "deviation": 20,
            "magic": position.magic,
            "comment": "Close via gateway",
            "type_time": self._mt5.ORDER_TIME_GTC,
            "type_filling": self._mt5.ORDER_FILLING_IOC,
        }
        
        logger.info(f"Closing position: {request}")
        
        result = await self._run_sync(self._mt5.order_send, request)
        
        if result is None:
            error = self._mt5.last_error()
            return {
                "success": False,
                "order_ticket": None,
                "retcode": error[0],
                "message": error[1]
            }
        
        return {
            "success": result.retcode == self._mt5.TRADE_RETCODE_DONE,
            "order_ticket": result.order,
            "retcode": result.retcode,
            "message": result.comment
        }
    
    async def modify_position(
        self,
        ticket: int,
        sl: Optional[float] = None,
        tp: Optional[float] = None
    ) -> Dict[str, Any]:
        """Modify position SL/TP."""
        if not self._connected:
            raise ConnectionError("MT5 not connected")
        
        position = await self._run_sync(self._mt5.positions_get, ticket=ticket)
        if not position:
            return {
                "success": False,
                "order_ticket": None,
                "retcode": -1,
                "message": "Position not found"
            }
        
        position = position[0]
        
        request = {
            "action": self._mt5.TRADE_ACTION_SLTP,
            "symbol": position.symbol,
            "position": ticket,
            "sl": sl if sl is not None else position.sl,
            "tp": tp if tp is not None else position.tp,
        }
        
        logger.info(f"Modifying position: {request}")
        
        result = await self._run_sync(self._mt5.order_send, request)
        
        if result is None:
            error = self._mt5.last_error()
            return {
                "success": False,
                "order_ticket": None,
                "retcode": error[0],
                "message": error[1]
            }
        
        return {
            "success": result.retcode == self._mt5.TRADE_RETCODE_DONE,
            "order_ticket": result.order,
            "retcode": result.retcode,
            "message": result.comment
        }
    
    async def modify_order(
        self,
        ticket: int,
        price: Optional[float] = None,
        sl: Optional[float] = None,
        tp: Optional[float] = None
    ) -> Dict[str, Any]:
        """Modify pending order."""
        if not self._connected:
            raise ConnectionError("MT5 not connected")
        
        orders = await self._run_sync(self._mt5.orders_get, ticket=ticket)
        if not orders:
            return {
                "success": False,
                "order_ticket": None,
                "retcode": -1,
                "message": "Order not found"
            }
        
        order = orders[0]
        
        request = {
            "action": self._mt5.TRADE_ACTION_MODIFY,
            "order": ticket,
            "price": price if price is not None else order.price_open,
            "sl": sl if sl is not None else order.sl,
            "tp": tp if tp is not None else order.tp,
        }
        
        logger.info(f"Modifying order: {request}")
        
        result = await self._run_sync(self._mt5.order_send, request)
        
        if result is None:
            error = self._mt5.last_error()
            return {
                "success": False,
                "order_ticket": None,
                "retcode": error[0],
                "message": error[1]
            }
        
        return {
            "success": result.retcode == self._mt5.TRADE_RETCODE_DONE,
            "order_ticket": result.order,
            "retcode": result.retcode,
            "message": result.comment
        }
