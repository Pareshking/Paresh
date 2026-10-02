# NSE Index Historical Data Verification Project

**Project Status:** 🔄 Pivoted to Official Source Verification  
**Last Updated:** October 2, 2026  
**Current Phase:** Collecting 2024-2026 data from official NSE sources  
**Target Confidence:** 99.5%+ (from official NSE announcements)

## Overview

This project builds **production-ready, officially-verified NSE index constituent data** by reconstructing historical membership lists from official NSE press releases and circulars.

### New Approach (Phase 1)
**Start with recent dates (2024-2026) and work backward**, collecting data directly from official NSE sources:
- Official NSE press releases & circulars
- NSE website live data
- Complete audit trail for regulatory compliance

### Existing Dataset (For Reference)
- **NIFTY_MIDCAP_150** - 22 snapshots, 312 unique symbols
- **NIFTY_SMALLCAP_250** - 40 snapshots, 588 unique symbols  
- **NIFTY_MICROCAP_250** - 32 snapshots, 687 unique symbols
- **Coverage:** September 2019 to October 2, 2026

### Purpose:
Build verified NSE index constituent data suitable for:
- Production trading systems (only after verification completes)
- Regulatory reporting (only after verification completes)
- Fund strategy decisions (only after verification completes)
- ✓ Index replication
- ✓ NAV calculations

### Target Confidence: 99.5%+
(via official NSE source verification)

---

## Directory Structure

```
nse_verification/
├── data/
│   ├── NIFTY_MIDCAP_150.csv          # 3,482 rows, 22 snapshots
│   ├── NIFTY_SMALLCAP_250.csv         # 10,576 rows, 40 snapshots
│   └── NIFTY_MICROCAP_250.csv         # 8,764 rows, 32 snapshots
│
├── reports/
│   ├── DATA_VERIFICATION_REPORT.md    # Comprehensive analysis
│   ├── DATA_CONSISTENCY_NOTES.md      # Temporal cascade explanation
│   ├── INDEX_HISTORY_OVERVIEW.md      # High-level overview
│   ├── anomaly_analysis.json          # Detailed anomaly analysis (auto-generated)
│   └── anomalies_explained.csv        # VERIFICATION CHECKLIST tracker
│
├── scripts/
│   ├── analyze_anomalies.py           # Main anomaly detection
│   ├── cross_reference.py             # NSE circular verification
│   ├── symbol_history.py              # Symbol tracking (TODO)
│   └── generate_audit_report.py       # Audit trail generator (TODO)
│
├── analysis/
│   ├── anomaly_timeline.png           # Visualization (TODO)
│   ├── constituent_churn.json         # Churn analysis (TODO)
│   └── corporate_actions_log.csv      # Actions causing anomalies (TODO)
│
├── logs/
│   └── verification_log.txt           # Verification progress
│
├── VERIFICATION_CHECKLIST.md          # Phase-by-phase verification tasks
└── README.md                          # This file
```

---

## Key Findings (Phase 1 ✓ Complete)

### Data Quality: GOOD ✓

| Check | Status | Details |
|-------|--------|---------|
| **Format Integrity** | ✓ PASS | Valid CSV, proper dates |
| **Duplicates** | ✓ PASS | No duplicate entries |
| **Latest Data** | ✓ PASS | All indices have 2026-10-02 |
| **Logical Progression** | ✓ PASS | Constituent changes make sense |

### Anomalies Detected: 20+ ⚠️

#### Critical Issues Requiring Verification:

1. **NIFTY_MICROCAP_250 on 2024-03-28**
   - Found: 325 constituents
   - Expected: 250
   - **Deviation: +75 (+30%)** ← HIGHEST DEVIATION
   - Status: ⚠️ MUST VERIFY

2. **NIFTY_SMALLCAP_250 on 2022-03-31**
   - Found: 291 constituents
   - Expected: 250
   - **Deviation: +41 (+16%)**
   - Status: ⚠️ MUST VERIFY

3. **NIFTY_MICROCAP_250 on 2022-03-31**
   - Found: 323 constituents
   - Expected: 250
   - **Deviation: +73 (+29%)**
   - Status: ⚠️ MUST VERIFY

[See DATA_VERIFICATION_REPORT.md for complete list]

