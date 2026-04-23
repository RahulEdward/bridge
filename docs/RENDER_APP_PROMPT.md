# 🚀 Render SaaS App — AI Prompt (FastAPI + Next.js)

Yeh prompt copy karke kisi bhi AI (Claude, ChatGPT, Cursor, Bolt, Replit Agent) ko do.
Yeh tumhare Render pe hosted SaaS app ko Windows VPS pe running MT5 Gateway se fully integrate karega.

---

## PROMPT START

Tu ek senior full-stack developer hai. Mere paas ek **production MT5 Execution Gateway** chal raha hai Windows VPS pe jo MetaTrader 5 trading accounts ko REST API se control karta hai. Mujhe ek complete SaaS trading app banana hai jo Render pe host hogi.

---

### 🔧 Architecture

```
[User Browser]
     ↓
[Next.js Frontend — Render]
     ↓
[FastAPI Backend — Render]
     ↓ (HTTP + WebSocket)
[MT5 Gateway — Windows VPS]
     ↓
[MetaTrader 5 Terminals]
     ↓
[Broker Servers]
```

---

### 🔑 Gateway Connection Details

```
Gateway URL  : http://<VPS_IP>:5000
Auth Header  : X-API-Key: <YOUR_API_KEY>
WebSocket    : ws://<VPS_IP>:5000/ws/{account_id}?api_key=<YOUR_API_KEY>
```

Environment variables set karo Render pe:
```
GATEWAY_URL=http://<VPS_IP>:5000
GATEWAY_API_KEY=<YOUR_API_KEY>
```

---

### 📡 Complete API Reference

#### Gateway Endpoints (High-Level — SaaS ke liye recommended)

**POST /gateway/connect_mt5** — User ka MT5 account connect karo
```json
{
  "user_id": "user_123",
  "login": 12345678,
  "password": "mt5password",
  "server": "ICMarkets-Demo",
  "investor_mode": false
}
```
Response:
```json
{
  "success": true,
  "user_id": "user_123",
  "status": "starting",
  "message": "MT5 instance created and connection initiated"
}
```

**POST /gateway/start_trading** — Trading engine activate karo with risk params
```json
{
  "user_id": "user_123",
  "max_positions": 20,
  "max_volume_per_trade": 10.0,
  "max_drawdown_percent": 30.0
}
```

**POST /gateway/stop_trading** — Trading engine stop karo
```json
{
  "user_id": "user_123",
  "close_all_positions": false
}
```

**GET /gateway/status/{user_id}** — Full status: connection + engine + account
```json
{
  "user_id": "user_123",
  "connection": {
    "status": "connected",
    "login": 12345678,
    "server": "ICMarkets-Demo",
    "connected_at": "2025-01-15T10:30:00",
    "last_error": null,
    "restart_count": 0
  },
  "trading_engine": {
    "is_active": true,
    "trades_executed": 15,
    "max_positions": 20
  },
  "account": {
    "balance": 10000.00,
    "equity": 10250.50,
    "margin": 500.00,
    "free_margin": 9750.50,
    "currency": "USD",
    "leverage": 100,
    "trade_allowed": true,
    "open_positions": 2
  }
}
```

**POST /gateway/buy** — Quick buy
```json
{
  "user_id": "user_123",
  "symbol": "EURUSD",
  "volume": 0.01,
  "sl": 1.0800,
  "tp": 1.0950,
  "comment": "SaaS trade"
}
```

**POST /gateway/sell** — Quick sell
```json
{
  "user_id": "user_123",
  "symbol": "EURUSD",
  "volume": 0.01,
  "sl": 1.0950,
  "tp": 1.0800,
  "comment": "SaaS trade"
}
```

**GET /gateway/positions/{user_id}** — Open positions
**GET /gateway/balance/{user_id}** — Balance/equity
**POST /gateway/disconnect/{user_id}** — Disconnect user

---

#### Account Endpoints (Low-Level)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/account/create` | MT5 account add karo |
| GET | `/account/status/{id}` | Connection status |
| GET | `/account/info/{id}` | Balance, equity, margin |
| GET | `/account/positions/{id}` | Open positions |
| GET | `/account/orders/{id}` | Pending orders |
| POST | `/account/start/{id}` | Account start karo |
| POST | `/account/stop/{id}` | Account stop karo |
| POST | `/account/restart/{id}` | Account restart karo |
| POST | `/account/enable-trading/{id}` | AutoTrading force enable |

#### Trading Endpoints

