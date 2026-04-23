import os
import sys
import logging
from typing import Optional, List
from pydantic_settings import BaseSettings
from pydantic import Field
from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    app_name: str = "MT5 Execution Gateway"
    version: str = "1.0.0"
    debug: bool = False
    production: bool = Field(default=False, description="Production mode - enforces security requirements")
    
    host: str = "0.0.0.0"
    port: int = 5000
    
    api_key: str = Field(default="", description="API key for authentication from SaaS")
    allowed_ips: str = Field(default="", description="Comma-separated list of allowed IPs")
    
    encryption_key: str = Field(default="", description="Fernet encryption key for credentials")
    
    mt5_base_path: str = Field(default="C:\\MT5_INSTANCES", description="Base path for per-user MT5 instances")
    mt5_template_path: str = Field(default="C:\\MT5Template", description="Path to MT5 template installation")
    
    health_check_interval: int = 30
    max_restart_attempts: int = 3
    restart_cooldown: int = 60
    
    db_path: str = "data/gateway.db"
    
    class Config:
        env_file = ".env"
        env_prefix = "GATEWAY_"


settings = Settings()

_cached_encryption_key: Optional[bytes] = None


def validate_production_settings():
    if settings.production:
        errors = []
        
        if not settings.api_key:
            errors.append("GATEWAY_API_KEY is required in production mode")
        
        if not settings.encryption_key:
            errors.append("GATEWAY_ENCRYPTION_KEY is required in production mode")
        
        if errors:
            for error in errors:
                logger.critical(f"Production validation failed: {error}")
            print("\n*** PRODUCTION MODE SECURITY ERROR ***")
            print("The following required settings are missing:")
            for error in errors:
                print(f"  - {error}")
            print("\nGenerate encryption key with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"")
            print("***\n")
            sys.exit(1)


def get_encryption_key() -> bytes:
    global _cached_encryption_key
    
    if _cached_encryption_key is not None:
        return _cached_encryption_key
    
    if settings.encryption_key:
        _cached_encryption_key = settings.encryption_key.encode()
        return _cached_encryption_key
    
    if settings.production:
        raise RuntimeError("Encryption key required in production mode")
    
    logger.warning("No encryption key configured - generating temporary key (credentials will not persist across restarts)")
    _cached_encryption_key = Fernet.generate_key()
    return _cached_encryption_key


def encrypt_credentials(data: str) -> str:
    key = get_encryption_key()
    f = Fernet(key)
    return f.encrypt(data.encode()).decode()


def decrypt_credentials(encrypted_data: str) -> str:
    key = get_encryption_key()
    f = Fernet(key)
    return f.decrypt(encrypted_data.encode()).decode()


def get_allowed_ips() -> List[str]:
    if not settings.allowed_ips:
        return []
    return [ip.strip() for ip in settings.allowed_ips.split(",") if ip.strip()]
