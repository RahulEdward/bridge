"""Full gateway endpoint test."""
import httpx
import time

BASE = "http://localhost:5000"
H = {"X-API-Key": "LvyMwWH8AfRxFTDYQGKBdcoO2JkU7usgeIilpEm3nZq9CXjz"}

print("=== 1. HEALTH ===")
r = httpx.get(f"{BASE}/health")
d = r.json()
print(f"  {r.status_code} | {d['status']} | Active: {d['active_accounts']}")

print("\n=== 2. CONNECT MT5 (Gateway) ===")
r = httpx.post(f"{BASE}/gateway/connect_mt5", headers=H, json={
    "user_id": "test_user_001",
    "login": 12345678,
    "password": "testpass123",
    "server": "ICMarkets-Demo",
    "investor_mode": False
})
print(f"  {r.status_code} | {r.json()}")

time.sleep(1)

print("\n=== 3. STATUS ===")
r = httpx.get(f"{BASE}/gateway/status/test_user_001", headers=H)
d = r.json()
print(f"  {r.status_code} | connection={d['connection']['status']} | engine={d['trading_engine']['is_active']}")

print("\n=== 4. BALANCE ===")
r = httpx.get(f"{BASE}/gateway/balance/test_user_001", headers=H)
print(f"  {r.status_code} | {r.json()}")

print("\n=== 5. START TRADING ===")
r = httpx.post(f"{BASE}/gateway/start_trading", headers=H, json={
    "user_id": "test_user_001",
    "max_positions": 10,
    "max_volume_per_trade": 5.0,
    "max_drawdown_percent": 25.0
})
print(f"  {r.status_code} | {r.json()}")

print("\n=== 6. BUY ===")
r = httpx.post(f"{BASE}/gateway/buy", headers=H, json={
    "user_id": "test_user_001",
    "symbol": "EURUSD",
    "volume": 0.01,
    "sl": 1.0800,
    "tp": 1.0950
})
print(f"  {r.status_code} | {r.json()}")

print("\n=== 7. SELL ===")
r = httpx.post(f"{BASE}/gateway/sell", headers=H, json={
    "user_id": "test_user_001",
    "symbol": "GBPUSD",
    "volume": 0.02
})
print(f"  {r.status_code} | {r.json()}")

print("\n=== 8. POSITIONS ===")
r = httpx.get(f"{BASE}/gateway/positions/test_user_001", headers=H)
d = r.json()
print(f"  {r.status_code} | {len(d['positions'])} positions")

print("\n=== 9. FULL STATUS (after trades) ===")
r = httpx.get(f"{BASE}/gateway/status/test_user_001", headers=H)
d = r.json()
eng = d["trading_engine"]
print(f"  {r.status_code} | trades_executed={eng.get('trades_executed', 0)} | active={eng['is_active']}")

print("\n=== 10. STOP TRADING ===")
r = httpx.post(f"{BASE}/gateway/stop_trading", headers=H, json={
    "user_id": "test_user_001",
    "close_all_positions": False
})
print(f"  {r.status_code} | {r.json()}")

print("\n=== 11. DISCONNECT ===")
r = httpx.post(f"{BASE}/gateway/disconnect/test_user_001", headers=H)
print(f"  {r.status_code} | {r.json()}")

print("\n=== 12. DETAILED HEALTH ===")
r = httpx.get(f"{BASE}/health/detailed", headers=H)
d = r.json()
print(f"  {r.status_code} | Active: {d['active_accounts']} | Total: {d['total_accounts']}")

print("\n=== 13. AUTH TEST (no key) ===")
r = httpx.get(f"{BASE}/gateway/status/test_user_001")
print(f"  {r.status_code} | {r.json()}")

print("\n" + "=" * 50)
print("  ALL GATEWAY TESTS COMPLETE!")
print("=" * 50)