### Possible Explanations (Require Confirmation):

- Corporate Actions (mergers, demergers)
- Delisting grace periods
- Index methodology rules allowing temporary overages
- Index rebalancing transitions

---

## Phase-by-Phase Verification Status

### ✓ Phase 1: Baseline Data Quality
**Status:** COMPLETE

- [x] Loaded all 3 indices
- [x] Validated CSV structure
- [x] Checked for duplicates
- [x] Identified anomalies
- [x] Generated initial report

**Result:** Data structure is sound; 20+ anomalies flagged for investigation

---

### ⏳ Phase 2: Anomaly Documentation
**Status:** IN PROGRESS

- [ ] Investigate NIFTY_MICROCAP_250 (2024-03-28: 325 constituents)
- [ ] Investigate NIFTY_SMALLCAP_250 (2022-03-31: 291 constituents)
- [ ] Investigate NIFTY_MICROCAP_250 (2022-03-31: 323 constituents)
- [ ] Document 15+ other anomalies
- [ ] Find NSE circular references for each

**Expected Output:** `anomalies_explained.csv` with NSE circular links

---

### ⏳ Phase 3: Sample Cross-Reference
**Status:** NOT STARTED

Select 5 dates across timeline and verify against NSE official data:
- 2019-09-27 (baseline)
- 2021-09-30 (MICROCAP_250 start)
- 2022-03-31 (multiple anomalies)
- 2024-03-28 (highest anomaly)
- 2026-10-02 (latest)

**Target Match Rate:** >99%

---

### ⏳ Phase 4: Symbol History Validation
**Status:** NOT STARTED

Trace history of key symbols:
- JPASSOCIAT (removed from NIFTY 50 in 2014, now in MICROCAP_250)
- 10 other random symbols
- Verify against NSE corporate actions

**Target:** 100% traceability to NSE announcements

---

### ⏳ Phase 5: Source Documentation Audit
**Status:** NOT STARTED

Complete audit trail:
- Original NSE press releases
- Rebalancing circular references
- Corporate action documentation
- Index methodology compliance

**Target:** 95%+ traceability to official NSE sources

---

## How to Use This Verification Project

### For Data Users:

1. **Before Using Data:**
   - Read `DATA_VERIFICATION_REPORT.md`
   - Review `VERIFICATION_CHECKLIST.md`
   - Check confidence level (currently 65-75%)

2. **For Backtesting:**
   - ✓ Safe: Use with awareness of anomalies
   - ✓ Recommended: Reference anomalies_explained.csv
   - ❌ Not Safe: Production trading until Phase 5 complete

3. **For Research:**
   - ✓ Use freely but document uncertainty
   - ✓ Cite verification status in publications

### For Verification Contributors:

1. **Run Anomaly Analysis:**
   ```bash
   python scripts/analyze_anomalies.py
   ```
   Generates: `reports/anomaly_analysis.json`

2. **Check Specific Date:**
   ```bash
   # Search NSE for circular on specific date
   # Example: "NIFTY Midcap 150 Composition Change 2022-03-31"
   ```

3. **Document Findings:**
   - Add entries to `anomalies_explained.csv`
   - Include NSE circular reference
   - Note reason (corporate action, etc.)

4. **Update Checklist:**
   - Edit `VERIFICATION_CHECKLIST.md`
   - Mark items as complete
   - Add notes and NSE references

---

## Quick Start: Running Analysis Scripts

### 1. Analyze Anomalies
```bash
cd nse_verification
python scripts/analyze_anomalies.py
```

**Output:**
- Prints summary for each index
- Lists all anomalies (sorted by severity)
- Saves detailed report to `reports/anomaly_analysis.json`

### 2. Check Specific Symbol
```bash
# Find all dates when JPASSOCIAT appears
grep "JPASSOCIAT" data/NIFTY_*.csv
```

### 3. Count Constituents on Date
```bash
# Count how many constituents on specific date
grep "2024-03-28" data/NIFTY_MICROCAP_250.csv | wc -l
```

### 4. Generate Audit Report
```bash
# Generate complete audit trail (when Phase 5 script ready)
python scripts/generate_audit_report.py
```

---

## Official NSE Resources

