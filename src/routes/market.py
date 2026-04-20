from fastapi import APIRouter, HTTPException, Depends, Query

from src.models import (
    CandlesRequest, CandlesResponse,
    TicksRequest, TicksResponse, TimeFrame
)
from src.security import security_check
from src.terminal_manager import terminal_manager

router = APIRouter(prefix="/market", tags=["Market Data"])


@router.get("/candles/{account_id}", response_model=CandlesResponse)
async def get_candles(
    account_id: str,
    symbol: str = Query(..., description="Trading symbol (e.g., EURUSD)"),
    timeframe: TimeFrame = Query(TimeFrame.H1, description="Candle timeframe"),
    count: int = Query(100, ge=1, description="Number of candles — no upper limit, fetch all available"),
    auth: dict = Depends(security_check)
):
    bridge = terminal_manager.get_bridge(account_id)
    
    if not bridge:
        raise HTTPException(status_code=404, detail="Account not found or not connected")
    
    try:
        candles = await bridge.get_candles(symbol, timeframe, count)
        return CandlesResponse(
            symbol=symbol,
            timeframe=timeframe,
            candles=candles
        )
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get candles: {str(e)}")


@router.post("/candles", response_model=CandlesResponse)
async def get_candles_post(
    request: CandlesRequest,
    auth: dict = Depends(security_check)
):
    bridge = terminal_manager.get_bridge(request.account_id)
    
    if not bridge:
        raise HTTPException(status_code=404, detail="Account not found or not connected")
    
    try:
        candles = await bridge.get_candles(request.symbol, request.timeframe, request.count)
        return CandlesResponse(
            symbol=request.symbol,
            timeframe=request.timeframe,
            candles=candles
        )
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get candles: {str(e)}")


@router.get("/ticks/{account_id}", response_model=TicksResponse)
async def get_ticks(
    account_id: str,
    symbol: str = Query(..., description="Trading symbol (e.g., EURUSD)"),
    auth: dict = Depends(security_check)
):
    bridge = terminal_manager.get_bridge(account_id)
    
    if not bridge:
        raise HTTPException(status_code=404, detail="Account not found or not connected")
    
    try:
        tick = await bridge.get_tick(symbol)
        return TicksResponse(symbol=symbol, tick=tick)
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get tick: {str(e)}")


@router.post("/ticks", response_model=TicksResponse)
async def get_ticks_post(
    request: TicksRequest,
    auth: dict = Depends(security_check)
):
    bridge = terminal_manager.get_bridge(request.account_id)
    
    if not bridge:
        raise HTTPException(status_code=404, detail="Account not found or not connected")
    
    try:
        tick = await bridge.get_tick(request.symbol)
        return TicksResponse(symbol=request.symbol, tick=tick)
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get tick: {str(e)}")
