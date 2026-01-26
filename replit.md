# MT5 Execution Gateway

## Overview
A VPS-hosted execution gateway that connects a SaaS application (FastAPI backend on Render, Next.js frontend) with MetaTrader 5 (MT5) trading accounts. This acts as a self-hosted MetaApi alternative.

## Admin Panel
Access the admin panel at `/` or `/admin`:
- View system health and resource usage
- Monitor connected MT5 accounts
- Add new trading accounts
- View open positions
- Restart/stop accounts
- Auto-refreshes every 10 seconds

## Architecture

```
[ SaaS App on Render ]
- FastAPI (AI logic, strategy, auth, billing)
- Next.js frontend (UI)
        |
        | HTTPS (secure, API key based)
        v
[ VPS – Execution Layer ]
- Central Gateway App (this project)
- One or more MT5 terminals
- One bridge per MT5 terminal
```

## Project Structure

```
├── main.py                 # FastAPI application entry point
├── static/
│   └── admin.html          # Admin panel UI
├── src/
│   ├── config.py           # Configuration and settings
│   ├── models.py           # Pydantic models for requests/responses
│   ├── security.py         # API key authentication and IP allowlist
│   ├── mt5_bridge.py       # MT5 communication layer (mock/dev)
│   ├── mt5_bridge_windows.py # Real MT5 bridge (Windows only)
│   ├── terminal_manager.py # MT5 lifecycle management
│   └── routes/
│       ├── health.py       # Health check endpoints
│       ├── account.py      # Account management endpoints
│       ├── market.py       # Market data endpoints
│       ├── trade.py        # Trading endpoints
│       └── websocket.py    # WebSocket for real-time data
├── docs/                   # Documentation
│   ├── DEPLOYMENT.md       # Windows VPS deployment guide
│   └── API_REFERENCE.md    # Complete API reference
├── data/                   # Runtime data storage
└── .env.example            # Environment configuration template
```

## API Endpoints

### Health
- `GET /health` - Basic health check
- `GET /health/detailed` - Detailed system status (authenticated)

### Account Management
- `POST /account/create` - Create and connect MT5 account
- `GET /account/status/{account_id}` - Get account connection status
- `GET /account/info/{account_id}` - Get account info (balance, equity, margin)
- `GET /account/positions/{account_id}` - Get open positions
- `GET /account/orders/{account_id}` - Get pending orders
- `POST /account/start/{account_id}` - Start account connection
- `POST /account/stop/{account_id}` - Stop account connection
- `POST /account/restart/{account_id}` - Restart account connection

### Market Data
- `GET /market/candles/{account_id}` - Get historical candles
- `POST /market/candles` - Get candles (POST version)
- `GET /market/ticks/{account_id}` - Get current tick data
- `POST /market/ticks` - Get tick data (POST version)

### Trading
- `POST /trade/place` - Place a new order
- `POST /trade/close` - Close a position
- `POST /trade/modify` - Modify a position (SL/TP)

### WebSocket
- `WS /ws/{account_id}` - Real-time data stream

## Configuration

Environment variables (prefix with `GATEWAY_`):
- `API_KEY` - API key for authentication from SaaS
- `ALLOWED_IPS` - Comma-separated list of allowed IPs
- `ENCRYPTION_KEY` - Fernet encryption key for credentials
- `MT5_BASE_PATH` - Base path for MT5 installations (Windows)
- `MT5_TEMPLATE_PATH` - Path to MT5 template installation
- `HEALTH_CHECK_INTERVAL` - Health check interval in seconds
- `MAX_RESTART_ATTEMPTS` - Max restart attempts for failed accounts
- `RESTART_COOLDOWN` - Cooldown between restarts in seconds

## Security Model

1. **API Key Authentication**: All endpoints (except basic health) require X-API-Key header
2. **IP Allowlist**: Optional IP restriction for incoming requests
3. **Encrypted Credentials**: MT5 passwords are stored encrypted using Fernet
4. **No Public MT5 Access**: MT5 terminals communicate only via localhost

## Deployment Notes

This gateway is designed to run on a **Windows VPS** because:
- MT5 only runs on Windows
- One MT5 terminal per user account
- Each account gets its own isolated terminal instance

## Running Locally

```bash
python main.py
```

The server starts on http://0.0.0.0:5000 with interactive docs at /docs.
