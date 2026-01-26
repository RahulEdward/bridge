# MT5 Execution Gateway - Windows VPS Deployment Guide

## Overview

This guide covers deploying the MT5 Execution Gateway on a Windows VPS to enable your SaaS application to control MetaTrader 5 trading accounts.

## System Requirements

### Windows VPS Specifications
- **OS**: Windows Server 2019/2022 or Windows 10/11
- **CPU**: 2+ cores (more for multiple accounts)
- **RAM**: 4GB minimum + ~500MB per MT5 terminal
- **Storage**: 50GB SSD minimum
- **Network**: Static IP, low latency to brokers

### Software Requirements
- Python 3.11+
- MetaTrader 5 terminals
- SSL certificate (for HTTPS)

## Installation Steps

### 1. Install Python

```powershell
# Download and install Python 3.11
# Ensure "Add to PATH" is checked during installation
winget install Python.Python.3.11
```

### 2. Install Dependencies

```powershell
# Navigate to project directory
cd C:\MT5Gateway

# Install Python dependencies
pip install -r requirements.txt

# Install MetaTrader5 package (Windows only)
pip install MetaTrader5
```

### 3. Configure Environment

Create `.env` file:

```env
# REQUIRED for production - gateway will not start without these
GATEWAY_PRODUCTION=true
GATEWAY_API_KEY=your-secure-api-key-here
GATEWAY_ENCRYPTION_KEY=your-fernet-key-here

# Optional: restrict access to specific IPs
GATEWAY_ALLOWED_IPS=render-ip-1,render-ip-2

# MT5 paths
GATEWAY_MT5_BASE_PATH=C:\MT5Terminals
GATEWAY_MT5_TEMPLATE_PATH=C:\Program Files\MetaTrader 5

# Server settings
GATEWAY_HOST=0.0.0.0
GATEWAY_PORT=443
```

**IMPORTANT**: In production mode (`GATEWAY_PRODUCTION=true`), the gateway will refuse to start if `GATEWAY_API_KEY` or `GATEWAY_ENCRYPTION_KEY` are not set.

Generate encryption key:
```python
from cryptography.fernet import Fernet
print(Fernet.generate_key().decode())
```

### 4. Set Up MT5 Template

1. Install MetaTrader 5 to `C:\Program Files\MetaTrader 5`
2. Configure it as a portable installation
3. This will be copied for each new account

### 5. MT5 Bridge Selection (Automatic)

The gateway automatically detects the operating system:
- **Windows**: Uses real MetaTrader5 Python integration
- **Linux/Mac**: Uses mock bridge for development/testing

No manual configuration needed - just ensure MetaTrader5 package is installed on Windows:
```powershell
pip install MetaTrader5
```

### 6. Install as Windows Service

Using NSSM (Non-Sucking Service Manager):

```powershell
# Download NSSM
# https://nssm.cc/download

# Install service
nssm install MT5Gateway "C:\Python311\python.exe" "C:\MT5Gateway\main.py"
nssm set MT5Gateway AppDirectory "C:\MT5Gateway"
nssm set MT5Gateway AppEnvironmentExtra "PYTHONPATH=C:\MT5Gateway"

# Start service
nssm start MT5Gateway
```

### 7. Configure Firewall

```powershell
# Allow incoming connections on port 443
New-NetFirewallRule -DisplayName "MT5 Gateway" -Direction Inbound -Port 443 -Protocol TCP -Action Allow
```

### 8. Set Up SSL (Recommended)

Using Let's Encrypt with win-acme:

```powershell
# Download win-acme
# https://www.win-acme.com/

# Generate certificate
wacs --target manual --host gateway.yourdomain.com

# Update main.py to use SSL
uvicorn.run(
    "main:app",
    host="0.0.0.0",
    port=443,
    ssl_keyfile="path/to/key.pem",
    ssl_certfile="path/to/cert.pem"
)
```

## Folder Structure on VPS

```
C:\
├── MT5Gateway\
│   ├── main.py
│   ├── src\
│   ├── data\
│   │   └── accounts.json
│   └── logs\
├── MT5Terminals\
│   ├── MT5_account_001\
│   │   └── terminal64.exe
│   ├── MT5_account_002\
│   │   └── terminal64.exe
│   └── ...
└── Program Files\
    └── MetaTrader 5\        # Template installation
```

## Process Architecture

```
[Windows Service: MT5Gateway]
    │
    ├── main.py (FastAPI server)
    │
    └── [Per Account]
        ├── MT5Bridge instance
        │   └── MetaTrader5 Python connection
        └── terminal64.exe process
```

## SaaS Integration

### From Your Render Backend

```python
import httpx

GATEWAY_URL = "https://your-vps-ip:443"
API_KEY = "your-api-key"

headers = {"X-API-Key": API_KEY}

# Create account
response = httpx.post(
    f"{GATEWAY_URL}/account/create",
    headers=headers,
    json={
        "account_id": "user_123",
        "broker_server": "ICMarkets-Demo",
        "login": 12345678,
        "password": "password123",
        "investor_mode": False
    }
)

# Get account info
response = httpx.get(
    f"{GATEWAY_URL}/account/info/user_123",
    headers=headers
)

# Place trade
response = httpx.post(
    f"{GATEWAY_URL}/trade/place",
    headers=headers,
    json={
        "account_id": "user_123",
        "symbol": "EURUSD",
        "order_type": "buy",
        "volume": 0.1,
        "sl": 1.0800,
        "tp": 1.0950
    }
)
```

### WebSocket Connection

```python
import websockets
import json

async def stream_data():
    uri = f"wss://your-vps-ip:443/ws/user_123?api_key={API_KEY}"
    
    async with websockets.connect(uri) as ws:
        # Subscribe to ticks
        await ws.send(json.dumps({
            "type": "subscribe_tick",
            "symbol": "EURUSD"
        }))
        
        while True:
            message = await ws.recv()
            data = json.loads(message)
            print(f"Received: {data}")
```

## Scaling

### Multiple Accounts per VPS
- Each MT5 terminal uses ~300-500MB RAM
- Typical VPS (8GB RAM) can handle 10-15 accounts
- Monitor CPU during high-frequency trading

### Multiple VPS Nodes
1. Deploy gateway on multiple VPS servers
2. Use load balancer or direct routing from SaaS
3. Assign accounts to specific nodes
4. Store node mapping in your SaaS database

### High Availability
- Set up secondary VPS for failover
- Implement health check monitoring
- Auto-restart crashed terminals

## Monitoring

### Health Check Endpoint

```bash
curl https://your-vps-ip:443/health
```

### Detailed Status

```bash
curl -H "X-API-Key: your-key" https://your-vps-ip:443/health/detailed
```

### Windows Event Logs

```powershell
Get-EventLog -LogName Application -Source MT5Gateway -Newest 20
```

## Troubleshooting

### MT5 Connection Issues
- Verify broker server address
- Check login credentials
- Ensure terminal path is correct
- Review MT5 terminal logs

### Performance Issues
- Monitor memory usage per terminal
- Check network latency to brokers
- Review system resources with `Get-Process`

### Service Won't Start
- Check Windows Event Viewer
- Verify Python path in service config
- Review gateway logs in `logs/` directory

## Security Checklist

- [ ] Strong API key configured
- [ ] IP allowlist enabled
- [ ] SSL/TLS certificate installed
- [ ] Firewall rules configured
- [ ] Credentials encrypted at rest
- [ ] Regular security updates applied
- [ ] Audit logging enabled
