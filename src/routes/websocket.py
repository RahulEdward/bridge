import asyncio
import json
import logging
from typing import Dict, Set
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from src.config import settings
from src.terminal_manager import terminal_manager

logger = logging.getLogger(__name__)
router = APIRouter()


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        self._running = False
        self._broadcast_task = None
    
    async def connect(self, websocket: WebSocket, account_id: str):
        await websocket.accept()
        
        if account_id not in self.active_connections:
            self.active_connections[account_id] = set()
        
        self.active_connections[account_id].add(websocket)
        logger.info(f"WebSocket connected for account {account_id}")
    
    def disconnect(self, websocket: WebSocket, account_id: str):
        if account_id in self.active_connections:
            self.active_connections[account_id].discard(websocket)
            if not self.active_connections[account_id]:
                del self.active_connections[account_id]
        logger.info(f"WebSocket disconnected for account {account_id}")
    
    async def send_to_account(self, account_id: str, message: dict):
        if account_id not in self.active_connections:
            return
        
        dead_connections = set()
        
        for connection in self.active_connections[account_id]:
            try:
                await connection.send_json(message)
            except Exception:
                dead_connections.add(connection)
        
        for dead in dead_connections:
            self.active_connections[account_id].discard(dead)
    
    async def broadcast(self, message: dict):
        for account_id in list(self.active_connections.keys()):
            await self.send_to_account(account_id, message)
    
    def start_broadcast_loop(self):
        self._running = True
        self._broadcast_task = asyncio.create_task(self._broadcast_loop())
    
    def stop_broadcast_loop(self):
        self._running = False
        if self._broadcast_task:
            self._broadcast_task.cancel()
    
    async def _broadcast_loop(self):
        while self._running:
            try:
                await asyncio.sleep(1)
                
                for account_id in list(self.active_connections.keys()):
                    bridge = terminal_manager.get_bridge(account_id)
                    if not bridge or not bridge.is_connected():
                        continue
                    
                    try:
                        info = await bridge.get_account_info()
                        positions = await bridge.get_positions()
                        
                        await self.send_to_account(account_id, {
                            "type": "account_update",
                            "data": {
                                "balance": info["balance"],
                                "equity": info["equity"],
                                "margin": info["margin"],
                                "free_margin": info["free_margin"],
                                "positions_count": len(positions)
                            }
                        })
                    except Exception as e:
                        logger.error(f"Error broadcasting to {account_id}: {e}")
            
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Broadcast loop error: {e}")


manager = ConnectionManager()


@router.websocket("/ws/{account_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    account_id: str,
    api_key: str = Query(None)
):
    if settings.api_key and api_key != settings.api_key:
        await websocket.close(code=4001, reason="Invalid API key")
        return
    
    bridge = terminal_manager.get_bridge(account_id)
    if not bridge:
        await websocket.close(code=4004, reason="Account not found")
        return
    
    await manager.connect(websocket, account_id)
    
    try:
        while True:
            data = await websocket.receive_text()
            
            try:
                message = json.loads(data)
                msg_type = message.get("type")
                
                if msg_type == "ping":
                    await websocket.send_json({"type": "pong"})
                
                elif msg_type == "subscribe_tick":
                    symbol = message.get("symbol")
                    if symbol:
                        tick = await bridge.get_tick(symbol)
                        await websocket.send_json({
                            "type": "tick",
                            "symbol": symbol,
                            "data": {
                                "bid": tick.bid,
                                "ask": tick.ask,
                                "time": tick.time.isoformat()
                            }
                        })
                
                elif msg_type == "get_positions":
                    positions = await bridge.get_positions()
                    await websocket.send_json({
                        "type": "positions",
                        "data": [
                            {
                                "ticket": p.ticket,
                                "symbol": p.symbol,
                                "type": p.type,
                                "volume": p.volume,
                                "profit": p.profit
                            }
                            for p in positions
                        ]
                    })
                
                elif msg_type == "get_account":
                    info = await bridge.get_account_info()
                    await websocket.send_json({
                        "type": "account",
                        "data": info
                    })
                
            except json.JSONDecodeError:
                await websocket.send_json({"error": "Invalid JSON"})
            except Exception as e:
                await websocket.send_json({"error": str(e)})
    
    except WebSocketDisconnect:
        manager.disconnect(websocket, account_id)
