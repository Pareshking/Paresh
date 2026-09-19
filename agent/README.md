# Research Agent — Foundation

This directory adds an agent/orchestration layer around the existing Paresh quantitative engine.

## Non-negotiable architecture

The agent is **not** a second ranking engine. It consumes the canonical outputs already produced by `src/engine` and treats those outputs as facts.

The agent may:
- explain quantitative results;
- investigate market, sector, industry and company context;
- collect positive evidence, negative evidence and unknowns;
- challenge its own conclusions;
- produce a weekly research report;
- record provenance and uncertainty.

The agent must not:
- change System-1 formulas;
- silently change benchmark, horizons, weights, universe or portfolio rules;
- manufacture missing data;
- turn qualitative evidence into a hidden numerical score;
- replace backtest results with narrative judgement.

## Staged implementation

1. **Foundation** — contracts, provenance, evidence model and report schema.
2. **Quant adapter** — expose the existing screener/backtest outputs through read-only agent tools.
3. **Market hierarchy** — market → sector → industry → peer context.
4. **Company research** — events, filings, announcements, corporate actions and material news.
5. **Adversarial review** — researcher → challenger → reviewer.
6. **Weekly report** — Top-25 quantitative candidates plus evidence, risks and unknowns.
7. **Historical audit** — measure whether the research process adds useful information without contaminating the ranking.
8. **Automation** — GitHub Actions only after the manual workflow is reproducible and tests are green.

## Provenance rule

Every external claim in an agent report should carry:
- source;
- publication/event date when available;
- retrieval date;
- entity/ticker;
- claim type;
- confidence;
- whether the source is primary or secondary.

The quantitative snapshot should also carry the exact as-of date and model/config fingerprint.

## Current status

Foundation only. No production ranking or portfolio behaviour is changed by these files.
