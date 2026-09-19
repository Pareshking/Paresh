# Stage-3 Live Hierarchy Verification — 2026-09-19

## Purpose

This document records the first **actual live execution** of the Stage-3 Market → Sector → Industry → Peer adapter against the current published production ranking artifact.

This closes the verification gap identified after the original Stage-3 implementation: tests had passed, but the actual Top-25 hierarchy had not previously been executed against the live published artifact.

## Execution evidence

- Workflow: V1 Full Validation
- Workflow run: **#289**
- Stage-3 step: **PASS**
- Snapshot as-of: **2026-09-18**
- Snapshot rows: **750**
- Benchmark: **^CRSLDX**
- Market regime: **MarketRegime.BEARISH**
- Benchmark price: **22840.5508**
- Benchmark 200DMA: **23019.6680**
- Benchmark distance to 200DMA: **-0.7781%**
- Universe: **NIFTY TOTAL MARKET**
- Pipeline: **v4_calendar_periods_cbab8da9**
- Price source: **screener**
- Source artifact: `data-latest/rankings.parquet`
- Taxonomy: **TV Industry (119)**
- Taxonomy rows loaded: **2319**
- Classified live ranking rows: **750**
- Unknown classification rows: **0**

The Stage-3 live step completed successfully before the separate full-universe Yahoo validation failed later in the same workflow.

## Actual Top-25 hierarchy

| Rank | Symbol | Score | TV Sector | TV Industry | Peer count | Top peers by rank |
|---:|---|---:|---|---|---:|---|
| 1 | SHILPAMED | 2.760197 | Health Technology | Pharmaceuticals: Major | 42 | LAURUSLABS, DIVISLAB, GLAND, ALIVUS, NEULANDLAB, IPCALAB, MARKSANS, CORONA, EMCURE, ACUTAAS |
| 2 | WELCORP | 2.716014 | Producer Manufacturing | Industrial Machinery | 27 | GMMPFAUDLR, INOXINDIA, KRN, IONEXCHANG, DYNAMATECH, ELGIEQUIP, MAHSCOOTER, TRITURBINE, KIRLOSBROS, NESCO |
| 3 | LAURUSLABS | 2.563710 | Health Technology | Pharmaceuticals: Major | 42 | SHILPAMED, DIVISLAB, GLAND, ALIVUS, NEULANDLAB, IPCALAB, MARKSANS, CORONA, EMCURE, ACUTAAS |
| 4 | STLTECH | 2.326297 | Technology Services | Information Technology Services | 16 | COFORGE, BBOX, TECHM, PERSISTENT, ZENTEC, HCLTECH, MASTEK, SONATSOFTW, TANLA, CAMS |
| 5 | DIVISLAB | 2.277198 | Health Technology | Pharmaceuticals: Major | 42 | SHILPAMED, LAURUSLABS, GLAND, ALIVUS, NEULANDLAB, IPCALAB, MARKSANS, CORONA, EMCURE, ACUTAAS |
| 6 | DIACABS | 2.230110 | Producer Manufacturing | Electrical Products | 24 | BHEL, QPOWER, TDPOWERSYS, FINCABLES, RRKABEL, KIRLOSENG, VOLTAMP, SIEMENS, ABB, CGPOWER |
| 7 | ANANDRATHI | 2.192162 | Finance | Investment Managers | 9 | PRUDENT, NUVAMA, ICICIAMC, 360ONE, HDFCAMC, CRAMC, UTIAMC, CMSINFO |
| 8 | SANSERA | 2.139645 | Producer Manufacturing | Auto Parts: OEM | 23 | SONACOMS, VARROC, SHRIPISTON, BOSCHLTD, ASKAUTOLTD, PRICOLLTD, MOTHERSON, LUMAXTECH, EXIDEIND, BELRISE |
| 9 | CUPID | 2.105713 | Consumer Non-Durables | Household/Personal Care | 9 | MARICO, COLPAL, JYOTHYLAB, DABUR, HINDUNILVR, GODREJCP, EMAMILTD, GILLETTE |
| 10 | ATHERENERG | 2.071025 | Consumer Durables | Motor Vehicles | 13 | SMLMAH, TVSMOTOR, HYUNDAI, TMCV, EICHERMOT, OLAELEC, HEROMOTOCO, FORCEMOT, M&M, OLECTRA |
| 11 | LENSKART | 2.051989 | Health Technology | Medical Specialties | 2 | POLYMED |
| 12 | GMMPFAUDLR | 1.934447 | Producer Manufacturing | Industrial Machinery | 27 | WELCORP, INOXINDIA, KRN, IONEXCHANG, DYNAMATECH, ELGIEQUIP, MAHSCOOTER, TRITURBINE, KIRLOSBROS, NESCO |
| 13 | SYRMA | 1.901869 | Electronic Technology | Electronic Production Equipment | 7 | AVALON, DATAPATTNS, APOLLO, DIXON, KAYNES, PGEL |
| 14 | AVALON | 1.885958 | Electronic Technology | Electronic Production Equipment | 7 | SYRMA, DATAPATTNS, APOLLO, DIXON, KAYNES, PGEL |
| 15 | WELENT | 1.883340 | Industrial Services | Engineering & Construction | 27 | ACMESOLAR, WABAG, CEMPRO, KPIL, JSWINFRA, ENGINERSIN, LLOYDSENGG, HCC, DBL, LT |
| 16 | SKYGOLD | 1.877212 | Consumer Durables | Other Consumer Specialties | 8 | PCJEWELLER, TITAN, THANGAMAYL, SENCO, VAIBHAVGBL, VIPIND, SAFARI |
| 17 | YATHARTH | 1.852871 | Health Services | Hospital/Nursing Management | 12 | MEDANTA, APOLLOHOSP, PARKHOSPS, RAINBOW, HCG, KIMS, NH, ASTERDM, MAXHEALTH, JLHL |
| 18 | SAILIFE | 1.834899 | Commercial Services | Miscellaneous Commercial Services | 17 | ECLERX, SAGILITY, CONCORDBIO, IKS, AXISCADES, CHOICEIN, CCAVENUE, FSL, RITES, IGIL |
| 19 | GLAND | 1.825983 | Health Technology | Pharmaceuticals: Major | 42 | SHILPAMED, LAURUSLABS, DIVISLAB, ALIVUS, NEULANDLAB, IPCALAB, MARKSANS, CORONA, EMCURE, ACUTAAS |
| 20 | SONACOMS | 1.785196 | Producer Manufacturing | Auto Parts: OEM | 23 | SANSERA, VARROC, SHRIPISTON, BOSCHLTD, ASKAUTOLTD, PRICOLLTD, MOTHERSON, LUMAXTECH, EXIDEIND, BELRISE |
| 21 | RUBICON | 1.783190 | Health Technology | Biotechnology | 3 | AKUMS, ANTHEM |
| 22 | PAYTM | 1.776287 | Finance | Finance/Rental/Leasing | 38 | CGCL, PIRAMALFIN, PNBHOUSING, HOMEFIRST, FIVESTAR, IIFL, LTF, BAJFINANCE, POONAWALLA, CHOLAFIN |
| 23 | WELSPUNLIV | 1.761778 | Consumer Non-Durables | Consumer Sundries | 1 | — |
| 24 | AKUMS | 1.751681 | Health Technology | Biotechnology | 3 | RUBICON, ANTHEM |
| 25 | ENTERO | 1.727708 | Distribution Services | Medical Distributors | 1 | — |

