import httpx

H = {"X-API-Key": "test-api-key-12345"}
BASE = "http://localhost:5000"

print("=== MARKET TICK (EURUSD) ===")
r = httpx.get(f"{BASE}/market/ticks/forex_eur_001?symbol=EURUSD", headers=H)
print(r.json())

print("\n=== MARKET CANDLES (EURUSD H1, 5 bars) ===")
r = httpx.get(f"{BASE}/market/candles/forex_eur_001?symbol=EURUSD&timeframe=H1&count=5", headers=H)
d = r.json()
candles = d["candles"]
print(f"Candles count: {len(candles)}")
for c in candles:
    t = c["time"]
    print(f"  {t} | O:{c['open']} H:{c['high']} L:{c['low']} C:{c['close']}")

print("\n=== PLACE BUY TRADE (EURUSD 0.01 lot) ===")
r = httpx.post(f"{BASE}/trade/place", headers=H, json={
    "account_id": "forex_eur_001",
    "symbol": "EURUSD",
    "order_type": "buy",
    "volume": 0.01,
    "deviation": 20,
    "comment": "Gateway test"
})
print(r.json())

print("\n=== POSITIONS ===")
r = httpx.get(f"{BASE}/account/positions/forex_eur_001", headers=H)
d = r.json()
positions = d["positions"]
print(f"Open positions: {len(positions)}")
for p in positions:
    print(f"  Ticket:{p['ticket']} {p['symbol']} {p['type']} {p['volume']}lot P/L:{p['profit']}")

if positions:
    ticket = positions[0]["ticket"]
    print(f"\n=== CLOSE POSITION (ticket: {ticket}) ===")
    r = httpx.post(f"{BASE}/trade/close", headers=H, json={
        "account_id": "forex_eur_001",
        "ticket": ticket
    })
    print(r.json())

print("\n=== FINAL ACCOUNT INFO ===")
r = httpx.get(f"{BASE}/account/info/forex_eur_001", headers=H)
d = r.json()
print(f"Balance: {d['balance']} | Equity: {d['equity']} | Positions: {d['positions_count']}")

print("\n=== ALL REAL MT5 TESTS COMPLETE ===")
