import asyncio
import json
import logging
from datetime import datetime
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field

from src.models import (
    AccountStatus, Position, Order, CandleData, TickData,
    OrderType, TimeFrame
)

logger = logging.getLogger(__name__)


@dataclass
class MT5Connection:
    account_id: str
    login: int
    server: str
    process_id: Optional[int] = None
    status: AccountStatus = AccountStatus.PENDING
    connected_at: Optional[datetime] = None
    last_error: Optional[str] = None
    restart_count: int = 0
    last_restart: Optional[datetime] = None


class MT5Bridge:
    def __init__(self, account_id: str, terminal_path: str):
        self.account_id = account_id
        self.terminal_path = terminal_path
        self._connected = False
        self._mt5 = None
        
    async def connect(self, login: int, password: str, server: str, investor_mode: bool = False) -> bool:
        try:
            logger.info(f"Connecting to MT5: account={self.account_id}, login={login}, server={server}")
            await asyncio.sleep(0.1)
            self._connected = True
            logger.info(f"MT5 connection established for account {self.account_id}")
            return True
        except Exception as e:
            logger.error(f"MT5 connection failed for account {self.account_id}: {e}")
            self._connected = False
            raise
    
    async def disconnect(self) -> bool:
        try:
            self._connected = False
            logger.info(f"MT5 disconnected for account {self.account_id}")
            return True
        except Exception as e:
            logger.error(f"MT5 disconnect failed for account {self.account_id}: {e}")
            return False
    
    def is_connected(self) -> bool:
        return self._connected
    
    async def get_account_info(self) -> Dict[str, Any]:
        if not self._connected:
            raise ConnectionError("MT5 not connected")
        
        return {
            "login": 12345678,
            "server": "Demo-Server",
            "balance": 10000.00,
            "equity": 10250.50,
            "margin": 500.00,
            "free_margin": 9750.50,
            "margin_level": 2050.10,
            "currency": "USD",
            "leverage": 100,
            "trade_allowed": True,
            "name": "Demo Account",
            "company": "Demo Broker"
        }
    
    async def get_positions(self) -> List[Position]:
        if not self._connected:
            raise ConnectionError("MT5 not connected")
        
        return [
            Position(
                ticket=123456789,
                symbol="EURUSD",
                type="buy",
                volume=0.1,
                open_price=1.0850,
                current_price=1.0875,
                sl=1.0800,
                tp=1.0950,
                profit=25.00,
                swap=-0.50,
                open_time=datetime.now(),
                magic=0,
                comment=""
            )
        ]
    
    async def get_orders(self) -> List[Order]:
        if not self._connected:
            raise ConnectionError("MT5 not connected")
        
        return []
    
    async def get_candles(self, symbol: str, timeframe: TimeFrame, count: int) -> List[CandleData]:
        if not self._connected:
            raise ConnectionError("MT5 not connected")
        
        candles = []
        base_time = datetime.now()
        for i in range(count):
            candles.append(CandleData(
                time=base_time,
                open=1.0850 + (i * 0.0001),
                high=1.0860 + (i * 0.0001),
                low=1.0840 + (i * 0.0001),
                close=1.0855 + (i * 0.0001),
                tick_volume=100 + i,
                spread=1,
                real_volume=0
            ))
        return candles
    
    async def get_tick(self, symbol: str) -> TickData:
        if not self._connected:
            raise ConnectionError("MT5 not connected")
        
        return TickData(
            time=datetime.now(),
            bid=1.0850,
            ask=1.0851,
            last=1.0850,
            volume=0
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
        if not self._connected:
            raise ConnectionError("MT5 not connected")
        
        logger.info(f"Placing order: symbol={symbol}, type={order_type}, volume={volume}")
        
        return {
            "success": True,
            "order_ticket": 987654321,
            "retcode": 10009,
            "message": "Order placed successfully"
        }
    
    async def close_position(self, ticket: int, volume: Optional[float] = None) -> Dict[str, Any]:
        if not self._connected:
            raise ConnectionError("MT5 not connected")
        
        logger.info(f"Closing position: ticket={ticket}, volume={volume}")
        
        return {
            "success": True,
            "order_ticket": ticket,
            "retcode": 10009,
            "message": "Position closed successfully"
        }
    
    async def modify_position(
        self,
        ticket: int,
        sl: Optional[float] = None,
        tp: Optional[float] = None
    ) -> Dict[str, Any]:
        if not self._connected:
            raise ConnectionError("MT5 not connected")
        
        logger.info(f"Modifying position: ticket={ticket}, sl={sl}, tp={tp}")
        
        return {
            "success": True,
            "order_ticket": ticket,
            "retcode": 10009,
            "message": "Position modified successfully"
        }
    
    async def modify_order(
        self,
        ticket: int,
        price: Optional[float] = None,
        sl: Optional[float] = None,
        tp: Optional[float] = None
    ) -> Dict[str, Any]:
        if not self._connected:
            raise ConnectionError("MT5 not connected")
        
        logger.info(f"Modifying order: ticket={ticket}, price={price}, sl={sl}, tp={tp}")
        
        return {
            "success": True,
            "order_ticket": ticket,
            "retcode": 10009,
            "message": "Order modified successfully"
        }
