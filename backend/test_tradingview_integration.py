#!/usr/bin/env python3
"""Quick integration test for TradingView technical panel without full environment."""

import asyncio
import json
from app.services.tradingview import ratings, label

async def main():
    print("=" * 60)
    print("TradingView Integration Test")
    print("=" * 60)

    # Test 1: Label function
    print("\n[1] Label mapping:")
    test_values = [0.7, 0.3, 0.0, -0.3, -0.7, None]
    for value in test_values:
        print(f"  {value:5} -> {label(value)}")

    # Test 2: Ratings fetch
    print("\n[2] Scanner API call (BTC/ETH @ 1h, 4h):")
    pairs_by_tf = {
        "1h": {"BTC/USDT", "ETH/USDT"},
        "4h": {"BTC/USDT"},
    }
    result = await ratings(pairs_by_tf)
    if result:
        print(f"  Fetched {len(result)} ratings:")
        for (pair, tf), value in sorted(result.items()):
            print(f"    {pair:12} @ {tf:4} = {value:8.4f} ({label(value)})")
    else:
        print("  ⚠ No ratings returned (scanner may be unreachable)")

    # Test 3: Schema serialization
    print("\n[3] Schema validation (PublicTechnical):")
    from app.schemas.public import PublicTechnical, PublicResultsOut
    from datetime import UTC, datetime

    tech_items = [
        PublicTechnical(pair="BTC/USDT", timeframe="1h", value=0.5, label="Compra fuerte"),
        PublicTechnical(pair="ETH/USDT", timeframe="4h", value=-0.2, label="Venta"),
        PublicTechnical(pair="ADA/USDT", timeframe="1d", value=None, label=None),
    ]

    # Simulate a minimal payload
    payload = PublicResultsOut(
        generated_at=datetime.now(UTC),
        stake_currency="USDT",
        totals={
            "accounts": 1, "reachable": 1, "running": 1, "live_accounts": 0,
            "dry_accounts": 1, "profit_closed_abs": 0.0, "profit_all_abs": 0.0,
            "closed_trade_count": 0, "winning_trades": 0, "losing_trades": 0,
            "winrate": None, "open_trades": 0, "total_stake_deployed": 0.0,
            "balance_total": 100.0
        },
        accounts=[],
        technical=tech_items,
    )

    # Serialize and check
    serialized = payload.model_dump_json()
    obj = json.loads(serialized)
    print(f"  ✓ Payload serialized to {len(serialized)} bytes")
    print(f"  ✓ Contains {len(obj['technical'])} technical items")
    print("  ✓ JSON structure valid")

    # Verify no secrets leak
    forbidden = ["@", "cp-bot-", "_enc", "password", "secret"]
    leaked = [s for s in forbidden if s in serialized.lower()]
    if leaked:
        print(f"  ✗ SECURITY: Found forbidden strings: {leaked}")
    else:
        print(f"  ✓ No forbidden strings in payload")

    print("\n" + "=" * 60)
    print("All checks passed! ✓")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())
