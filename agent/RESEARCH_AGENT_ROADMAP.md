# Paresh Research-Agent Roadmap (Stages 1-9)

**Status:** Stages 1-4 built and real. Stages 5-9 are a proposed
continuation, not a locked specification -- recorded here so the
architectural context survives beyond chat, per Paresh's explicit
instruction (2026-09-20) that Stage 4 was never intended as the system's
final destination.

**Caveat, stated by Paresh at the same time this was recorded:** the exact
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
Stage 5 -- Comparative / Peer Intelligence
        |
Stage 6 -- Continuous Monitoring / Change Detection
        |
Stage 7 -- Living Thesis / Research State Tracking
        |
Stage 8 -- Portfolio / Market-Level Intelligence
        |
Stage 9 -- Research Feedback / Learning Loop
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
  their identity explicit"). Already computes, per symbol,
  `HierarchyRow.peer_group: tuple[str, ...]` -- the full same-taxonomy
  peer list from the canonical ranking frame. This is Stage 5's
  foundation, already built and currently unused by Stage 4.
- **Stage 4 -- Adaptive Company Research**: everything tracked in
  `agent/STAGE_4B_IMPROVEMENT_TRACKER.md` -- company-specific research
  planning, adaptive domains, hypotheses, evidence collection, provenance,
  causal reasoning, contradiction detection, unresolved/monitoring
  questions, and (as of Loop 14) a formal adversarial-council review.
  Answers: "given this quantitative signal, what is actually happening
  with this company, why does it matter, and what evidence supports or
  contradicts that interpretation?" Five real archetypes live as of
  2026-09-20 (SANSERA, ANANDRATHI, PAYTM, YATHARTH, LENSKART) out of the
  Top-25 universe. The "4B" naming in the tracker suggests an earlier "4A"
  phase (likely the initial contracts/execution scaffolding) preceded this
  session's work; not otherwise resolved here.

## Stage 5 -- Comparative / Peer Intelligence

Moves from "what is happening to this company?" to "how does this company
compare with its peers and the broader industry?" -- common industry
driver vs. company-specific driver, peer divergence, relative
opportunity/risk, competitor evidence, industry-wide vs. company-specific
developments, whether a company's quantitative strength is supported by
its fundamentals/research context.

**Must use the existing peer hierarchy** (`HierarchyRow.peer_group` from
Stage 3), not a new ranking engine -- consistent with the hard boundary
Stage 1-4 already enforce ("no ranking mathematics").

**Practical gating factor**: peer comparison needs multiple members of the
same peer group actually researched. With only 5 of 25 Top-25 names
covered today, spread across different archetypes/industries, there is
limited real peer overlap yet to compare. Stage 5's value scales with
Stage 4's coverage breadth.

## Stage 6 -- Continuous Monitoring / Change Detection

Moves from periodic research to "what has changed since the last research
cycle?" -- tracking new filings, results, management commentary, orders,
regulatory changes, industry developments, contradictions that have been
resolved, previously unresolved questions, and changes in
research-plan relevance. The core idea is **delta research**, not
regenerating the entire dossier every cycle.

**This is the same gap already identified and discussed as "Loop 13 / V1.1"**
in `agent/STAGE_4B_IMPROVEMENT_TRACKER.md` -- incremental weekly research,
a persistent per-company evidence store, and an "unattended API-driven
agent loop" using Cloudflare R2 for storage (Paresh's decisions,
2026-09-20). V1.1 is not a side-track from this roadmap; it is Stage 6,
under a different name, already deferred until V1 is ready per Paresh's
explicit instruction. No further design work has been done here pending
that.

## Stage 7 -- Thesis / Research State Tracking

Turns the research dossier from a static report into a living research
state per hypothesis:

```
Hypothesis
    -> Supporting evidence
    -> Contradicting evidence
    -> Current confidence/uncertainty
    -> What would confirm it?
    -> What would invalidate it?
    -> Next monitoring trigger
```

**Partially foreshadowed today**: every Stage-4 dossier already has
`unresolved_questions` and `monitoring_questions` fields, and Loop 14's
`ResearchAudit.stale_evidence`/half-life tracking (items 11/12/14) gives a
per-item freshness signal. None of this yet persists across research
cycles into a tracked confidence trend -- that requires Stage 6's
persistent state to exist first. Stage 6 and 7 look like they could be one
engineering effort (a shared persisted-state model) rather than two fully
separate builds, since a change-detection record and a thesis-state update
are naturally the same event.

## Stage 8 -- Portfolio / Market-Level Intelligence

Only after company-level research is mature: reason across the
portfolio/universe -- multiple highly-ranked companies exposed to the same
external risk, sector-wide developments affecting many candidates, whether
a market regime is producing common fundamental effects, clusters of
unresolved risks/opportunities.

```
Quantitative ranking
       +
Company research
       +
Industry context
       +
Peer divergence
       ->
Market/portfolio research intelligence
```

**Must inform System-1, never silently modify its ranking methodology** --
same hard boundary already enforced throughout Stage 1-4. Likely leans
heavily on Stage 5's peer-comparison primitives rather than being a wholly
separate clustering/ranking engine; may turn out to be "Stage 5 aggregated
across the whole universe" rather than a fully distinct capability. Needs
most of the Top-25 covered to be meaningful, not just 5 names.

## Stage 9 -- Research Feedback / Learning Loop

Compares what the research predicted/flagged against what subsequently
happened -- which evidence was useful, which hypotheses were wrong, which
research domains mattered -- to improve future research planning.

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
```

**Must improve the research process, not silently optimise the
quantitative ranking** until a separately defined methodology change is
approved -- same boundary again. Needs Stages 6-8 to have run for real
research cycles first to have anything to learn from; this is correctly
the last stage in sequence, not something to build early.

## Sequencing assessment (Claude's honest take, 2026-09-20)

The 5-9 sequencing is sound and nothing in it reads as premature
over-engineering *if pursued in order* -- but right now, with 5 of 25
Top-25 names covered and no persistent incremental-research
infrastructure, Stages 5 and 8 don't have much real data to work with yet
(peer/portfolio comparison needs breadth of coverage Stage 4 alone hasn't
reached), and Stages 7 and 9 need Stage 6's persisted state to exist
before they have anything to track or learn from. This means Stage 6 (=
V1.1, already deferred) is the genuine prerequisite unlocking the rest,
not a parallel or optional track -- consistent with Paresh's own decision
to park it until V1 is ready. Nothing here is being built now; recorded
for continuity only.
