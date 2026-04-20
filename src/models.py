from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field


class AccountStatus(str, Enum):
    PENDING = "pending"
    STARTING = "starting"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    STOPPED = "stopped"


class OrderType(str, Enum):
    BUY = "buy"
    SELL = "sell"
    BUY_LIMIT = "buy_limit"
    SELL_LIMIT = "sell_limit"
    BUY_STOP = "buy_stop"
    SELL_STOP = "sell_stop"


class TimeFrame(str, Enum):
    M1 = "M1"
    M5 = "M5"
    M15 = "M15"
    M30 = "M30"
    H1 = "H1"
    H4 = "H4"
    D1 = "D1"
    W1 = "W1"
    MN1 = "MN1"


class AccountCreateRequest(BaseModel):
    account_id: str = Field(..., description="Unique account identifier from SaaS")
    broker_server: str = Field(..., description="Broker server address")
    login: int = Field(..., description="MT5 account login number")
    password: str = Field(..., description="MT5 account password")
    investor_mode: bool = Field(default=False, description="Read-only mode")


class AccountCreateResponse(BaseModel):
    success: bool
    account_id: str
    status: AccountStatus
    message: str


class AccountStatusResponse(BaseModel):
    account_id: str
    status: AccountStatus
    connected_at: Optional[datetime] = None
    last_error: Optional[str] = None
    uptime_seconds: Optional[int] = None


class AccountInfoResponse(BaseModel):
    account_id: str
    login: int
    server: str
    balance: float
    equity: float
    margin: float
    free_margin: float
    margin_level: Optional[float] = None
    currency: str
    leverage: int
    trade_allowed: bool
    positions_count: int
    orders_count: int


class Position(BaseModel):
    ticket: int
    symbol: str
    type: str
    volume: float
    open_price: float
    current_price: float
    sl: Optional[float] = None
    tp: Optional[float] = None
    profit: float
    swap: float
    open_time: datetime
    magic: int = 0
    comment: str = ""


class Order(BaseModel):
    ticket: int
    symbol: str
    type: str
    volume: float
    price: float
    sl: Optional[float] = None
    tp: Optional[float] = None
    open_time: datetime
    magic: int = 0
    comment: str = ""


class PositionsResponse(BaseModel):
    account_id: str
    positions: List[Position]


class OrdersResponse(BaseModel):
    account_id: str
    orders: List[Order]


class CandleData(BaseModel):
    time: datetime
    open: float
    high: float
    low: float
    close: float
    tick_volume: int
    spread: int
    real_volume: int


class CandlesRequest(BaseModel):
    account_id: str
    symbol: str
    timeframe: TimeFrame
    count: int = Field(default=100, ge=1)  # No upper limit — fetch as much as MT5 has


class CandlesResponse(BaseModel):
    symbol: str
    timeframe: TimeFrame
    candles: List[CandleData]


class TickData(BaseModel):
    time: datetime
    bid: float
    ask: float
    last: float
    volume: float


class TicksRequest(BaseModel):
    account_id: str
    symbol: str


class TicksResponse(BaseModel):
    symbol: str
    tick: TickData


class TradeRequest(BaseModel):
    account_id: str
    symbol: str
    order_type: OrderType
    volume: float
    price: Optional[float] = None
    sl: Optional[float] = None
    tp: Optional[float] = None
    deviation: int = 20
    magic: int = 0
    comment: str = ""


class TradeResponse(BaseModel):
    success: bool
    order_ticket: Optional[int] = None
    message: str
    retcode: Optional[int] = None


class CloseTradeRequest(BaseModel):
    account_id: str
    ticket: int
    volume: Optional[float] = None


class ModifyTradeRequest(BaseModel):
    account_id: str
    ticket: int
    sl: Optional[float] = None
    tp: Optional[float] = None
    price: Optional[float] = None


class HealthResponse(BaseModel):
    status: str
    version: str
    uptime_seconds: int
    active_accounts: int
    system_resources: Dict[str, Any]


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
    code: Optional[str] = None