## Assertions recorded by the live verifier

- SNAPSHOT_ROWS=750: PASS
- HIERARCHY_ROWS=750: PASS
- TOP25_ROWS=25: PASS
- DUPLICATE_SYMBOLS=0: PASS
- CLASSIFIED_BY_TV_INDUSTRY_119=750
- UNKNOWN_CLASSIFICATION_ROWS=0
- Peer groups are derived from the full 750-row supplied ranking frame.
- No new ranking calculation or taxonomy was introduced.

## Important interpretation boundary

The peer list above is a **taxonomy membership output**, not a peer-quality judgment. It does not claim that the listed companies are economically equivalent, nor does it rank peers independently of the canonical ranking.

The current live verification uses TradingView Industry (119). NSE Industry and TradingView Sector remain separate selectable taxonomies in the Stage-3 adapter and must not be conflated.

## Separate CI issue

Workflow #289 subsequently failed at the existing `scripts/full_validation.py` Yahoo-backed full-universe check because only **430/750** symbols had a close for 2026-09-17 and the existing finite-score floor is 700. The Stage-3 live hierarchy step itself passed and was not affected by that later failure.

## Permanent gate rule

From this verification onward, Stage-3 cannot be considered fully verified merely because unit/regression tests pass. The gate must include a real execution against the current published ranking artifact, with:

1. actual snapshot as-of and row count;
2. actual taxonomy coverage;
3. actual Top-25 hierarchy;
4. peer membership derived from the full live universe;
5. retained CI evidence.

If live execution cannot be performed, the documentation must explicitly say **NOT VERIFIED** rather than implying that synthetic tests are live evidence.

## Repeat and durable retention — workflow #296

After the first live run, the workflow was repaired so the Stage-3 output is uploaded immediately after the live step and is not lost when a later unrelated QA gate fails.

V1 Full Validation run **#296** repeated the live Stage-3 execution successfully with the same current published snapshot and Top-25 output, then:

- Stage-3 live hierarchy output: **PASS**
- Retain Stage-3 live hierarchy artifact: **PASS**
- Artifact name: `stage3-live-hierarchy`
- Artifact size: **2,418 bytes**
- Artifact SHA-256: `a82d1e7d52f7ea170a522094303f7b102451c9040285af68ebc7ef2e30194fcf`
- Artifact contents verified after download: `stage3_live_hierarchy.md`

The workflow still fails later at the pre-existing full-universe Yahoo validation. That later failure does not invalidate the already-passed Stage-3 live step or its retained artifact.