**POST /trade/place**
```json
{
  "account_id": "user_123",
  "symbol": "EURUSD",
  "order_type": "buy",
  "volume": 0.01,
  "sl": null,
  "tp": null,
  "price": null,
  "deviation": 20,
  "magic": 0,
  "comment": ""
}
```
order_type values: `buy`, `sell`, `buy_limit`, `sell_limit`, `buy_stop`, `sell_stop`

**POST /trade/close**
```json
{ "account_id": "user_123", "ticket": 123456789, "volume": null }
```

**POST /trade/modify**
```json
{ "account_id": "user_123", "ticket": 123456789, "sl": 1.0800, "tp": 1.0950 }
```

#### Market Data

- `GET /market/candles/{account_id}?symbol=EURUSD&timeframe=H1&count=100`
- `GET /market/ticks/{account_id}?symbol=EURUSD`

Timeframes: `M1`, `M5`, `M15`, `M30`, `H1`, `H4`, `D1`, `W1`, `MN1`

#### WebSocket — Real-time

```
ws://<VPS_IP>:5000/ws/{account_id}?api_key=<API_KEY>
```

Server har second bhejta hai:
```json
{"type": "account_update", "data": {"balance": 10000, "equity": 10250, "margin": 500, "free_margin": 9750, "positions_count": 2}}
```

Client bhej sakta hai:
```json
{"type": "ping"}
{"type": "get_positions"}
{"type": "get_account"}
{"type": "subscribe_tick", "symbol": "EURUSD"}
```

#### Health

- `GET /health` — No auth needed, gateway health check

---

### 🎯 Kya banana hai

#### FastAPI Backend (Render pe host)

1. **Gateway Client Service** (`services/mt5_gateway.py`)
   - Saare gateway API calls wrapped in async functions
   - Proper error handling, timeouts, retries
   - Environment variables se URL aur API key
   - Connection pooling with httpx.AsyncClient

2. **User Authentication System**
   - JWT based auth (signup, login, logout)
   - Har user ka apna account_id mapping
   - Database mein user → MT5 account mapping store karo

3. **API Routes:**
   - `POST /api/auth/signup` — User registration
   - `POST /api/auth/login` — JWT token return
   - `POST /api/trading/connect` — User ka MT5 connect karo (calls /gateway/connect_mt5)
   - `POST /api/trading/start` — Trading start karo (calls /gateway/start_trading)
   - `POST /api/trading/stop` — Trading stop karo (calls /gateway/stop_trading)
   - `GET /api/trading/status` — User ka full status
   - `POST /api/trading/buy` — Buy order (calls /gateway/buy)
   - `POST /api/trading/sell` — Sell order (calls /gateway/sell)
   - `GET /api/trading/positions` — Open positions
   - `GET /api/trading/balance` — Balance/equity
   - `GET /api/trading/candles?symbol=EURUSD&timeframe=H1&count=100`
   - `POST /api/trading/close` — Close position
   - `POST /api/trading/modify` — Modify SL/TP
   - `GET /api/accounts` — User ke saare connected accounts
   - `POST /api/accounts/disconnect` — Account disconnect

4. **WebSocket Proxy**
   - Backend se gateway ka WebSocket connect karo
   - Frontend ko real-time data forward karo
   - API key backend mein safe rahe

#### Next.js Frontend (Render pe host)

1. **Pages:**
   - `/login` — Login page
   - `/signup` — Registration page
   - `/dashboard` — Main trading dashboard
   - `/connect` — MT5 account connect form
   - `/settings` — Account settings, risk parameters

2. **Dashboard Components:**
   - **Account Overview Card** — Balance, equity, margin, free margin, currency
   - **Positions Table** — Open positions with: ticket, symbol, type, volume, open price, current price, P&L, SL, TP, close button
   - **Trade Panel** — Symbol selector, buy/sell buttons, volume input, SL/TP inputs
   - **Connection Status Badge** — Real-time status (connected/disconnected/error)
   - **P&L Chart** — Equity curve over time
   - **Quick Actions** — Close all positions, stop trading

3. **Real-time Updates:**
   - WebSocket connection for live balance/equity
   - Auto-refresh positions every 2 seconds
   - Live P&L updates on open positions

4. **Connect Account Form:**
   - Broker server input (dropdown with common brokers)
   - Login number input
   - Password input (secure)
   - Investor mode toggle
   - Connect button with loading state

---

### ⚠️ Important Rules

