# Data Consistency & Relationship Between Snapshots

## Your Question: "If I add/delete changes to May 2026, will it match today's file?"

### Answer: Not Automatically

The data has a **temporal cascade** relationship:

```
Sep 2019 → Mar 2020 → Sep 2020 → ... → May 2026 → Oct 2, 2026
(oldest)                                 (previous)   (today)
```

Each snapshot is **independent** - it represents what NSE published as the official index composition on that rebalancing date.

## What Happens if You Manually Edit May 2026

If you modify the May 2026 constituent list:
- ✗ It will **NOT** automatically propagate to Oct 2, 2026
- ✓ It will **stay as you edited it** until the next actual NSE rebalancing
- ⚠ If there's no Oct 2 rebalancing circle from NSE, the Oct 2 data might be carry-forward

## How Changes Actually Propagate (NSE's Logic)

NSE rebalancing circulars announce ADDED and REMOVED stocks. The cascade works like:

```
May 2026 Composition: [A, B, C, D, E]
        ↓
NSE Sep 2026 Circular: Add [X], Remove [B]
        ↓
Sep 2026 Composition: [A, C, D, E, X]
        ↓
NSE Oct 2 2026 Circular (if exists): Add [Y], Remove [C]
        ↓
Oct 2026 Composition: [A, D, E, X, Y]
```

## Your Use Case: Manual Edits

If you want to:

### 1. **Fix historical data** (e.g., May 2026 had wrong stocks)
- Edit May 2026 in the CSV
- Manually cascade the changes forward (add/remove based on subsequent circulars)
- Update all later snapshots that depend on it

### 2. **Match today with May 2026**
- Don't edit May 2026
- Instead, apply the actual NSE circulars from Jun-Oct 2026
- Or use the official Oct 2, 2026 snapshot (what we have)

### 3. **Validate consistency**
```python
import pandas as pd

# Load data
df = pd.read_csv('NIFTY_50.csv')

# Get May 2026 and Oct 2 constituents
may = set(df[df['Effective_Date'] == '2026-05-15']['Symbol'])
oct = set(df[df['Effective_Date'] == '2026-10-02']['Symbol'])

# Check what changed
added = oct - may
removed = may - oct

print(f"May 2026: {len(may)} stocks")
print(f"Oct 2, 2026: {len(oct)} stocks")
print(f"Added since May: {added}")
print(f"Removed since May: {removed}")
```

## Key Points

1. **Each snapshot is official** - it comes from NSE's rebalancing circular on that date
2. **Manual edits are manual** - they don't cascade unless you explicitly make them cascade
3. **Latest snapshot (Oct 2, 2026)** = NSE's current official composition for that date
4. **Previous snapshots (May 2026, etc.)** = NSE's official composition as of those dates

## If Data Looks Wrong

**Scenario**: Oct 2 snapshot has 53 stocks instead of 50 for NIFTY Next 50

**Reasons**:
1. NSE includes both old and new tickers during transition period
2. A merger was announced but not yet effective
3. Data extraction had a bug (check source)
4. There's a grace period in the index rules

**Resolution**:
- Check the NSE circular for Oct 2, 2026
- Verify if a stock is marked as "to be removed after X date"
- Check if there's a corporate action in progress

## Recommendation

✓ **Use the data as-is** - it's direct from NSE official sources
✓ **Don't manually edit** unless you find an error and validate against NSE
✓ **Always check source circulars** before making material backtesting decisions
⚠ **For live trading**: Always verify against NSE website directly

