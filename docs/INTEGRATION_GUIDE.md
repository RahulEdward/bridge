# MT5 Gateway Integration Guide

## Overview

Yeh guide aapko batayega ki apni **FastAPI** ya **Next.js** app ko is MT5 Execution Gateway se kaise connect karein.

---

## Gateway Details

```
Gateway URL : http://<VPS_IP>:5000
API Key     : test-api-key-12345   (production mein change karein)
Header      : X-API-Key: <your-api-key>
```

---

## FastAPI App Integration

### 1. Install Dependencies

```bash
pip install httpx
```

### 2. Gateway Client Service banao

```python
# services/mt5_gateway.py

import httpx
from typing import Optional

GATEWAY_URL = "http://<VPS_IP>:5000"
API_KEY = "test-api-key-12345"

HEADERS = {
    "X-API-Key": API_KEY,
    "Content-Type": "application/json"
}

async def get_account_info(account_id: str) -> dict:
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{GATEWAY_URL}/account/info/{account_id}", headers=HEADERS)
        r.raise_for_status()
        return r.json()

async def get_positions(account_id: str) -> dict:
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{GATEWAY_URL}/account/positions/{account_id}", headers=HEADERS)
        r.raise_for_status()
        return r.json()

async def place_order(account_id: str, symbol: str, order_type: str, volume: float,
                      sl: float = None, tp: float = None) -> dict:
    async with httpx.AsyncClient() as client:
        body = {
            "account_id": account_id,
            "symbol": symbol,
            "order_type": order_type,   # "buy" | "sell" | "buy_limit" | "sell_limit"
            "volume": volume,
            "sl": sl,
            "tp": tp
        }
        r = await client.post(f"{GATEWAY_URL}/trade/place", headers=HEADERS, json=body)
        r.raise_for_status()
        return r.json()

async def close_position(account_id: str, ticket: int) -> dict:
    async with httpx.AsyncClient() as client:
        body = {"account_id": account_id, "ticket": ticket}
        r = await client.post(f"{GATEWAY_URL}/trade/close", headers=HEADERS, json=body)
        r.raise_for_status()
        return r.json()

async def add_account(account_id: str, login: int, password: str, server: str) -> dict:
    async with httpx.AsyncClient() as client:
        body = {
            "account_id": account_id,
            "broker_server": server,
            "login": login,
            "password": password,
            "investor_mode": False
        }
        r = await client.post(f"{GATEWAY_URL}/account/create", headers=HEADERS, json=body)
        r.raise_for_status()
        return r.json()
```

### 3. FastAPI Routes mein use karo

```python
# main.py ya routes/trading.py

from fastapi import APIRouter, HTTPException
from services.mt5_gateway import place_order, get_positions, get_account_info

router = APIRouter(prefix="/trading", tags=["Trading"])

@router.get("/account/{account_id}")
async def account_info(account_id: str):
    try:
        return await get_account_info(account_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/order")
async def create_order(account_id: str, symbol: str, order_type: str, volume: float):
    try:
        return await place_order(account_id, symbol, order_type, volume)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/positions/{account_id}")
async def positions(account_id: str):
    try:
        return await get_positions(account_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

---

## Next.js App Integration

### 1. Environment Variable set karo

```env
# .env.local
NEXT_PUBLIC_GATEWAY_URL=http://<VPS_IP>:5000
GATEWAY_API_KEY=test-api-key-12345
```

### 2. Gateway API utility banao

```typescript
// lib/gateway.ts

const GATEWAY_URL = process.env.NEXT_PUBLIC_GATEWAY_URL
const API_KEY = process.env.GATEWAY_API_KEY

const headers = {
  "X-API-Key": API_KEY!,
  "Content-Type": "application/json",
}

