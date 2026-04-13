import httpx
import asyncio

H = {"X-API-Key": "test-api-key-12345"}
BASE = "http://localhost:5000"


async def place_order(account_id, symbol, order_type, volume):
    async with httpx.AsyncClient() as client:
        r = await client.post(f"{BASE}/trade/place", headers=H, json={
            "account_id": account_id,
            "symbol": symbol,
            "order_type": order_type,
            "volume": volume,
            "deviation": 20,
            "comment": "Simultaneous test",
        }, timeout=30)
        return account_id, r.json()


async def main():
    print("=== PLACING ORDERS ON BOTH ACCOUNTS SIMULTANEOUSLY ===\n")

    # Fire both orders at the same time
    results = await asyncio.gather(
        place_order("forex_eur_001", "EURUSD", "buy", 0.01),
        place_order("ramu_singh_001", "EURUSD", "buy", 0.01),
    )

    for account_id, result in results:
        status = "OK" if result.get("success") else "FAIL"
        ticket = result.get("order_ticket", "-")
        msg = result.get("message", "")
        print(f"  [{status}] {account_id}: ticket={ticket} | {msg}")

    # Check positions on both
    print("\n=== POSITIONS ===\n")
    async with httpx.AsyncClient() as client:
        for acc in ["forex_eur_001", "ramu_singh_001"]:
            r = await client.get(f"{BASE}/account/positions/{acc}", headers=H)
            d = r.json()
            positions = d["positions"]
            print(f"  {acc}: {len(positions)} position(s)")
            for p in positions:
                print(f"    ticket={p['ticket']} {p['symbol']} {p['type']} {p['volume']}lot profit={p['profit']}")

    print("\n=== DONE ===")


asyncio.run(main())
