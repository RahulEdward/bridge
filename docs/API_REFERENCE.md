# MT5 Execution Gateway - API Reference

## Authentication

All authenticated endpoints require the `X-API-Key` header:

```
X-API-Key: your-api-key
```

## Base URL

```
https://your-vps-ip:port
```

---

## Health Endpoints

### GET /health

Basic health check (no authentication required).

**Response:**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "uptime_seconds": 3600,
  "active_accounts": 5,
  "system_resources": {
    "cpu_percent": 25.5,
    "memory_total_gb": 8.0,
    "memory_used_gb": 4.2,
    "memory_percent": 52.5,
    "disk_total_gb": 100.0,
    "disk_used_gb": 35.0,
    "disk_percent": 35.0
  }
}
```

### GET /health/detailed

Detailed system status (authenticated).

**Response:**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "uptime_seconds": 3600,
  "active_accounts": 5,
  "total_accounts": 10,
  "accounts": [
    {
      "account_id": "user_123",
      "status": "connected",
      "login": 12345678,
      "server": "ICMarkets-Demo",
      "connected_at": "2024-01-15T10:30:00Z",
      "restart_count": 0,
      "last_error": null
    }
  ],
  "system_resources": {...}
}
```

---

## Account Endpoints

### POST /account/create

Create and connect a new MT5 account.

**Request:**
```json
{
  "account_id": "user_123",
  "broker_server": "ICMarkets-Demo",
  "login": 12345678,
  "password": "password123",
  "investor_mode": false
}
```

**Response:**
```json
{
  "success": true,
  "account_id": "user_123",
  "status": "starting",
  "message": "Account created and connection initiated"
}
```

### GET /account/status/{account_id}

Get account connection status.

**Response:**
```json
{
  "account_id": "user_123",
  "status": "connected",
  "connected_at": "2024-01-15T10:30:00Z",
  "last_error": null,
  "uptime_seconds": 3600
}
```

**Status Values:**
- `pending` - Account created, not started
- `starting` - Connection in progress
- `connected` - Successfully connected
- `disconnected` - Lost connection
- `error` - Connection error
- `stopped` - Manually stopped

### GET /account/info/{account_id}

Get account trading information.

**Response:**
```json
{
  "account_id": "user_123",
  "login": 12345678,
  "server": "ICMarkets-Demo",
  "balance": 10000.00,
  "equity": 10250.50,
  "margin": 500.00,
  "free_margin": 9750.50,
  "margin_level": 2050.10,
  "currency": "USD",
  "leverage": 100,
  "trade_allowed": true,
  "positions_count": 2,
  "orders_count": 1
}
```

### GET /account/positions/{account_id}

Get all open positions.

**Response:**
```json
{
  "account_id": "user_123",
  "positions": [
    {
      "ticket": 123456789,
      "symbol": "EURUSD",
      "type": "buy",
      "volume": 0.1,
      "open_price": 1.0850,
      "current_price": 1.0875,
      "sl": 1.0800,
      "tp": 1.0950,
      "profit": 25.00,
      "swap": -0.50,
      "open_time": "2024-01-15T09:00:00Z",
      "magic": 0,
      "comment": ""
    }
  ]
}
```

### GET /account/orders/{account_id}

Get all pending orders.

**Response:**
```json
{
  "account_id": "user_123",
  "orders": [
    {
      "ticket": 987654321,
      "symbol": "GBPUSD",
      "type": "buy_limit",
      "volume": 0.2,
      "price": 1.2500,
      "sl": 1.2450,
      "tp": 1.2600,
      "open_time": "2024-01-15T08:00:00Z",
      "magic": 0,
      "comment": ""
    }
  ]
}
```

### POST /account/start/{account_id}

Start/reconnect an account.

### POST /account/stop/{account_id}

Stop an account connection.

### POST /account/restart/{account_id}

Restart an account connection.

---

## Market Data Endpoints

### GET /market/candles/{account_id}

Get historical candle data.

**Query Parameters:**
- `symbol` (required): Trading symbol (e.g., "EURUSD")
- `timeframe`: M1, M5, M15, M30, H1, H4, D1, W1, MN1 (default: H1)
- `count`: Number of candles, 1-1000 (default: 100)

**Response:**
```json
{
  "symbol": "EURUSD",
  "timeframe": "H1",
  "candles": [
    {
      "time": "2024-01-15T10:00:00Z",
      "open": 1.0850,
      "high": 1.0875,
      "low": 1.0840,
      "close": 1.0860,
      "tick_volume": 1500,
      "spread": 1,
      "real_volume": 0
    }
  ]
}
```

### GET /market/ticks/{account_id}

Get current tick data.

**Query Parameters:**
- `symbol` (required): Trading symbol

**Response:**
```json
{
  "symbol": "EURUSD",
  "tick": {
    "time": "2024-01-15T10:30:45Z",
    "bid": 1.0850,
    "ask": 1.0851,
    "last": 1.0850,
    "volume": 0
  }
}
```

---

## Trading Endpoints

### POST /trade/place

Place a new order.

**Request:**
```json
{
  "account_id": "user_123",
  "symbol": "EURUSD",
  "order_type": "buy",
  "volume": 0.1,
  "price": null,
  "sl": 1.0800,
  "tp": 1.0950,
  "deviation": 20,
  "magic": 12345,
  "comment": "Via SaaS"
}
```

**Order Types:**
- `buy` - Market buy
- `sell` - Market sell
- `buy_limit` - Buy limit order
- `sell_limit` - Sell limit order
- `buy_stop` - Buy stop order
- `sell_stop` - Sell stop order

**Response:**
```json
{
  "success": true,
  "order_ticket": 123456789,
  "message": "Order placed successfully",
  "retcode": 10009
}
```

### POST /trade/close

Close a position.

**Request:**
```json
{
  "account_id": "user_123",
  "ticket": 123456789,
  "volume": null
}
```

**Response:**
```json
{
  "success": true,
  "order_ticket": 123456790,
  "message": "Position closed successfully",
  "retcode": 10009
}
```

### POST /trade/modify

Modify position SL/TP.

**Request:**
```json
{
  "account_id": "user_123",
  "ticket": 123456789,
  "sl": 1.0820,
  "tp": 1.0980
}
```

**Response:**
```json
{
  "success": true,
  "order_ticket": 123456789,
  "message": "Position modified successfully",
  "retcode": 10009
}
```

---

## WebSocket Endpoint

### WS /ws/{account_id}

Real-time data streaming.

**Query Parameters:**
- `api_key`: API key for authentication

**Client Messages:**

```json
{"type": "ping"}
{"type": "subscribe_tick", "symbol": "EURUSD"}
{"type": "get_positions"}
{"type": "get_account"}
```

**Server Messages:**

```json
{"type": "pong"}

{"type": "tick", "symbol": "EURUSD", "data": {"bid": 1.0850, "ask": 1.0851, "time": "..."}}

{"type": "positions", "data": [...]}

{"type": "account", "data": {...}}

{"type": "account_update", "data": {"balance": 10000, "equity": 10250, ...}}
```

---

## Error Responses

All errors follow this format:

```json
{
  "detail": "Error message here"
}
```

**HTTP Status Codes:**
- `400` - Bad request (invalid parameters)
- `401` - Unauthorized (missing/invalid API key)
- `403` - Forbidden (IP not allowed)
- `404` - Not found (account not found)
- `500` - Internal server error
- `503` - Service unavailable (MT5 not connected)

---

## Rate Limits

Recommended limits (configurable):
- 100 requests/minute per API key
- 10 concurrent WebSocket connections per account
