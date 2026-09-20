# Paresh Research-Agent Roadmap (Stages 1-8)

**Status:** Stages 1-4 built and real. Stages 5-8 are a proposed
continuation, not a locked specification -- recorded here so the
architectural context survives beyond chat, per Paresh's explicit
instruction (2026-09-20) that Stage 4 was never intended as the system's
final destination.

**Revision history:**
- 2026-09-20 (initial): recorded a 9-stage split (5 Comparative, 6
  Monitoring, 7 Thesis, 8 Portfolio, 9 Learning), with a "Sequencing
  assessment" section flagging that 5/8 and 6/7 looked likely to collapse
  into fewer stages once built.
- 2026-09-20 (revision): Paresh had a second AI review that same split and
  argued for exactly that collapse, plus a new "portfolio/user
  intelligence" stage not previously identified. Checked against the
  actual repo before accepting: two of the three arguments (5+8 merge,
  6+7 merge) independently match what this doc's own prior sequencing
  section already said, so this is confirmation more than reversal. One
  factual correction found (`HierarchyRow` carries more scoping fields
  than previously documented here) and one real open question found (no
  portfolio/holdings concept exists in the codebase at all) -- both noted
  below. Renumbered 9 stages down to 8 on that basis.

**Caveat, stated by Paresh when this was first recorded:** the exact
post-Stage-4 stages below are the logical continuation of the architecture
already being built, not an already-approved locked design. Treat this as
the proposed next roadmap. Paresh also noted some of it may turn out to be
unnecessary given the quality already reached in Stage 4 -- this is not a
commitment to build all of it as specified.

## The full picture

```
SYSTEM-1
Canonical quantitative engine
        |
        v
Stage 1 -- Foundation / Contracts
        |
Stage 2 -- Canonical Quantitative Hand-off
        |
Stage 3 -- Market Hierarchy / Context
        |
Stage 4 -- Adaptive Company Research
        |
        v
Stage 5 -- Persistent Research State & Continuous Monitoring
        |
Stage 6 -- Cross-Company / Market Intelligence
        |
Stage 7 -- Portfolio / User Research Intelligence
        |
Stage 8 -- Research Feedback / Learning Loop
```

Stage 4 is the point where Paresh moves from being primarily a
quantitative ranking system toward becoming a quant + evidence-based
research intelligence system -- it is a foundation, not an end-state.

## Stages 1-4: built, real, confirmed against the actual codebase

These names are not aspirational relabeling -- they are the terminology
already used in the code's own module docstrings, confirmed by direct
inspection on 2026-09-20:

- **Stage 1 -- Foundation / Contracts**: `agent/contracts.py`. Deliberately
  contains no ranking mathematics; defines the boundary between
  deterministic quantitative facts and qualitative research.
- **Stage 2 -- Canonical Quantitative Hand-off**: `agent/quant_hand_off.py`
  ("Stage-2 read-only hand-off from the canonical ranking artifact").
- **Stage 3 -- Market Hierarchy / Context**: `agent/market_hierarchy.py`
  ("Stage 3 does not own market calculations or taxonomy. It accepts
  outputs already produced by Paresh canonical loaders/engines and makes
  their identity explicit"). `HierarchyRow` already carries, per symbol:
  `sector`, `industry`, `peer_taxonomy`, and `peer_group: tuple[str, ...]`
  (the full same-taxonomy peer list from the canonical ranking frame,
  under a selectable taxonomy: NSE Industry, TV Industry (119), or TV
  Sector (20)). This is more scoping granularity than this doc originally
  credited it with (it previously mentioned only `peer_group`) -- Stage 3
  already has the primitives for peer, industry, *and* sector scoping, all
  currently unused by Stage 4.
- **Stage 4 -- Adaptive Company Research**: everything tracked in
  `agent/STAGE_4B_IMPROVEMENT_TRACKER.md` -- company-specific research
  planning, adaptive domains, hypotheses, evidence collection, provenance,
  causal reasoning, contradiction detection, unresolved/monitoring
  questions, and (as of Loop 14) a formal adversarial-council review.
  Answers: "given this quantitative signal, what is actually happening
  with this company, why does it matter, and what evidence supports or
  contradicts that interpretation?" Five real archetypes live as of
  2026-09-20 (SANSERA, ANANDRATHI, PAYTM, YATHARTH, LENSKART) out of the
  Top-25 universe, deliberately chosen to span very different economic
  models (industrial/auto engineering, wealth management, fintech,
  hospitals, retail) -- enough to prove the adaptive architecture, not
  enough for meaningful same-taxonomy peer comparison yet. The "4B" naming
  in the tracker suggests an earlier "4A" phase (likely the initial
  contracts/execution scaffolding) preceded this session's work; not
  otherwise resolved here.

## Stage 5 -- Persistent Research State & Continuous Monitoring

Merges what earlier versions of this doc called "Stage 6 (Continuous
Monitoring)" and "Stage 7 (Thesis / Research State Tracking)" into one
stage, because they are the same event: new evidence arriving *is* the
input, and updating each affected hypothesis's confidence/state *is* the
interpretation of that event. Splitting detection from interpretation
into separate stages was an artificial boundary once a persistent store
exists to hold both.

Builds, per company: a persistent record of `research_plan`, hypotheses,
evidence, causal findings, contradictions, unresolved/monitoring
questions, last-researched cutoff, and a tracked confidence/state history
per hypothesis (not just the current dossier snapshot). The weekly loop
becomes delta research against the last cutoff, not a full re-run:
fetch only new/relevant information, judge materiality, and only then
challenge existing hypotheses and update the persisted state.

