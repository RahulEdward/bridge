from fastapi import APIRouter, HTTPException, Depends

from src.models import (
    TradeRequest, TradeResponse,
    CloseTradeRequest, ModifyTradeRequest
)
from src.security import security_check
from src.terminal_manager import terminal_manager

router = APIRouter(prefix="/trade", tags=["Trading"])


@router.post("/place", response_model=TradeResponse)
async def place_trade(
    request: TradeRequest,
    auth: dict = Depends(security_check)
):
    bridge = terminal_manager.get_bridge(request.account_id)
    
    if not bridge:
        raise HTTPException(status_code=404, detail="Account not found or not connected")
    
    try:
        result = await bridge.place_order(
            symbol=request.symbol,
            order_type=request.order_type,
            volume=request.volume,
            price=request.price,
            sl=request.sl,
            tp=request.tp,
            deviation=request.deviation,
            magic=request.magic,
            comment=request.comment
        )
        
        return TradeResponse(
            success=result["success"],
            order_ticket=result.get("order_ticket"),
            message=result["message"],
            retcode=result.get("retcode")
        )
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to place trade: {str(e)}")


@router.post("/close", response_model=TradeResponse)
async def close_trade(
    request: CloseTradeRequest,
    auth: dict = Depends(security_check)
):
    bridge = terminal_manager.get_bridge(request.account_id)
    
    if not bridge:
        raise HTTPException(status_code=404, detail="Account not found or not connected")
    
    try:
        result = await bridge.close_position(
            ticket=request.ticket,
            volume=request.volume
        )
        
        return TradeResponse(
            success=result["success"],
            order_ticket=result.get("order_ticket"),
            message=result["message"],
            retcode=result.get("retcode")
        )
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to close trade: {str(e)}")


@router.post("/modify", response_model=TradeResponse)
async def modify_trade(
    request: ModifyTradeRequest,
    auth: dict = Depends(security_check)
):
    bridge = terminal_manager.get_bridge(request.account_id)
    
    if not bridge:
        raise HTTPException(status_code=404, detail="Account not found or not connected")
    
    try:
        result = await bridge.modify_position(
            ticket=request.ticket,
            sl=request.sl,
            tp=request.tp
        )
        
        return TradeResponse(
            success=result["success"],
            order_ticket=result.get("order_ticket"),
            message=result["message"],
            retcode=result.get("retcode")
        )
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to modify trade: {str(e)}")