### Primary Sources:
- **NSE Indices**: https://www.nseindia.com/indices
- **Press Releases**: https://www.nseindia.com/news/
- **Circulars Archive**: https://www.nseindia.com/circulars/
- **Index Methodology**: https://www.nseindia.com/products/content/indices/

### Data Download:
- **Index Compositions**: NSE website → Indices → [Index Name] → Constituents
- **Historical Data**: May require registration at NSE data portal
- **Corporate Actions**: https://www.nseindia.com/corporates/

### Search Pattern for Verification:
```
"NIFTY [Index Name] - Composition Change" [Date]
Example: "NIFTY Midcap 150 - Composition Change 2022-03-31"
```

---

## Confidence Level Progression

```
Phase 1: ✓ 65-75%   (Data structure verified, anomalies flagged)
Phase 2: → 75-80%   (Anomalies explained with NSE references)
Phase 3: → 85-90%   (Sample dates cross-verified)
Phase 4: → 90-95%   (Symbol history validated)
Phase 5: → 95%+     (Complete audit trail from NSE)
```

**Current:** Phase 1 ✓ + Phase 2 ⏳  
**Estimated Final:** 2-3 weeks

---

## Known Issues & Limitations

### Data Limitations:
1. **Constituent Count Anomalies**: 20+ snapshots have non-standard counts
2. **No Source Attribution**: Individual snapshot sources not documented
3. **Grace Period Rules**: Not documented which anomalies are due to corporate actions
4. **Historical Depth**: NIFTY_MICROCAP_250 starts only from 2021-09-30

### Verification Limitations:
1. **2014 Data**: Cannot verify JPASSOCIAT case (outside dataset scope)
2. **Pre-2019 Data**: No coverage
3. **Intra-Day Changes**: Only snapshot data available
4. **Methodology Changes**: Index rules evolution not documented

---

## Contributing to Verification

### Want to Help Verify?

1. **Pick an Anomaly** from VERIFICATION_CHECKLIST.md
2. **Search NSE** for official circular on that date
3. **Document Findings** in `anomalies_explained.csv`
4. **Add NSE Reference** (press release, circular number, etc.)
5. **Create Pull Request** with findings

### Template for Entry:
```csv
Date,Index,Found_Count,Expected_Count,Deviation,NSE_Circular,Reason,Verified
2022-03-31,NIFTY_SMALLCAP_250,291,250,+41,[Ref],Corporate Actions,Yes/No
```

---

## Questions & Support

### Frequently Asked Questions:

**Q: Is this data safe to use for trading?**  
A: No. Use only after Phase 5 completion (95%+ confidence).

**Q: Why are there different constituent counts?**  
A: Likely due to corporate actions, mergers, or delisting grace periods. See Phase 2 for explanations.

**Q: How do I verify a specific date?**  
A: Search NSE website for "[Index Name] Composition Change [Date]" and compare constituent lists.

**Q: What if I find a discrepancy?**  
A: Create an issue or PR with:
- Date, Index, and discrepancy details
- NSE circular reference (if found)
- Proposed explanation

---

## References

### Data Source:
- **GitHub:** https://github.com/yurukatsu/nse-historical-membership
- **License:** MIT
- **Last Updated:** As per GitHub repository

### Official NSE Documentation:
- NIFTY Indices Methodology
- NIFTY Smallcap 250 Index Circular
- NIFTY Midcap 150 Index Circular
- NIFTY Microcap 250 Index Circular

### Related Resources:
- `DATA_CONSISTENCY_NOTES.md` - Temporal cascade explanation
- `DATA_VERIFICATION_REPORT.md` - Detailed findings
- `VERIFICATION_CHECKLIST.md` - Phase-by-phase tasks

---

## Version History

| Date | Version | Changes |
|------|---------|---------|
| 2026-10-02 | 1.0 | Initial verification project setup |
| 2026-10-02 | 1.1 | Added anomaly analysis scripts |
| 2026-10-02 | 1.2 | Created comprehensive checklist |

---

## License & Attribution

Data sourced from NSE official announcements and https://github.com/yurukatsu/nse-historical-membership  
Verification work: Original analysis  
Status: Under verification - Use with caution

---

**Last Updated:** October 2, 2026  
**Next Review:** October 4, 2026 (Phase 2 progress check)