export async function getAccountInfo(accountId: string) {
  const res = await fetch(`${GATEWAY_URL}/account/info/${accountId}`, { headers })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function getPositions(accountId: string) {
  const res = await fetch(`${GATEWAY_URL}/account/positions/${accountId}`, { headers })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function placeOrder(params: {
  account_id: string
  symbol: string
  order_type: "buy" | "sell" | "buy_limit" | "sell_limit" | "buy_stop" | "sell_stop"
  volume: number
  sl?: number
  tp?: number
  price?: number
}) {
  const res = await fetch(`${GATEWAY_URL}/trade/place`, {
    method: "POST",
    headers,
    body: JSON.stringify(params),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function closePosition(accountId: string, ticket: number) {
  const res = await fetch(`${GATEWAY_URL}/trade/close`, {
    method: "POST",
    headers,
    body: JSON.stringify({ account_id: accountId, ticket }),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function addAccount(params: {
  account_id: string
  login: number
  password: string
  broker_server: string
}) {
  const res = await fetch(`${GATEWAY_URL}/account/create`, {
    method: "POST",
    headers,
    body: JSON.stringify({ ...params, investor_mode: false }),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}
```

### 3. Next.js API Route (Server-side — API key safe rahega)

```typescript
// app/api/trading/positions/route.ts

import { getPositions } from "@/lib/gateway"
import { NextRequest, NextResponse } from "next/server"

export async function GET(req: NextRequest) {
  const accountId = req.nextUrl.searchParams.get("account_id")
  if (!accountId) return NextResponse.json({ error: "account_id required" }, { status: 400 })

  try {
    const data = await getPositions(accountId)
    return NextResponse.json(data)
  } catch (e: any) {
    return NextResponse.json({ error: e.message }, { status: 500 })
  }
}
```

```typescript
// app/api/trading/order/route.ts

import { placeOrder } from "@/lib/gateway"
import { NextRequest, NextResponse } from "next/server"

export async function POST(req: NextRequest) {
  try {
    const body = await req.json()
    const result = await placeOrder(body)
    return NextResponse.json(result)
  } catch (e: any) {
    return NextResponse.json({ error: e.message }, { status: 500 })
  }
}
```

### 4. React Component mein use karo

```tsx
// components/TradingPanel.tsx

"use client"
import { useState, useEffect } from "react"

export default function TradingPanel({ accountId }: { accountId: string }) {
  const [positions, setPositions] = useState([])
  const [accountInfo, setAccountInfo] = useState<any>(null)

  useEffect(() => {
    // Positions fetch karo
    fetch(`/api/trading/positions?account_id=${accountId}`)
      .then(r => r.json())
      .then(d => setPositions(d.positions || []))

    // Account info fetch karo
    fetch(`/api/trading/account?account_id=${accountId}`)
      .then(r => r.json())
      .then(setAccountInfo)
  }, [accountId])

  const handleBuy = async () => {
    const res = await fetch("/api/trading/order", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        account_id: accountId,
        symbol: "EURUSD",
        order_type: "buy",
        volume: 0.01,
      }),
    })
    const data = await res.json()
    alert(data.success ? `Order placed! Ticket: ${data.order_ticket}` : `Error: ${data.message}`)
  }

  return (
    <div>
      {accountInfo && (
        <div>
          <p>Balance: {accountInfo.balance} {accountInfo.currency}</p>
          <p>Equity: {accountInfo.equity}</p>
        </div>
      )}
      <button onClick={handleBuy}>Buy EURUSD 0.01</button>
      <h3>Open Positions ({positions.length})</h3>
      {positions.map((p: any) => (
        <div key={p.ticket}>
          {p.symbol} | {p.type} | {p.volume} lots | P&L: {p.profit}
        </div>
      ))}
    </div>
  )
}
```

---

## WebSocket — Real-time Data

```typescript
// hooks/useGatewaySocket.ts

import { useEffect, useRef } from "react"

export function useGatewaySocket(accountId: string, onUpdate: (data: any) => void) {
  const ws = useRef<WebSocket | null>(null)

  useEffect(() => {
    const GATEWAY_URL = process.env.NEXT_PUBLIC_GATEWAY_URL!.replace("http", "ws")
    const API_KEY = process.env.NEXT_PUBLIC_GATEWAY_API_KEY!

    ws.current = new WebSocket(`${GATEWAY_URL}/ws/${accountId}?api_key=${API_KEY}`)

    ws.current.onmessage = (e) => {
      const data = JSON.parse(e.data)
      onUpdate(data)
    }

    ws.current.onopen = () => {
      // Ping bhejo
      ws.current?.send(JSON.stringify({ type: "ping" }))
    }

    return () => ws.current?.close()
  }, [accountId])
}
```

---

## Local Development Setup

Agar aap local machine pe develop kar rahe hain aur VPS pe gateway chal raha hai:

```bash
# Option 1: Direct VPS IP use karo
NEXT_PUBLIC_GATEWAY_URL=http://<VPS_IP>:5000

# Option 2: Agar VPS pe firewall hai to SSH tunnel banao
ssh -L 5000:localhost:5000 Administrator@<VPS_IP>
# Phir local mein:
NEXT_PUBLIC_GATEWAY_URL=http://localhost:5000
```

---

## Available API Endpoints Summary

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/account/create` | Naya MT5 account add karo |
| GET | `/account/status/{id}` | Account connection status |
| GET | `/account/info/{id}` | Balance, equity, margin |
| GET | `/account/positions/{id}` | Open positions |
| GET | `/account/orders/{id}` | Pending orders |
| POST | `/account/restart/{id}` | Account restart karo |
| POST | `/account/stop/{id}` | Account stop karo |
| POST | `/trade/place` | Order place karo |
| POST | `/trade/close` | Position close karo |
| POST | `/trade/modify` | SL/TP modify karo |
| GET | `/market/candles/{id}` | Historical candles |
| GET | `/market/ticks/{id}` | Live tick data |
| WS | `/ws/{id}` | Real-time streaming |
| GET | `/health` | Gateway health check |

---

## Order Types

```
buy        → Market Buy
sell       → Market Sell
buy_limit  → Buy Limit (price se neeche)
sell_limit → Sell Limit (price se upar)
buy_stop   → Buy Stop (price se upar)
sell_stop  → Sell Stop (price se neeche)
```

---

## Error Handling

```typescript
// Gateway se aane wale common errors:
// 401 → API key galat hai
// 404 → Account nahi mila ya connected nahi
// 503 → MT5 terminal connected nahi
// 500 → Internal server error
```
