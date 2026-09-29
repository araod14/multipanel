# TradingView Technical Analysis Panel — Implementation Guide

## Overview

The public results page (`/results`) now displays a **left sidebar panel** with TradingView technical ratings for all pairs being traded by active bots. The panel shows:

- **Unique pairs** across all bots (deduplicated)
- **Per-pair rating** from TradingView scanner API grouped by **timeframe**
- **Color-coded labels**: Compra fuerte, Compra, Neutral, Venta, Venta fuerte
- **Source attribution** and disclaimer

The feature degrades gracefully — if TradingView is unreachable, the page still loads with "No disponible".

### Key Design Decisions

1. **Scanner API** (non-official): `POST https://scanner.tradingview.com/crypto/scan` is not an official API but is what the TradingView web UI uses. It returns numeric ratings ([-1, 1]) that we map to Spanish labels.
2. **Timeframe-aware**: Each pair may appear multiple times if it trades on different timeframes (1h, 4h, 1d, etc.). The backend collects pairs per timeframe and fetches ratings accordingly.
3. **Deduplication**: A pair trading on the same timeframe across multiple bots appears once.
4. **Caching**: Technical ratings cache independently from the main results (TTL: 300s by default) to avoid hammering TradingView.
5. **No bot/user leakage**: The technical list contains only pair, timeframe, value, and label — never a username or container name.
6. **Responsive**: On mobile (<767px), the sidebar collapses to a single column and appears above the summary metrics.

## Architecture

### Backend Changes

#### 1. **Config** (`backend/app/config.py`)
```python
public_technical_ttl: float = 300.0
```
Controls how long technical ratings are cached (independent of results cache).

#### 2. **TradingView Service** (`backend/app/services/tradingview.py`)

**Core functions:**

- `async ratings(pairs_by_timeframe: dict[str, set[str]]) -> dict[tuple[str, str], float|None]`
  - Accepts pairs grouped by timeframe (e.g., `{"1h": {"BTC/USDT", "ETH/USDT"}, "4h": {"BTC/USDT"}}`)
  - Returns `{(pair, timeframe): rating_value}` where value is in [-1, 1]
  - Timeframe-to-column mapping is **fixed and closed** (see `_TIMEFRAME_COLUMN_MAP`)
  - Unknown symbols are silently omitted (TradingView behavior)
  - HTTP errors are caught and logged; returns `{}` on failure

- `label(value: float|None) -> str|None`
  - Maps numeric rating to Spanish label:
    - `>= 0.5` → "Compra fuerte"
    - `>= 0.1` → "Compra"
    - `> -0.1` → "Neutral"
    - `> -0.5` → "Venta"
    - `<= -0.5` → "Venta fuerte"

**Implementation notes:**
- Timeframe mapping is intentionally closed — only supported Freqtrade timeframes map to TradingView columns.
- Default exchange is `CP_DEFAULT_EXCHANGE` (kraken in dev, binance in prod).
- Symbol format: `{EXCHANGE}:{BASEUSDT}` (e.g., `BINANCE:BTCUSDT`).
- Single `httpx.AsyncClient` call batches all symbols and columns.

#### 3. **Public Stats** (`backend/app/services/public_stats.py`)

**New function:**
- `async _collect_technical(accounts) -> list[PublicTechnical]`
  - Called during each collection, after accounts are gathered
  - Extracts unique `(pair, timeframe)` from all accounts (using `whitelist` if available, else `pairs`)
  - Calls `tradingview.ratings()`
  - Returns sorted list of `PublicTechnical` items
  - **Has its own TTL cache** (`_technical_cache`) to avoid hammering TradingView on every request

**Integration:**
- `_collect_uncached()` now calls `_collect_technical()` and adds result to payload under key `"technical"`
- `invalidate()` only clears the main cache; `_invalidate_technical()` is for use if you need to force a fresh TradingView fetch

#### 4. **Schemas** (`backend/app/schemas/public.py`)

**New model:**
```python
class PublicTechnical(BaseModel):
    pair: str
    timeframe: str
    value: float | None
    label: str | None
```

**Updated:**
- `PublicResultsOut.technical: list[PublicTechnical]` (added field)

#### 5. **Smoke Tests** (`backend/smoke_public.py`)

- Extended the field allowlist check to verify technical ratings don't leak secrets.
- Test still ensures all forbidden strings are absent from the entire payload.

### Frontend Changes

#### 1. **Types** (`frontend/src/api/types.ts`)

**New interface:**
```typescript
export interface PublicTechnical {
  pair: string;
  timeframe: string;
  value: number | null;
  label: string | null;
}
```

**Updated:**
- `PublicResults.technical: PublicTechnical[]`

#### 2. **Component** (`frontend/src/components/TechnicalPanel.tsx`)

**Props:**
```typescript
interface TechnicalPanelProps {
  technical: PublicTechnical[];
}
```

**Behavior:**
- Displays "No disponible" if list is empty
- Sorts pairs alphabetically
- Renders each pair + timeframe with color-coded label
- Shows "Fuente: TradingView" and disclaimer at bottom

**Color mapping (via CSS classes):**
- `strong-buy` → green
- `buy` → light green
- `neutral` → gray
- `sell` → light red
- `strong-sell` → red

#### 3. **Page Layout** (`frontend/src/pages/public/ResultsPage.tsx`)

**Structure:**
```
<div className="public-body">
  <aside className="public-aside">
    <div className="card">
      <h3>Val. técnica (TradingView)</h3>
      <TechnicalPanel technical={data.technical} />
    </div>
  </aside>
  <div>
    <!-- main content: summary, table, detail -->
  </div>
</div>
```

