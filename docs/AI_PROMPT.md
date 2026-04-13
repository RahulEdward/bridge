# AI System Prompt — MT5 Gateway Integration

Copy karo aur AI (Claude, ChatGPT, Cursor, etc.) ko do:

---

## PROMPT START

You are an expert full-stack developer. I have a running **MT5 Execution Gateway** on a VPS that controls MetaTrader 5 trading accounts via REST API.

**Gateway is already running at:** `http://<VPS_IP>:5000`

**Authentication:** Every request needs header `X-API-Key: test-api-key-12345`

---

### Gateway API Reference

**Account Endpoints:**
- `GET /account/info/{account_id}` → balance, equity, margin, currency, leverage
- `GET /account/positions/{account_id}` → open positions list
- `GET /account/orders/{account_id}` → pending orders list
- `GET /account/status/{account_id}` → connection status
- `POST /account/create` → add new MT5 account
  ```json
  { "account_id": "string", "broker_server": "string", "login": 123, "password": "string", "investor_mode": false }
  ```
- `POST /account/restart/{account_id}` → restart account
- `POST /account/stop/{account_id}` → stop account

**Trading Endpoints:**
- `POST /trade/place` → place order
  ```json
  { "account_id": "string", "symbol": "EURUSD", "order_type": "buy", "volume": 0.01, "sl": null, "tp": null, "price": null }
  ```
  order_type values: `buy`, `sell`, `buy_limit`, `sell_limit`, `buy_stop`, `sell_stop`

- `POST /trade/close` → close position
  ```json
  { "account_id": "string", "ticket": 123456789 }
  ```

- `POST /trade/modify` → modify SL/TP
  ```json
  { "account_id": "string", "ticket": 123456789, "sl": 1.08, "tp": 1.10 }
  ```

**Market Data:**
- `GET /market/candles/{account_id}?symbol=EURUSD&timeframe=H1&count=100`
- `GET /market/ticks/{account_id}?symbol=EURUSD`

**WebSocket:**
- `ws://<VPS_IP>:5000/ws/{account_id}?api_key=test-api-key-12345`
- Server sends: `{ "type": "account_update", "data": { "balance": 0, "equity": 0, "positions_count": 0 } }`
- Client can send: `{ "type": "ping" }`, `{ "type": "get_positions" }`, `{ "type": "subscribe_tick", "symbol": "EURUSD" }`

**Health:**
- `GET /health` → no auth needed

---

### My App Stack

[FILL IN: e.g. "Next.js 14 with App Router and TypeScript" OR "FastAPI with Python"]

### What I want you to do

[FILL IN: e.g. "Integrate this gateway into my existing Next.js app. Create:
1. A gateway client utility file
2. Server-side API routes for all trading operations
3. A dashboard page showing account balance and open positions
4. A trade form to place buy/sell orders
5. Real-time balance updates via WebSocket"]

### My existing code structure

[PASTE YOUR PROJECT STRUCTURE HERE]

### Important rules
- Keep API key server-side only (never expose in client/browser)
- Use environment variables: `GATEWAY_URL` and `GATEWAY_API_KEY`
- Handle errors properly with user-friendly messages
- All gateway calls should go through Next.js API routes (not directly from browser)

## PROMPT END