1. **API Key KABHI browser mein expose mat karo** — saare gateway calls backend se karo
2. **Environment variables use karo:** `GATEWAY_URL`, `GATEWAY_API_KEY`
3. **Error handling proper karo** — loading states, error messages, retry buttons
4. **JWT token har request mein bhejo** — Authorization: Bearer <token>
5. **CORS configure karo** — frontend domain allow karo
6. **Rate limiting lagao** — abuse prevent karo
7. **Input validation** — volume, symbol, SL/TP validate karo frontend + backend dono pe
8. **Responsive design** — mobile pe bhi kaam kare

---

### 📁 Expected Project Structure

```
render-saas-app/
├── backend/                    # FastAPI (Render Web Service)
│   ├── main.py                 # FastAPI app entry
│   ├── config.py               # Settings, env vars
│   ├── auth/
│   │   ├── jwt_handler.py      # JWT create/verify
│   │   ├── models.py           # User models
│   │   └── routes.py           # Auth endpoints
│   ├── services/
│   │   └── mt5_gateway.py      # Gateway client (all API calls)
│   ├── routes/
│   │   ├── trading.py          # Trading endpoints
│   │   ├── accounts.py         # Account management
│   │   └── market.py           # Market data
│   ├── database.py             # DB connection (SQLite/PostgreSQL)
│   ├── requirements.txt
│   └── Dockerfile
│
├── frontend/                   # Next.js (Render Static Site)
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx            # Landing/redirect
│   │   ├── login/page.tsx
│   │   ├── signup/page.tsx
│   │   ├── dashboard/page.tsx  # Main trading UI
│   │   ├── connect/page.tsx    # MT5 connect form
│   │   └── settings/page.tsx
│   ├── components/
│   │   ├── AccountCard.tsx
│   │   ├── PositionsTable.tsx
│   │   ├── TradePanel.tsx
│   │   ├── StatusBadge.tsx
│   │   └── EquityChart.tsx
│   ├── lib/
│   │   ├── api.ts              # Backend API client
│   │   └── websocket.ts        # WebSocket hook
│   ├── package.json
│   └── Dockerfile
│
└── docker-compose.yml          # Local development
```

---

### 🔐 Render Environment Variables

**Backend Service:**
```
GATEWAY_URL=http://<VPS_IP>:5000
GATEWAY_API_KEY=<your-gateway-api-key>
JWT_SECRET=<random-secret-key>
DATABASE_URL=postgresql://<render-db-url>
FRONTEND_URL=https://<your-frontend>.onrender.com
```

**Frontend (Static Site):**
```
NEXT_PUBLIC_API_URL=https://<your-backend>.onrender.com
```

---

### 🔄 User Flow

```
1. User signup/login → JWT token milta hai
2. User MT5 credentials deta hai → Backend calls /gateway/connect_mt5
3. Gateway MT5 instance create karta hai → AutoTrading enable → Connected
4. User dashboard pe aata hai → Balance, positions dikhte hain (real-time)
5. User buy/sell karta hai → Backend calls /gateway/buy or /gateway/sell
6. Positions table mein live P&L update hota hai
7. User close karta hai → Backend calls /trade/close
8. User disconnect karta hai → Backend calls /gateway/disconnect/{user_id}
```

---

### 💡 Gateway Client Example (Python — Backend)

