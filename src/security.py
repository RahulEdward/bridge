import logging
from typing import Optional
from fastapi import Request, HTTPException, Depends
from fastapi.security import APIKeyHeader

from src.config import settings, get_allowed_ips

logger = logging.getLogger(__name__)

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(api_key: Optional[str] = Depends(api_key_header)) -> str:
    if not settings.api_key:
        if settings.production:
            logger.error("API key not configured in production mode - denying request")
            raise HTTPException(
                status_code=500,
                detail="Server configuration error - authentication not configured"
            )
        logger.warning("API key not configured - running in development mode without authentication")
        return "dev-mode"
    
    if not api_key:
        logger.warning("API key missing in request")
        raise HTTPException(
            status_code=401,
            detail="API key required"
        )
    
    if api_key != settings.api_key:
        logger.warning("Invalid API key attempt")
        raise HTTPException(
            status_code=401,
            detail="Invalid API key"
        )
    
    return api_key


async def verify_ip_allowlist(request: Request) -> str:
    client_ip = request.client.host if request.client else "unknown"
    
    allowed_ips = get_allowed_ips()
    
    if not allowed_ips:
        return client_ip
    
    if client_ip not in allowed_ips and client_ip != "127.0.0.1":
        logger.warning(f"Request from unauthorized IP: {client_ip}")
        raise HTTPException(
            status_code=403,
            detail="IP not allowed"
        )
    
    return client_ip


async def security_check(
    api_key: str = Depends(verify_api_key),
    client_ip: str = Depends(verify_ip_allowlist)
) -> dict:
    return {"api_key": api_key, "client_ip": client_ip}
