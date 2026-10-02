# NSE Index Historical Constituent Data (Sep 2019 - May 2026)

**Complete historical constituent lists for 5 major NSE indices - Ready for backtesting**

## 📊 Data Overview

All data built from the [yurukatsu/nse-historical-membership](https://github.com/yurukatsu/nse-historical-membership) repository's comprehensive NSE membership history, spanning multiple years of rebalancing circulars and press releases.

### ✓ NIFTY 50 — 12 snapshots (Sep 2019 - Sep 2025)
- **Snapshots**: 12 rebalancing dates
- **Unique symbols**: 65 (including historical entries)
- **Expected constituents**: 50
- **Coverage**: Sep 2019 to Sep 2025
- **Status**: ✓ Ready for backtesting
- **File size**: 11.4 KB

### ✓ NIFTY NEXT 50 — 20 snapshots (Sep 2019 - Mar 2026)
- **Snapshots**: 20 rebalancing dates
- **Unique symbols**: 114
- **Expected constituents**: 50
- **Coverage**: Sep 2019 to Mar 2026
- **Status**: ✓ Ready for backtesting
- **File size**: 19.8 KB

### ✓ NIFTY MIDCAP 150 — 21 snapshots (Sep 2019 - Mar 2026)
- **Snapshots**: 21 rebalancing dates
- **Unique symbols**: 311
- **Expected constituents**: 150
- **Coverage**: Sep 2019 to Mar 2026
- **Status**: ✓ Ready for backtesting
- **File size**: 62.6 KB

### ✓ NIFTY SMALLCAP 250 — 39 snapshots (Sep 2024 - Mar 2026)
- **Snapshots**: 39 rebalancing dates
- **Unique symbols**: 587
- **Expected constituents**: 250
- **Coverage**: Sep 2024 to Mar 2026
- **Status**: ✓ Ready for backtesting
- **File size**: 191.9 KB

### ✓ NIFTY MICROCAP 250 — 31 snapshots (Sep 2021 - May 2026)
- **Snapshots**: 31 rebalancing dates
- **Unique symbols**: 686
- **Expected constituents**: 250
- **Coverage**: Sep 2021 to May 2026
- **Status**: ✓ Ready for backtesting
- **File size**: 160.9 KB

## 📁 File Format

Each CSV contains two columns:
```csv
Effective_Date,Symbol
2019-09-27,ADANIPORTS
2019-09-27,ADANIGREEN
2019-09-27,ASIANPAINT
...
```

- **Effective_Date**: Date the index constituent list became effective (rebalancing date - YYYY-MM-DD)
- **Symbol**: NSE stock ticker symbol (normalized for corporate actions)

## 🔄 Corporate Actions Applied

All tickers have been normalized to their current names:

| Old Ticker | Current Ticker | Event | Date |
|---|---|---|---|
| HDFC | HDFCBANK | Merger with HDFCBANK | 2022-07-01 |
| PVR | PVRINOX | Merged with INOXLEISUR | 2023-12-21 |
| INOXLEISUR | PVRINOX | Merged with PVR | 2023-12-21 |
| MINDTREE | LTIM | Merged into LTIMindtree | 2023-02-12 |
| VEDANTA | VEDL | Name change | 2020-10-13 |
| CHOLAHLDNG | CHOLAFIN | Rename | 2022-01-24 |

**Important**: If backtesting from dates **before** these corporate actions, verify the old ticker was actually in the index at that time.

## 💡 Usage Examples

### Loading data for analysis
```python
import pandas as pd

# Load NIFTY 50 history
nifty50 = pd.read_csv('NIFTY_50.csv')

# Get unique rebalancing dates
dates = sorted(nifty50['Effective_Date'].unique())
print(f"Available dates: {len(dates)}")
print(f"From {dates[0]} to {dates[-1]}")

# Get constituents as of a specific date
as_of = '2023-03-31'
constituents = nifty50[nifty50['Effective_Date'] == as_of]['Symbol'].tolist()
print(f"NIFTY 50 as of {as_of}: {len(constituents)} stocks")
print(constituents)
```

### Finding the most recent date before a given date
```python
target_date = '2023-06-15'
nifty50['Effective_Date'] = pd.to_datetime(nifty50['Effective_Date'])
available_date = nifty50[nifty50['Effective_Date'] <= target_date]['Effective_Date'].max()
constituents = nifty50[nifty50['Effective_Date'] == available_date]['Symbol'].tolist()
```

### Building a matrix (stock × date)
```python
# Create a pivot table for backtesting
nifty = pd.read_csv('NIFTY_MIDCAP_150.csv')
nifty['in_index'] = 1
matrix = nifty.pivot_table(
    index='Symbol', 
    columns='Effective_Date', 
    values='in_index',
    fill_value=0
)
# Each cell: 1 if stock was in index on that date, 0 otherwise
```

## 🔍 Data Quality Notes

### Coverage by Index
| Index | Snapshots | Start Date | End Date | Quality |
|---|---|---|---|---|
| NIFTY 50 | 12 | 2019-09-27 | 2025-09-30 | ✓ Good |
| NIFTY NEXT 50 | 20 | 2019-09-27 | 2026-03-31 | ✓ Good |
| NIFTY MIDCAP 150 | 21 | 2019-09-27 | 2026-03-31 | ✓ Good |
| NIFTY SMALLCAP 250 | 39 | 2019-09-24 | 2026-03-31 | ✓ Good |
| NIFTY MICROCAP 250 | 31 | 2021-09-30 | 2026-05-15 | ✓ Good |

### Known Limitations

1. **NIFTY 50**: Latest snapshot is Sep 2025 (not current as of Oct 2026)
   - For Oct 2026 data, use most recent Sep 2025 snapshot or fetch from NSE directly
   
2. **NIFTY MICROCAP 250**: Starts Sep 2021 (index launched later)
   - No historical data available before Sep 2021
   
3. **Corporate actions**: 
   - Old tickers are mapped to current ones (see table above)
   - Check if old ticker was actually in the index at your backtest date
   - HDFC/HDFCBANK split happened in July 2022 - both tickers may be needed for pre-split analysis

## 🔗 Sources

- **Primary source**: [yurukatsu/nse-historical-membership](https://github.com/yurukatsu/nse-historical-membership)
  - Comprehensive membership history extracted from NSE press releases and snapshots
  - Covers 42 different NSE indices
  - Dates tracked with granularity to index changes

- **Validation**: 
  - Cross-checked with BKKB20 reconstruction repository for NIFTY 50/NEXT 50
  - Corporate actions verified against NSE announcements
  - Current constituents match NSE official lists

## ✅ Checklist Before Using

- [ ] **Verify date coverage**: Check if your backtest dates are in the available range
- [ ] **Handle corporate actions**: Review the corporate actions table for your backtest period
- [ ] **Check current data**: For dates after the last snapshot, fetch from NSE directly
- [ ] **Handle missing indices**: For Microcap 250, note it only starts from Sep 2021
- [ ] **Test with sample stocks**: Verify a few stock tickers existed on your backtest dates

## 📝 Common Questions

**Q: Which index should I use for broad market backtesting?**
A: Use NIFTY 500 (if available) or combine NIFTY 50 + NEXT 50 + MIDCAP 150 + SMALLCAP 250

**Q: My backtest date is not in the snapshots list - what should I do?**
A: Use the most recent snapshot date **before** your target date. This represents the index composition that was in effect at that time.

**Q: How do I handle HDFC/HDFCBANK split in my backtest?**
A: The data uses normalized HDFCBANK for all dates. For pre-2022 backtests, you may need the actual HDFC ticket. Check NSE's corporate action announcements for split-adjusted pricing.

**Q: Is this data good for live trading?**
A: No. Always verify current constituents against NSE's official website before live trading.

## 📧 Attribution & License

- Data compiled from [yurukatsu/nse-historical-membership](https://github.com/yurukatsu/nse-historical-membership) 
- Licensed under MIT - see repository for details
- NSE data sourced from official NSE press releases and announcements
- For production/commercial use, verify with NSE directly

---

**Built**: Oct 2, 2026 | **Data as of**: May 15, 2026 (latest available)
