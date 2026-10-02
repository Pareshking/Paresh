# NSE Official Source Verification Plan
## Building Production-Ready Data from Official Announcements

**Strategy:** Reconstruct NSE index constituent data from official NSE press releases and circulars, starting with recent dates (2024-2026) and working backward.

**Target Confidence:** 99.5%+  
**Timeline:** 2-3 weeks for 2024-2026  
**Deliverable:** Verified constituent lists with complete NSE circular audit trail

---

## Phase 1: Recent Data Verification (2024-2026)

### Timeline & Key Dates

```
2026-10-02 (TODAY)
├─ Current constituent snapshot
├─ Get from: NSE website live data
└─ Verify: All 3 indices (NIFTY_MIDCAP_150, SMALLCAP_250, MICROCAP_250)

2024-2025 Verification (Quarterly Rebalancing Pattern)
├─ March rebalancing (typically March 28)
├─ June rebalancing (typically June 28)
├─ September rebalancing (typically Sept 27)
└─ December rebalancing (typically Dec 27)
```

### Data Collection Points

**For Each Date, Collect:**

```
1. Official NSE Circular/Press Release
   - NSE URL or circular number
   - Document type (e.g., "NIFTY Midcap 150 - Composition Change")
   - Download link/archive reference

2. Constituent List
   - Exact member count (expected: 150/250)
   - Complete symbol list
   - Add/delete symbols vs previous date
   - Effective date

3. Corporate Actions (if applicable)
   - Mergers, demergers, delistings
   - Stocks moved from/to other indices
   - Grace periods or special rules applied

4. Methodology Notes
   - Any index rule changes on that date
   - Special exceptions or grace periods
   - Reason for any member count deviations
```

---

## Collection Template

For each verified date, complete this template:

```csv
date,index_id,index_name,verified_count,expected_count,nse_circular,circular_url,source_type,status,notes
2026-10-02,201,NIFTY_MIDCAP_150,150,150,NIFTY-INDEX-2026-10-02,https://...,press_release,verified,"Latest official snapshot"
```

---

## Phase 1 Execution Plan

### Week 1: Most Recent Dates (2025-2026)

**2026-10-02** (TODAY - Priority 1)
- [ ] Go to https://www.nseindia.com/indices
- [ ] Select NIFTY Midcap 150 → View Constituents
- [ ] Record all 150 members
- [ ] Screenshot or PDF save
- [ ] Search NSE press releases for Oct 2 2026 updates
- [ ] Document in verified_constituents_2026_oct02.csv

**2025-12-27** (Q4 2025 Rebalancing)
- [ ] Search NSE: "NIFTY Midcap 150 Composition Change December 2025"
- [ ] Collect circular and constituent list
- [ ] Verify count and members
- [ ] Document

**2025-09-26** (Q3 2025 Rebalancing)
- [ ] Search NSE: "NIFTY Midcap 150 Composition Change September 2025"
- [ ] Verify against expected pattern
- [ ] Document

**2025-06-27** (Q2 2025 Rebalancing)
- [ ] Search NSE press archive
- [ ] Collect and verify
- [ ] Document

**2025-03-28** (Q1 2025 Rebalancing)
- [ ] Search NSE press archive
- [ ] Collect and verify
- [ ] Document

### Week 2: 2024 Full Year Verification

Repeat collection process for all 4 quarterly rebalancings in 2024:
- 2024-12-27
- 2024-09-27
- 2024-06-28
- 2024-03-28 ← **CRITICAL** (the 325-constituent anomaly date)

### Week 3: Validation & Documentation

- [ ] Cross-check all dates against existing dataset
- [ ] Document any discrepancies
- [ ] Identify patterns and anomalies
- [ ] Create audit trail CSV
- [ ] Get sign-off documentation

---

## NSE Resources

### Official NSE Links

**Index Constituents (Current):**
- https://www.nseindia.com/indices
- Navigate to index → View Constituents
- Download option usually available

**Press Releases Archive:**
- https://www.nseindia.com/news/
- Search pattern: "[Index Name] Composition Change [Month Year]"

**Index Methodology:**
- https://www.nseindia.com/products/content/indices/
- Look for PDF methodology documents

**Historical Data (if available):**
- May require registration at NSE data portal
- Contact: NSE data team for historical archives

### Search Patterns

```
For NIFTY Midcap 150:
- "NIFTY Midcap 150 Composition Change March 2024"
- "NIFTY Midcap 150 Rebalancing December 2023"
- "Midcap 150 Index - Composition Update"

For NIFTY Smallcap 250:
- "NIFTY Smallcap 250 Composition Change March 2024"
- "Smallcap 250 Index" + date

For NIFTY Microcap 250:
- "NIFTY Microcap 250 Composition Change"
- "Microcap 250 Index" + date
```

---

## Expected Findings

### 2024-03-28 Investigation (Priority)
The existing data shows **325 constituents** in NIFTY_MICROCAP_250 (+75 from expected 250).

**Questions to Answer:**
1. Is 325 the official NSE count or a data error?
2. If 325 is official, what caused the overage?
   - Merger grace period?
   - Delisting transitions?
   - Index methodology rule?
3. When did it return to 250?

**Verification Plan:**
- [ ] Get official NSE circular for 2024-03-28
- [ ] Confirm exact constituent count
- [ ] Document reason for any overage
- [ ] Verify subsequent snapshots show return to normal

---

## Output Structure

```
nse_verification/
├── verified_data/
│   ├── 2024/
│   │   ├── NIFTY_MIDCAP_150_2024-03-28_verified.csv
│   │   ├── NIFTY_MIDCAP_150_2024-06-28_verified.csv
│   │   ├── NIFTY_MIDCAP_150_2024-09-27_verified.csv
│   │   ├── NIFTY_MIDCAP_150_2024-12-27_verified.csv
│   │   └── [same for SMALLCAP and MICROCAP indices]
│   │
│   └── 2025/
│       └── [same pattern]
│
├── verification_checklist.csv
│   (date | index | count | expected | nse_circular | url | status)
│
├── anomaly_explanations.csv
│   (date | index | anomaly | cause | nse_reference)
│
└── AUDIT_TRAIL.md
    (Complete source documentation for regulatory review)
```

---

## Sign-Off Checklist

After collecting and verifying all 2024-2026 data:

```
✓ All dates have official NSE source references
✓ All constituent counts verified against official data
✓ All anomalies explained with NSE documentation
✓ 100% match rate between verified and official data
✓ Complete audit trail created
✓ Ready for regulatory review
✓ Suitable for production trading systems

CONFIDENCE LEVEL: 99.5%+
STATUS: APPROVED FOR PRODUCTION USE
```

---

## Next Steps

1. **Start with 2026-10-02** (today's date)
   - Get current NSE constituent lists
   - Verify against existing data
   - Document first verified snapshot

2. **Work backward through 2025**
   - 4 quarterly rebalancings
   - ~1-2 hours per quarter
   
3. **Complete 2024 verification**
   - Focus on 2024-03-28 anomaly
   - Verify other 3 quarters

4. **Create regulatory documentation**
   - Audit trail
   - Source references
   - Sign-off forms

---

**Document Version:** 1.0  
**Created:** October 2, 2026  
**Last Updated:** October 2, 2026  
**Status:** Ready for execution
