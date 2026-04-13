import httpx
import time

BASE = "http://localhost:5000"
H = {"X-API-Key": "test-api-key-12345"}

print("=== 1. HEALTH CHECK ===")
r = httpx.get(f"{BASE}/health")
print(f"  Status: {r.status_code} | Active: {r.json()['active_accounts']}")

print("\n=== 2. CREATE ACCOUNT ===")
r = httpx.post(f"{BASE}/account/create", headers=H, json={
    "account_id": "test_001",
    "broker_server": "ICMarkets-Demo",
    "login": 12345678,
    "password": "pass123",
    "investor_mode": False
})
print(f"  Status: {r.status_code} | {r.json()['message']}")
time.sleep(0.5)

print("\n=== 3. ACCOUNT STATUS ===")
r = httpx.get(f"{BASE}/account/status/test_001", headers=H)
print(f"  Status: {r.status_code} | Account: {r.json()['status']}")

print("\n=== 4. ACCOUNT INFO ===")
r = httpx.get(f"{BASE}/account/info/test_001", headers=H)
d = r.json()
print(f"  Status: {r.status_code} | Balance: {d['balance']} | Equity: {d['equity']}")

print("\n=== 5. POSITIONS ===")
r = httpx.get(f"{BASE}/account/positions/test_001", headers=H)
print(f"  Status: {r.status_code} | Count: {len(r.json()['positions'])}")

print("\n=== 6. MARKET CANDLES ===")
r = httpx.get(f"{BASE}/market/candles/test_001?symbol=EURUSD&timeframe=H1&count=5", headers=H)
print(f"  Status: {r.status_code} | Candles: {len(r.json()['candles'])}")

print("\n=== 7. MARKET TICK ===")
r = httpx.get(f"{BASE}/market/ticks/test_001?symbol=EURUSD", headers=H)
d = r.json()
print(f"  Status: {r.status_code} | Bid: {d['tick']['bid']} | Ask: {d['tick']['ask']}")

print("\n=== 8. PLACE TRADE ===")
r = httpx.post(f"{BASE}/trade/place", headers=H, json={
    "account_id": "test_001", "symbol": "EURUSD",
    "order_type": "buy", "volume": 0.1, "sl": 1.08, "tp": 1.095
})
d = r.json()
print(f"  Status: {r.status_code} | Success: {d['success']} | Ticket: {d['order_ticket']}")

print("\n=== 9. MODIFY TRADE ===")
r = httpx.post(f"{BASE}/trade/modify", headers=H, json={
    "account_id": "test_001", "ticket": 987654321, "sl": 1.082, "tp": 1.098
})
print(f"  Status: {r.status_code} | Success: {r.json()['success']}")

print("\n=== 10. CLOSE TRADE ===")
r = httpx.post(f"{BASE}/trade/close", headers=H, json={
    "account_id": "test_001", "ticket": 987654321
})
print(f"  Status: {r.status_code} | Success: {r.json()['success']}")

print("\n=== 11. AUTH TEST (no key) ===")
r = httpx.get(f"{BASE}/account/status/test_001")
print(f"  Status: {r.status_code} | Detail: {r.json()['detail']}")

print("\n=== 12. DETAILED HEALTH ===")
r = httpx.get(f"{BASE}/health/detailed", headers=H)
d = r.json()
print(f"  Status: {r.status_code} | Active: {d['active_accounts']} | Total: {d['total_accounts']}")

print("\n=== 13. STOP ACCOUNT ===")
r = httpx.post(f"{BASE}/account/stop/test_001", headers=H)
print(f"  Status: {r.status_code} | {r.json()['message']}")

print("\n=== 14. RESTART ACCOUNT ===")
r = httpx.post(f"{BASE}/account/restart/test_001", headers=H)
print(f"  Status: {r.status_code} | {r.json()['message']}")

print("\n" + "=" * 40)
print("ALL ENDPOINT TESTS COMPLETE!")
print("=" * 40)