**Updates:**
- Wrapped content in `.public-body` (CSS grid: `280px 1fr`)
- Aside is `position: sticky; top: 20px`
- Imported and rendered `TechnicalPanel`

#### 4. **Styles** (`frontend/src/styles.css`)

**New classes:**

- `.public-body`: Two-column grid (280px sidebar + 1fr main)
- `.public-aside`: Sticky left panel
- `.technical-list`: Flex column of items
- `.technical-item`: Pair + label + timeframe row
- `.technical-item .label.*`: Color variants (strong-buy, buy, neutral, sell, strong-sell)
- `.technical-empty`: Centered "No disponible" message
- `.technical-credit`: Footer with source and disclaimer

**Mobile breakpoint** (`@media max-width: 767px`):
- `.public-body` → single column (1fr)
- Aside moves to top with `order: -1`
- Becomes non-sticky

## Testing & Verification

### Unit Test (TradingView Service)

```bash
cd backend
python3 << 'EOF'
import asyncio
from app.services.tradingview import ratings, label

async def test():
    pairs_by_tf = {"1h": {"BTC/USDT", "ETH/USDT"}, "4h": {"BTC/USDT"}}
    result = await ratings(pairs_by_tf)
    for (pair, tf), value in sorted(result.items()):
        print(f"{pair:12} @ {tf:4} = {value:8.4f} ({label(value)})")

asyncio.run(test())
EOF
```

Expected output: 3 ratings (BTC/ETH @ 1h, BTC @ 4h) with labels.

### Integration Test

```bash
cd backend
python3 test_tradingview_integration.py
```

Verifies:
- Label mapping correctness
- Scanner API call works (or degrades gracefully)
- Schema serialization
- No security leaks in payload

### Smoke Test (End-to-End)

```bash
# Terminal 1: start the server
cd backend
CP_BOT_DATA_ROOT=$PWD/_test_bots CP_DEFAULT_EXCHANGE=kraken \
  python3 -m uvicorn app.main:app --port 9000

# Terminal 2: run the test
cd backend
.venv/bin/python smoke_public.py 9000
```

Expected output: `PASS`, with sections for:
- [4] Anonymous access to public/results
- [5] No leaks (checks `technical` field)
- [7] Cache hits (two calls share `generated_at`)
- [+] Rate limit 429 on burst

### Manual Testing

1. **Dev Environment:**
   ```bash
   make clean
   make install
   make env
   make dev-start
   ```
   Open http://localhost:5173/results

2. **Visual Checks:**
   - Sidebar visible on desktop (left of summary)
   - Pairs listed with timeframes (sorted A-Z)
   - Color-coded labels (green/red/gray)
   - "No disponible" when bot is down
   - "Fuente: TradingView" footer

3. **Mobile Responsiveness:**
   - Inspect in Chrome DevTools (iPad size: 768px)
   - Sidebar should be above summary
   - Layout should reflow nicely

4. **Failure Mode:**
   - Block TradingView in DevTools (DevTools → Network → right-click → block domain `scanner.tradingview.com`)
   - Reload page; should show "No disponible" in sidebar
   - Rest of page loads normally (no errors)

5. **Timeframe Accuracy:**
   - Configure bot1 with `timeframe: "1h"` and bot2 with `timeframe: "4h"`
   - Both trade BTC/USDT
   - Results should show BTC/USDT twice: once for 1h, once for 4h

## Deployment Notes

### Production Considerations

- **Exchange**: Set `CP_DEFAULT_EXCHANGE=binance` (or your region-reachable exchange)
- **TTL**: Adjust `CP_PUBLIC_TECHNICAL_TTL` (default 300s = 5 min) based on update frequency desire
- **Security**: TradingView scanner endpoint is non-official. If it changes:
  1. Check if the response shape still matches `{"data": [{"s": "...", "d": [...]}]}`
  2. Update `_TIMEFRAME_COLUMN_MAP` if new columns are needed
  3. Test with a smoke run before deploying

### Monitoring

If you add logging/metrics:
- TradingView calls are logged as `control_plane.tradingview` at WARNING level on failures
- Monitor for repeated HTTP errors (may indicate the scanner endpoint is down)

## Implementation Files Changed

| File | Changes |
|------|---------|
| `backend/app/config.py` | +3 lines (public_technical_ttl setting) |
| `backend/app/schemas/public.py` | +10 lines (PublicTechnical, update PublicResultsOut) |
| `backend/app/services/public_stats.py` | +68 lines (_collect_technical, integration) |
| `backend/app/services/tradingview.py` | **NEW** (140 lines: ratings, label, timeframe mapping) |
| `backend/smoke_public.py` | +6 lines (verify technical field) |
| `backend/test_tradingview_integration.py` | **NEW** (integration test) |
| `frontend/src/api/types.ts` | +8 lines (PublicTechnical, update PublicResults) |
| `frontend/src/components/TechnicalPanel.tsx` | **NEW** (52 lines) |
| `frontend/src/pages/public/ResultsPage.tsx` | +17 lines (layout wrapper, component render) |
| `frontend/src/styles.css` | +93 lines (layout, colors, responsive) |

## Future Enhancements

1. **User settings**: Allow visitors to pick timeframe (1h/4h/1d/1w)
2. **Pair filtering**: Show only pairs in use / all available
3. **Rating history**: Sparkline of rating changes over time
4. **Alerts**: Highlight pairs that flipped from Strong Buy to Sell
5. **Cache invalidation**: Manual refresh button (cost: one TradingView call)

---

**Implemented**: 2026-09-29  
**Commit**: `baf1b4a`
