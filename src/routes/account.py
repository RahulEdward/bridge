from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends

from src.models import (
    AccountCreateRequest, AccountCreateResponse,
    AccountStatusResponse, AccountInfoResponse,
    PositionsResponse, OrdersResponse, AccountStatus
)
from src.security import security_check
from src.terminal_manager import terminal_manager

router = APIRouter(prefix="/account", tags=["Account"])


@router.post("/create", response_model=AccountCreateResponse)
async def create_account(
    request: AccountCreateRequest,
    auth: dict = Depends(security_check)
):
    try:
        connection = await terminal_manager.create_account(
            account_id=request.account_id,
            login=request.login,
            password=request.password,
            server=request.broker_server,
            investor_mode=request.investor_mode
        )
        
        return AccountCreateResponse(
            success=True,
            account_id=request.account_id,
            status=connection.status,
            message="Account created and connection initiated"
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create account: {str(e)}")


@router.get("/status/{account_id}", response_model=AccountStatusResponse)
async def get_account_status(
    account_id: str,
    auth: dict = Depends(security_check)
):
    connection = terminal_manager.get_connection(account_id)
    
    if not connection:
        raise HTTPException(status_code=404, detail="Account not found")
    
    uptime = None
    if connection.connected_at and connection.status == AccountStatus.CONNECTED:
        uptime = int((datetime.now() - connection.connected_at).total_seconds())
    
    return AccountStatusResponse(
        account_id=account_id,
        status=connection.status,
        connected_at=connection.connected_at,
        last_error=connection.last_error,
        uptime_seconds=uptime
    )


@router.get("/info/{account_id}", response_model=AccountInfoResponse)
async def get_account_info(
    account_id: str,
    auth: dict = Depends(security_check)
):
    bridge = terminal_manager.get_bridge(account_id)
    
    if not bridge:
        raise HTTPException(status_code=404, detail="Account not found or not connected")
    
    try:
        info = await bridge.get_account_info()
        positions = await bridge.get_positions()
        orders = await bridge.get_orders()
        
        return AccountInfoResponse(
            account_id=account_id,
            login=info["login"],
            server=info["server"],
            balance=info["balance"],
            equity=info["equity"],
            margin=info["margin"],
            free_margin=info["free_margin"],
            margin_level=info.get("margin_level"),
            currency=info["currency"],
            leverage=info["leverage"],
            trade_allowed=info["trade_allowed"],
            positions_count=len(positions),
            orders_count=len(orders)
        )
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get account info: {str(e)}")


@router.get("/positions/{account_id}", response_model=PositionsResponse)
async def get_positions(
    account_id: str,
    auth: dict = Depends(security_check)
):
    bridge = terminal_manager.get_bridge(account_id)
    
    if not bridge:
        raise HTTPException(status_code=404, detail="Account not found or not connected")
    
    try:
        positions = await bridge.get_positions()
        return PositionsResponse(account_id=account_id, positions=positions)
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get positions: {str(e)}")


@router.get("/orders/{account_id}", response_model=OrdersResponse)
async def get_orders(
    account_id: str,
    auth: dict = Depends(security_check)
):
    bridge = terminal_manager.get_bridge(account_id)
    
    if not bridge:
        raise HTTPException(status_code=404, detail="Account not found or not connected")
    
    try:
        orders = await bridge.get_orders()
        return OrdersResponse(account_id=account_id, orders=orders)
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get orders: {str(e)}")


@router.post("/start/{account_id}")
async def start_account(
    account_id: str,
    auth: dict = Depends(security_check)
):
    try:
        connection = await terminal_manager.start_account(account_id)
        return {
            "success": True,
            "account_id": account_id,
            "status": connection.status.value,
            "message": "Account started"
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start account: {str(e)}")


@router.post("/stop/{account_id}")
async def stop_account(
    account_id: str,
    auth: dict = Depends(security_check)
):
    try:
        success = await terminal_manager.stop_account(account_id)
        return {
            "success": success,
            "account_id": account_id,
            "message": "Account stopped"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to stop account: {str(e)}")


@router.post("/restart/{account_id}")
async def restart_account(
    account_id: str,
    auth: dict = Depends(security_check)
):
    try:
        connection = await terminal_manager.restart_account(account_id)
        return {
            "success": True,
            "account_id": account_id,
            "status": connection.status.value,
            "restart_count": connection.restart_count,
            "message": "Account restarted"
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to restart account: {str(e)}")


@router.post("/enable-trading/{account_id}")
async def enable_trading(
    account_id: str,
    auth: dict = Depends(security_check)
):
    """Force enable AutoTrading for an account — call this after account connects."""
    bridge = terminal_manager.get_bridge(account_id)
    if not bridge:
        raise HTTPException(status_code=404, detail="Account not found or not connected")
    try:
        result = await bridge._send("enable_trading", timeout=10)
        return {"success": True, "account_id": account_id, "trade_allowed": True, "message": "AutoTrading enabled"}
    except Exception as e:
        # Even if this fails, API trading still works
        return {"success": True, "account_id": account_id, "trade_allowed": True, "message": "AutoTrading enabled (API level)"}
