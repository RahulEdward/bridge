import time
import psutil
from fastapi import APIRouter, Depends

from src.config import settings
from src.models import HealthResponse
from src.security import security_check
from src.terminal_manager import terminal_manager

router = APIRouter()

start_time = time.time()


@router.get("/health", response_model=HealthResponse)
async def health_check():
    uptime = int(time.time() - start_time)
    
    cpu_percent = psutil.cpu_percent(interval=0.1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    
    return HealthResponse(
        status="healthy",
        version=settings.version,
        uptime_seconds=uptime,
        active_accounts=terminal_manager.get_active_count(),
        system_resources={
            "cpu_percent": cpu_percent,
            "memory_total_gb": round(memory.total / (1024**3), 2),
            "memory_used_gb": round(memory.used / (1024**3), 2),
            "memory_percent": memory.percent,
            "disk_total_gb": round(disk.total / (1024**3), 2),
            "disk_used_gb": round(disk.used / (1024**3), 2),
            "disk_percent": disk.percent
        }
    )


@router.get("/health/detailed")
async def detailed_health(auth: dict = Depends(security_check)):
    uptime = int(time.time() - start_time)
    
    connections = terminal_manager.get_all_connections()
    
    accounts_status = []
    for conn in connections:
        accounts_status.append({
            "account_id": conn.account_id,
            "status": conn.status.value,
            "login": conn.login,
            "server": conn.server,
            "connected_at": conn.connected_at.isoformat() if conn.connected_at else None,
            "restart_count": conn.restart_count,
            "last_error": conn.last_error
        })
    
    return {
        "status": "healthy",
        "version": settings.version,
        "uptime_seconds": uptime,
        "active_accounts": terminal_manager.get_active_count(),
        "total_accounts": len(connections),
        "accounts": accounts_status,
        "system_resources": {
            "cpu_percent": psutil.cpu_percent(interval=0.1),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_percent": psutil.disk_usage("/").percent
        }
    }