Must also handle Top-25 roster churn: full initial research for a new
entrant, incremental research for an existing name, archival (not
deletion) for a dropout, and reconciliation against prior state on
re-entry.

**This is the same gap already identified and discussed as "Loop 13 /
V1.1"** in `agent/STAGE_4B_IMPROVEMENT_TRACKER.md` -- incremental weekly
research, a persistent per-company evidence store, and an "unattended
API-driven agent loop" using Cloudflare R2 for storage (Paresh's
decisions, 2026-09-20). V1.1 is not a side-track from this roadmap; it is
Stage 5, under a different name, already deferred until V1 is ready per
Paresh's explicit instruction. No further design work has been done here
pending that.

**This stage is the real bottleneck for everything below it.** Stage 6's
value depends on having enough companies researched to compare, and
manually building Top-25 x weekly-research forever is not viable -- so
production capacity here, not comparative-engine design, is what actually
gates the rest of the roadmap.

## Stage 6 -- Cross-Company / Market Intelligence

Merges what earlier versions of this doc called "Stage 5 (Comparative /
Peer Intelligence)" and "Stage 8 (Portfolio / Market-Level Intelligence)"
into one stage: once persistent per-company research state exists, peer
comparison, industry aggregation, sector aggregation, and universe-wide
aggregation are the same underlying engine running at different scopes,
not different systems. Same mechanism, wider net each time:

```
Company -> Peer Group -> Industry -> Sector -> Universe
```

This is more than ranked peer comparison. Because the underlying state is
evidence and hypotheses (not just numbers), the same engine can also
surface things ranking alone cannot:
- a shared external event (e.g. a tariff change) hitting several
  companies through different transmission mechanisms and with different
  financial consequences;
- a shared hypothesis (e.g. "China+1 creates incremental opportunity")
  where some companies merely discuss it and others show actual capacity,
  qualification, or orders against it;
- contradiction clusters -- the same kind of management-optimism-vs-
  evidence conflict recurring across multiple companies in a sector;
- unresolved-question concentration -- which sectors carry the most
  unresolved risk across the researched universe.

**Must use Stage 3's existing scoping fields** (`peer_group`, `industry`,
`sector`, `peer_taxonomy`), not a new ranking engine, and must never
modify System-1's ranking methodology -- this carries forward the hard
boundary the original "Stage 8" framing stated explicitly, and it must
survive the merge into this stage's name, not get diluted by it.

**Practical gating factor**: needs multiple members of the same
peer/industry/sector group actually researched under Stage 5's persistent
state to be meaningful. Today's five archetypes were deliberately chosen
to span different economic models to prove Stage 4's adaptive design, so
they have little same-taxonomy overlap to compare yet -- breadth within
archetypes (more auto/industrial names alongside SANSERA, more hospital
names alongside YATHARTH, etc.) is what unlocks this stage's value, and
that breadth is itself gated by Stage 5's production-capacity problem, not
by this stage's own design.

## Stage 7 -- Portfolio / User Research Intelligence

Connects System-1's quantitative signal, Stage 4's company research state,
and Stage 6's cross-company intelligence to the user's own actual
positions, rather than just the system's own Top-25 output. Concretely:
surfacing which held names had a material research-state change in a
given cycle (a previously unresolved question resolved, a new
contradiction, a hypothesis's confidence shifting), not a second
recommendation engine.

**Resolved, 2026-09-20 (Paresh):** "portfolio" here means the system's own
Top-25 ranked output, not a separate set of real holdings input by the
user. This closes the open data-model question raised when this stage was
first proposed -- there is still no "portfolio" concept in the codebase
today (checked directly), but this stage does not need to invent one: it
can key off the same Top-25 roster Stage 4/5/6 already track, rather than
a new user-input concept.

Must inform the user, never silently feed back into or modify System-1's
ranking -- same boundary as Stage 6.

## Stage 8 -- Research Feedback / Learning Loop

Compares what the research predicted/flagged against what subsequently
happened -- which evidence was useful, which hypotheses were wrong, which
research domains mattered -- to improve future research planning:

```
What the research predicted/flagged
              ->
What subsequently happened
              ->
Which evidence was useful?
              ->
Which hypotheses were wrong?
              ->
Which research domains mattered?
              ->
Improve future research planning
              (prioritisation, hypothesis generation,
               evidence selection, contradiction detection,
               monitoring questions, archetype research profiles)
```

**Must improve the research process, not silently optimise the
quantitative ranking** until a separately defined methodology change is
approved -- same boundary again. Needs Stages 5-7 to have run for real
research cycles first to have anything to learn from; this is correctly
the last stage in sequence, not something to build early.

## Sequencing assessment (Claude's honest take, 2026-09-20, revised)

Stage 5 (persistent state + monitoring) is the genuine prerequisite that
unlocks everything after it -- already true in the original 9-stage
version of this doc and unchanged by the revision. What changed: the
9-stage split understated how much Stage 6 (cross-company) and the old
Stage 8 (portfolio/market) shared the same engine, and how artificial the
detection/interpretation boundary was between the old Stage 6/7. Both are
now collapsed above. The new Stage 7 (portfolio/user intelligence) is a
genuinely useful addition this doc did not previously identify; its
data-model question (what "portfolio" means here) is now resolved --
Paresh confirmed it is the system's own Top-25 output, not separate
user-input holdings. Nothing here is being built now; recorded for
continuity only, and Stage 5/V1.1 stays parked
until Paresh says V1 is ready, per standing instruction.