```python
# services/mt5_gateway.py
import httpx
import os

GATEWAY_URL = os.getenv("GATEWAY_URL")
GATEWAY_API_KEY = os.getenv("GATEWAY_API_KEY")
HEADERS = {"X-API-Key": GATEWAY_API_KEY, "Content-Type": "application/json"}

async def connect_mt5(user_id: str, login: int, password: str, server: str):
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{GATEWAY_URL}/gateway/connect_mt5", headers=HEADERS, json={
            "user_id": user_id, "login": login, "password": password, "server": server
        })
        r.raise_for_status()
        return r.json()

async def start_trading(user_id: str, max_positions: int = 20):
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(f"{GATEWAY_URL}/gateway/start_trading", headers=HEADERS, json={
            "user_id": user_id, "max_positions": max_positions
        })
        r.raise_for_status()
        return r.json()

async def buy(user_id: str, symbol: str, volume: float, sl=None, tp=None):
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(f"{GATEWAY_URL}/gateway/buy", headers=HEADERS, json={
            "user_id": user_id, "symbol": symbol, "volume": volume, "sl": sl, "tp": tp
        })
        r.raise_for_status()
        return r.json()

async def sell(user_id: str, symbol: str, volume: float, sl=None, tp=None):
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(f"{GATEWAY_URL}/gateway/sell", headers=HEADERS, json={
            "user_id": user_id, "symbol": symbol, "volume": volume, "sl": sl, "tp": tp
        })
        r.raise_for_status()
        return r.json()

async def get_status(user_id: str):
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(f"{GATEWAY_URL}/gateway/status/{user_id}", headers=HEADERS)
        r.raise_for_status()
        return r.json()

async def get_positions(user_id: str):
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(f"{GATEWAY_URL}/gateway/positions/{user_id}", headers=HEADERS)
        r.raise_for_status()
        return r.json()

async def get_balance(user_id: str):
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(f"{GATEWAY_URL}/gateway/balance/{user_id}", headers=HEADERS)
        r.raise_for_status()
        return r.json()

async def close_position(user_id: str, ticket: int):
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(f"{GATEWAY_URL}/trade/close", headers=HEADERS, json={
            "account_id": user_id, "ticket": ticket
        })
        r.raise_for_status()
        return r.json()

async def stop_trading(user_id: str, close_all: bool = False):
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(f"{GATEWAY_URL}/gateway/stop_trading", headers=HEADERS, json={
            "user_id": user_id, "close_all_positions": close_all
        })
        r.raise_for_status()
        return r.json()

async def disconnect(user_id: str):
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(f"{GATEWAY_URL}/gateway/disconnect/{user_id}", headers=HEADERS)
        r.raise_for_status()
        return r.json()

async def get_candles(user_id: str, symbol: str, timeframe: str = "H1", count: int = 100):
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(
            f"{GATEWAY_URL}/market/candles/{user_id}",
            headers=HEADERS,
            params={"symbol": symbol, "timeframe": timeframe, "count": count}
        )
        r.raise_for_status()
        return r.json()

async def health_check():
    async with httpx.AsyncClient(timeout=5) as client:
        r = await client.get(f"{GATEWAY_URL}/health")
        return r.json()
```

---

### 💡 Next.js API Client Example (TypeScript — Frontend)

```typescript
// lib/api.ts
const API_URL = process.env.NEXT_PUBLIC_API_URL;

async function fetchAPI(endpoint: string, options: RequestInit = {}) {
  const token = localStorage.getItem("token");
  const res = await fetch(`${API_URL}${endpoint}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: "Request failed" }));
    throw new Error(error.detail || "Request failed");
  }
  return res.json();
}

export const api = {
  // Auth
  login: (email: string, password: string) =>
    fetchAPI("/api/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }),
  signup: (email: string, password: string, name: string) =>
    fetchAPI("/api/auth/signup", { method: "POST", body: JSON.stringify({ email, password, name }) }),

  // Trading
  connectMT5: (login: number, password: string, server: string) =>
    fetchAPI("/api/trading/connect", { method: "POST", body: JSON.stringify({ login, password, server }) }),
  startTrading: (maxPositions?: number) =>
    fetchAPI("/api/trading/start", { method: "POST", body: JSON.stringify({ max_positions: maxPositions }) }),
  stopTrading: (closeAll?: boolean) =>
    fetchAPI("/api/trading/stop", { method: "POST", body: JSON.stringify({ close_all_positions: closeAll }) }),
  getStatus: () => fetchAPI("/api/trading/status"),
  buy: (symbol: string, volume: number, sl?: number, tp?: number) =>
    fetchAPI("/api/trading/buy", { method: "POST", body: JSON.stringify({ symbol, volume, sl, tp }) }),
  sell: (symbol: string, volume: number, sl?: number, tp?: number) =>
    fetchAPI("/api/trading/sell", { method: "POST", body: JSON.stringify({ symbol, volume, sl, tp }) }),
  getPositions: () => fetchAPI("/api/trading/positions"),
  getBalance: () => fetchAPI("/api/trading/balance"),
  closePosition: (ticket: number) =>
    fetchAPI("/api/trading/close", { method: "POST", body: JSON.stringify({ ticket }) }),
  disconnect: () => fetchAPI("/api/accounts/disconnect", { method: "POST" }),
  getCandles: (symbol: string, timeframe: string, count: number) =>
    fetchAPI(`/api/trading/candles?symbol=${symbol}&timeframe=${timeframe}&count=${count}`),
};
```

---

Ab yeh sab bana do — clean, modular, production-ready code with proper error handling.

## PROMPT END
