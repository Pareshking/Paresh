# Stage 4B — Adaptive Research Execution Engine Plan

Date: 2026-09-19
Branch: agent/stage4b-execution
Status: PLAN — implementation not yet started

## Objective

Turn the proven manual SANSERA research loop into a repeatable execution boundary without introducing a second quantitative engine or pretending that a deterministic Python module can independently browse the web.

Stage 4B must separate:

1. deterministic orchestration/validation;
2. evidence collection by a research-capable agent/runtime;
3. adversarial analysis;
4. dossier compilation.

The first production acceptance run is SANSERA.

## Design principle

The research plan is company-specific. The execution engine must never impose a universal research checklist.

Execution sequence:

**QuantSnapshot → Company Profile → ResearchPlan → targeted evidence collection → evidence validation → causal analysis → contradiction search → defence/reconciliation → reviewer audit → judge gate → dossier**

The material domains, hypotheses and exclusions come from ResearchPlan.

## Agent roles

These are logical roles. They may initially be executed by one capable research model in sequential turns; they do not require separate AI accounts.

### 1. Planner
Creates and validates ResearchPlan:
- company archetype;
- economic drivers;
- material domains;
- hypotheses/questions;
- exclusions.

### 2. Evidence Researcher
Collects underlying primary and secondary evidence only for selected domains/hypotheses.
Every material claim must preserve:
- source;
- source tier;
- event/publication/retrieval dates;
- entity;
- domain;
- materiality;
- confidence.

### 3. Causal Analyst
Converts evidence into company-specific mechanisms:

**event → exposure → mechanism → timing → financial/operational variable → management response → peer/industry context → uncertainty**

It must distinguish sourced facts from analytical inference.

### 4. Challenger / Prosecution
Actively searches for:
- contradictory evidence;
- stale evidence;
- omitted negative information;
- lifecycle changes;
- weaker source alternatives;
- wrong entity/ticker;
- unsupported causal links;
- evidence that invalidates a hypothesis.

### 5. Defence
Tests whether supported claims survive the challenge.
Defence must not delete contradictions or turn unknowns into positives.

### 6. Reviewer
Checks:
- provenance;
- dates/cutoff;
- source tier;
- duplicate claims;
- entity identity;
- selected-domain coverage;
- contradiction handling;
- rank/score immutability;
- unsupported inference.

### 7. Judge
Fails closed when material evidence or review requirements are unmet.
Judge does not produce a buy/sell/hold conclusion.

### 8. Compiler
Produces the finished dossier plus machine-readable coverage metrics and unresolved questions.

## Contracts

Add a dedicated execution layer rather than expanding QuantSnapshot.

Required structures:
- ResearchExecutionRequest
- ResearchHypothesis
- CausalFinding
- ContradictionFinding
- ResearchAudit
- ResearchDossier

The dossier must retain:
- source evidence;
- analytical findings;
- contradictions;
- unknowns;
- monitoring questions;
- coverage metrics;
- quantitative identity.

## Research-provider boundary

The execution engine must not embed an unauthenticated web scraper or a second price/taxonomy engine.

A research provider supplies evidence records. The provider may be:
- the current ChatGPT research process during development;
- a future connected research runtime;
- a future API-backed agent.

The deterministic engine validates whatever provider returns.

## SANSERA acceptance run

The first end-to-end run must:
- start from the canonical SANSERA Top-25 candidate;
- generate a SANSERA-specific ResearchPlan;
- gather underlying primary/secondary evidence;
- cover only material domains;
- perform causal analysis;
- actively seek contradictions;
- reconcile evidence;
- produce a finished dossier;
- preserve explicit unknowns;
- run the full adversarial gate.

A news list is a failure.

## Adaptive second-company gate

Before Stage 4B can close, execute a materially different archetype (for example a bank/NBFC) and demonstrate that its ResearchPlan selects materially different drivers/domains.

## Non-duplication

The execution layer must not:
- calculate rankings;
- fetch prices for ranking;
- create a second taxonomy;
- replace corporate-action ownership;
- assign qualitative investment scores;
- produce target prices or buy/sell/hold recommendations.

## Testing

Unit:
- plan validation;
- evidence-to-hypothesis mapping;
- causal finding provenance;
- contradiction provenance;
- cutoff enforcement;
- duplicate detection;
- dossier compilation;
- rank/score immutability.

Adversarial:
- unsupported causal claim;
- evidence from excluded domain;
- post-cutoff information;
- contradiction ignored;
- missing primary evidence where required;
- unresolved material hypothesis incorrectly marked resolved;
- generic news with no company exposure;
- lifecycle event incorrectly treated as completed.

Integration:
- canonical snapshot → SANSERA request → provider packet → execution → dossier.

## Gate

Stage 4B is not complete merely because the code passes unit tests.

Completion requires:
1. current-head focused CI;
2. full regression;
3. real SANSERA execution;
4. full adversarial council;
5. materially different archetype execution;
6. retained dossiers and provenance;
7. no regression to System-1;
8. explicit VERIFIED/NOT VERIFIED status for every gate.
