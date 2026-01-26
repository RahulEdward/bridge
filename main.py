import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config import settings, validate_production_settings
from src.terminal_manager import terminal_manager
from src.routes import health, account, market, trade, websocket

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

validate_production_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting MT5 Execution Gateway...")
    await terminal_manager.start()
    websocket.manager.start_broadcast_loop()
    logger.info("Gateway started successfully")
    
    yield
    
    logger.info("Shutting down MT5 Execution Gateway...")
    websocket.manager.stop_broadcast_loop()
    await terminal_manager.stop()
    logger.info("Gateway shutdown complete")


app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    description="VPS-hosted execution gateway for MetaTrader 5 trading accounts",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(account.router)
app.include_router(market.router)
app.include_router(trade.router)
app.include_router(websocket.router)


@app.get("/")
async def root():
    return {
        "name": settings.app_name,
        "version": settings.version,
        "status": "running",
        "docs": "/docs"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug
    )
