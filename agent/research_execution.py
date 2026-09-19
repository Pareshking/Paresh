"""Stage-4B adaptive research execution and adversarial compilation.

This module is deliberately deterministic. It does not browse the web, fetch prices,
calculate rankings, or call an external AI API. A research-capable provider supplies
the evidence/analysis packet; this module validates, attacks, reconciles, and compiles
that packet into a publication-gated dossier.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from itertools import combinations
from typing import Iterable

from agent.company_research import (
    ResearchCandidate,
    build_research_items,
    validate_evidence_set,
    validate_research_coverage,
    validate_research_plan,
)
from agent.contracts import (
    Evidence,
    QuantSnapshot,
    ResearchDomain,
    ResearchItem,
    ResearchPlan,
    ResearchItem,
    SourceTier,
)


@dataclass(frozen=True)
class ResearchHypothesis:
    hypothesis: str
    rationale: str
    selected_domains: tuple[ResearchDomain, ...]


@dataclass(frozen=True)
class CausalFinding:
    hypothesis: str
    finding: str
    mechanism: str
    timing: str
    uncertainty: str
    evidence_refs: tuple[str, ...]


@dataclass(frozen=True)
class ContradictionFinding:
    hypothesis: str
    original_claim: str
    counter_evidence: str
    resolution: str
    original_claim_refs: tuple[str, ...]
    counter_evidence_refs: tuple[str, ...]
    """Item 7: a contradiction needs evidence on BOTH sides of the tension it
    claims, not one undifferentiated evidence_refs list. Splitting the field
    makes the two-sided structure auditable and enforced (_validate_contradictions
    requires both non-empty, resolvable, and disjoint), which is the part of
    "genuine disagreement" that is safely checkable without a semantic
    strawman-classifier this pipeline deliberately does not build (see the
    Stage-4B improvement tracker, item 7 loop notes, for why ref-count alone
    was tried and rejected as a proxy: SANSERA's one contradiction Report 1
    called genuinely good cited only 1 ref, and its three weak ones already
    cited >=2)."""

    @property
    def evidence_refs(self) -> tuple[str, ...]:
        """Combined view for generic per-finding consumers (e.g. the
        absence-based-support check in execute_research) that only need
        "every cited ref", not which side it supports."""
        return self.original_claim_refs + self.counter_evidence_refs


@dataclass(frozen=True)
class ResearchProviderPacket:
    plan: ResearchPlan
    evidence: tuple[Evidence, ...]
    causal_findings: tuple[CausalFinding, ...] = ()
    contradictions: tuple[ContradictionFinding, ...] = ()
    unresolved_questions: tuple[str, ...] = ()
    monitoring_questions: tuple[str, ...] = ()


@dataclass(frozen=True)
class ResearchAudit:
    evidence_count: int
    primary_evidence_count: int
    secondary_evidence_count: int
    derived_evidence_count: int
    domain_count: int
    contradiction_count: int
    causal_finding_count: int
    unresolved_question_count: int
    hypothesis_count: int
    hypotheses_with_evidence: int
    hypotheses_with_causal_analysis: int
    hypotheses_challenged: int
    blockers: tuple[str, ...] = ()
    newest_evidence_anchor: date | None = None
    """The latest per-item temporal anchor across all evidence (item 20;
    Report 2 F4). Not the same thing as per-item age (items 11/12): an
    evidence *set* can have every item individually "fresh enough" while the
    set as a whole has not been updated in months. Computed as
    max(published_on) for dated items, falling back to event_date only for
    an item that explicitly declares undated_primary_source=True (it still
    carries a real date, just not a publication date); DERIVED
    absence-of-evidence records never contribute -- they are not
    information, so they should not count as "current" information."""
    evidence_age_within_90d: int = 0
    evidence_age_91_to_180d: int = 0
    evidence_age_181_to_365d: int = 0
    evidence_age_over_365d: int = 0
    evidence_age_unanchored: int = 0
    """Age distribution (item 10), bucketed by the same per-item temporal
    anchor logic used for newest_evidence_anchor, relative to snapshot as-of.
    'unanchored' is a DERIVED item or one with neither published_on nor
    event_date -- distinct from the other buckets, not folded into the
    oldest one, since "no date" and "very old" are different findings."""
    causal_findings_absence_based: int = 0
    contradictions_absence_based: int = 0
    derived_only_domains: tuple[str, ...] = ()
    """Count of causal findings / contradictions whose evidence_refs resolve
    ONLY to DERIVED (absence-of-evidence) items (item 21). Not itself a
    blocker: "no stress test was disclosed" can be a legitimate contradiction
    of "the platform is resilient". But it must be visible that the finding
    rests on an absence rather than on contradicting evidence, per the
    handover's Section 24: "we could not find disclosure" must not silently
    read as "negative evidence"."""
    numeric_disagreements: tuple[str, ...] = ()
    """Item 8: pairs of same-domain evidence whose own headline INR figures
    differ materially while provably describing the same underlying quantity
    (see _numeric_disagreement). Never resolved automatically -- flagged for
    a human reviewer, per Section 23 of the handover."""

    @property
    def primary_coverage(self) -> float:
        if not self.evidence_count:
            return 0.0
        return self.primary_evidence_count / self.evidence_count


@dataclass(frozen=True)
class ResearchDossier:
    snapshot_as_of: date
    candidate: ResearchCandidate
    plan: ResearchPlan
    item: ResearchItem
    causal_findings: tuple[CausalFinding, ...]
    contradictions: tuple[ContradictionFinding, ...]
    unresolved_questions: tuple[str, ...]
    monitoring_questions: tuple[str, ...]
    audit: ResearchAudit

    @property
    def evidence_window_gap_days(self) -> int | None:
        """Days between the newest evidence anchor and the snapshot as-of.

        This is a REPORTED metric, not yet a hard gate (item 20). A universal
        threshold across archetypes would repeat the checklist mistake the
        adaptive-research design exists to avoid: a market-sensitive book and
        a quarterly-cadence manufacturer do not go stale at the same rate.
        None when no evidence item carries any usable temporal anchor.
        """
        anchor = self.audit.newest_evidence_anchor
        if anchor is None:
            return None
        return (self.snapshot_as_of - anchor).days


_INR_VALUE_PATTERN = re.compile(
    r"INR\s+([\d,]+(?:\.\d+)?)(?:\s*-\s*([\d,]+(?:\.\d+)?))?\s*"
    r"(lakh crore|crore|million|billion)",
    re.IGNORECASE,
)
_INR_UNIT_TO_MILLION = {"crore": 10, "million": 1, "billion": 1000, "lakh crore": 100000}
_NUMERIC_DISAGREEMENT_MATERIALITY = 0.10  # 10%


def _extract_inr_million_values(claim: str) -> frozenset[float]:
    """Extract every INR-denominated figure in a claim, normalized to a
    common unit (INR million), from patterns like "INR 44,368 million" or
    "INR 5,500-6,000 million" (both range endpoints). Anchored on the
    literal word "INR" so it only extracts monetary figures this dataset
    actually states this way, not any bare number in the text -- narrow by
    design (item 8; Section 23 of the handover: "start with deterministic
    detection where possible... do not build an overly ambitious NLP
    system")."""
    values: set[float] = set()
    for match in _INR_VALUE_PATTERN.finditer(claim):
        multiplier = _INR_UNIT_TO_MILLION[match.group(3).lower()]
        for group in (match.group(1), match.group(2)):
            if group:
                values.add(round(float(group.replace(",", "")) * multiplier, 3))
    return frozenset(values)


def _numeric_disagreement(claim_a: str, claim_b: str) -> tuple[float, float, float] | None:
    """Return (smaller_headline, larger_headline, pct_difference) if the two
    claims' own maximum extracted figures differ materially AND are provably
    about the same underlying quantity -- the smaller one appears verbatim
    (post-normalization) in the OTHER claim's own extracted values too.

    That linkage requirement is the entire design: matching on shared domain
    alone is not enough (a 2026-09-19 prototype run against both real
    packets found a same-domain, same-sentence false positive -- a claim's
    AUM figure spuriously "disagreeing" with an unrelated net-inflows figure
    quoted two sentences later) and matching on shared keywords is not safe
    either (a bag-of-words check would match "non-ADS order book" to "ADS
    backlog" purely because "non-ADS" tokenizes to include "ADS"). Requiring
    the smaller headline to be an exact, explicit restatement inside the
    other claim is what let the real SANSERA ADS-backlog case (44,368 vs
    57,500 million, a verified 30% gap Report 1 found and the pipeline had
    never caught) pass while producing zero false positives on either real
    packet in that same prototype run. It will miss disagreements stated in
    genuinely independent claims with no shared figure -- that is the
    accepted, stated cost of staying deterministic rather than guessing at
    topic similarity from text.
    """
    values_a = _extract_inr_million_values(claim_a)
    values_b = _extract_inr_million_values(claim_b)
    if not values_a or not values_b:
        return None
    max_a, max_b = max(values_a), max(values_b)
    if abs(max_a - max_b) < 0.01:
        return None
    smaller, larger = (max_a, max_b) if max_a < max_b else (max_b, max_a)
    other_values = values_b if smaller == max_a else values_a
    if not any(abs(smaller - v) < 0.01 for v in other_values):
        return None
    pct = (larger - smaller) / smaller
    if pct < _NUMERIC_DISAGREEMENT_MATERIALITY:
        return None
    return (smaller, larger, pct)


def evidence_ref(evidence: Evidence) -> str:
    """Create a deterministic evidence identity for analytical provenance."""
    return "|".join(
        (
            evidence.entity.strip().upper(),
            evidence.kind.value,
            evidence.domain.value,
            evidence.event_date.isoformat() if evidence.event_date else "",
            evidence.published_on.isoformat() if evidence.published_on else "",
            evidence.source.strip(),
            evidence.claim.strip(),
        )
    )


def _evidence_map(evidence: Iterable[Evidence]) -> dict[str, Evidence]:
    result: dict[str, Evidence] = {}
    for item in evidence:
        key = evidence_ref(item)
        if key in result:
            raise ValueError("duplicate evidence reference")
        result[key] = item
    return result


def _validate_causal_findings(
    plan: ResearchPlan,
    findings: Iterable[CausalFinding],
    evidence_by_ref: dict[str, Evidence],
) -> None:
    allowed = set(plan.hypotheses)
    for finding in findings:
        if finding.hypothesis not in allowed:
            raise ValueError("causal finding references an unknown hypothesis")
        if not finding.finding.strip() or not finding.mechanism.strip():
            raise ValueError("causal finding requires finding and mechanism")
        if not finding.timing.strip() or not finding.uncertainty.strip():
            raise ValueError("causal finding requires timing and uncertainty")
        if isinstance(finding.evidence_refs, str) or not isinstance(finding.evidence_refs, tuple):
            raise ValueError("causal finding evidence_refs must be a tuple[str, ...]")
        if not finding.evidence_refs:
            raise ValueError("causal finding requires evidence provenance")
        for ref in finding.evidence_refs:
            if ref not in evidence_by_ref:
                raise ValueError("causal finding references missing evidence")


def _validate_contradiction_ref_list(refs: object, side: str) -> tuple[str, ...]:
    if isinstance(refs, str) or not isinstance(refs, tuple):
        raise ValueError(f"contradiction {side} must be a tuple[str, ...]")
    if not refs:
        raise ValueError(f"contradiction requires {side} (evidence provenance)")
    return refs


def _validate_contradictions(
    plan: ResearchPlan,
    contradictions: Iterable[ContradictionFinding],
    evidence_by_ref: dict[str, Evidence],
) -> None:
    """Item 7: a contradiction must show evidence on BOTH sides of the
    tension it claims -- at least one ref backing the original_claim, at
    least one backing the counter_evidence, and the two sets disjoint. This
    does not detect every strawman (that needs reading the prose, which this
    deterministic pipeline does not automate -- see the class docstring on
    ContradictionFinding), but it does force the two-sided structure to be
    explicit and auditable rather than one undifferentiated ref list."""
    allowed = set(plan.hypotheses)
    for finding in contradictions:
        if finding.hypothesis not in allowed:
            raise ValueError("contradiction references an unknown hypothesis")
        if not finding.original_claim.strip() or not finding.counter_evidence.strip():
            raise ValueError("contradiction requires original and counter claims")
        if not finding.resolution.strip():
            raise ValueError("contradiction requires a resolution or unresolved statement")

        claim_refs = _validate_contradiction_ref_list(
            finding.original_claim_refs, "original_claim_refs"
        )
        counter_refs = _validate_contradiction_ref_list(
            finding.counter_evidence_refs, "counter_evidence_refs"
        )
        overlap = set(claim_refs) & set(counter_refs)
        if overlap:
            raise ValueError(
                "contradiction cites the same evidence on both sides, which "
                "cannot establish a disagreement: " + ", ".join(sorted(overlap))
            )
        for ref in claim_refs + counter_refs:
            if ref not in evidence_by_ref:
                raise ValueError("contradiction references missing evidence")


def _validate_hypothesis_coverage(
    plan: ResearchPlan,
    evidence: Iterable[Evidence],
    causal_findings: Iterable[CausalFinding],
    unresolved_questions: Iterable[str],
) -> None:
    evidence_by_hypothesis = {item.hypothesis for item in evidence if item.hypothesis.strip()}
    causal_hypotheses = {item.hypothesis for item in causal_findings}
    unresolved = tuple(question.strip() for question in unresolved_questions if question.strip())

    missing = [
        hypothesis
        for hypothesis in plan.hypotheses
        if hypothesis not in evidence_by_hypothesis
        and hypothesis not in causal_hypotheses
        and not any(hypothesis in question for question in unresolved)
    ]
    if missing:
        raise ValueError(
            "research hypotheses lack evidence, causal analysis, or explicit unresolved status: "
            + " | ".join(missing)
        )


def execute_research(
    snapshot: QuantSnapshot,
    candidate: ResearchCandidate,
    packet: ResearchProviderPacket,
) -> ResearchDossier:
    """Validate and compile one real provider research packet into a dossier."""
    if candidate.symbol.strip().upper() != packet.plan.symbol.strip().upper():
        raise ValueError("research plan symbol does not match candidate")

    validate_research_plan(packet.plan)
    if candidate.rank < 1:
        raise ValueError("candidate rank must be positive")

    evidence = tuple(packet.evidence)
    validate_evidence_set((candidate,), evidence, information_cutoff=snapshot.as_of)
    validate_research_coverage(evidence, packet.plan.material_domains)
    evidence_by_ref = _evidence_map(evidence)

    causal = tuple(packet.causal_findings)
    contradictions = tuple(packet.contradictions)
    unresolved = tuple(q.strip() for q in packet.unresolved_questions if q.strip())
    monitoring = tuple(q.strip() for q in packet.monitoring_questions if q.strip())

    _validate_causal_findings(packet.plan, causal, evidence_by_ref)
    _validate_contradictions(packet.plan, contradictions, evidence_by_ref)
    _validate_hypothesis_coverage(packet.plan, evidence, causal, unresolved)

    item = ResearchItem(
        symbol=candidate.symbol,
        rank=candidate.rank,
        quantitative_facts=dict(candidate.quantitative_facts),
        positive_evidence=tuple(e for e in evidence if e.kind.value == "positive"),
        negative_evidence=tuple(e for e in evidence if e.kind.value == "negative"),
        unknowns=tuple(e for e in evidence if e.kind.value == "unknown"),
    )

    evidence_hypotheses = {e.hypothesis for e in evidence if e.hypothesis.strip()}
    causal_hypotheses = {f.hypothesis for f in causal}
    challenged_hypotheses = {f.hypothesis for f in contradictions}

    blockers: list[str] = []
    if not causal:
        blockers.append("no causal analysis")
    if not contradictions:
        blockers.append("no contradiction challenge")
    if not unresolved and not monitoring:
        blockers.append("no unresolved or monitoring questions")

    def _temporal_anchor(evidence_item: Evidence) -> date | None:
        if evidence_item.source_tier is SourceTier.DERIVED:
            return None
        if evidence_item.published_on is not None:
            return evidence_item.published_on
        return evidence_item.event_date

    anchors = [a for e in evidence if (a := _temporal_anchor(e)) is not None]
    newest_anchor = max(anchors) if anchors else None

    age_within_90d = age_91_180d = age_181_365d = age_over_365d = age_unanchored = 0
    for e in evidence:
        anchor = _temporal_anchor(e)
        if anchor is None:
            age_unanchored += 1
            continue
        age_days = (snapshot.as_of - anchor).days
        if age_days <= 90:
            age_within_90d += 1
        elif age_days <= 180:
            age_91_180d += 1
        elif age_days <= 365:
            age_181_365d += 1
        else:
            age_over_365d += 1

    def _is_absence_based(refs: tuple[str, ...]) -> bool:
        cited = [evidence_by_ref[r] for r in refs if r in evidence_by_ref]
        return bool(cited) and all(e.source_tier is SourceTier.DERIVED for e in cited)

    causal_absence_based = sum(1 for f in causal if _is_absence_based(f.evidence_refs))
    contradictions_absence_based = sum(
        1 for f in contradictions if _is_absence_based(f.evidence_refs)
    )

    domains_with_real_evidence = {
        e.domain for e in evidence if e.source_tier is not SourceTier.DERIVED
    }
    domains_with_any_evidence = {e.domain for e in evidence}
    derived_only_domains = tuple(
        sorted(
            d.value
            for d in packet.plan.material_domains
            if d in domains_with_any_evidence and d not in domains_with_real_evidence
        )
    )
    """Item 5: material domains covered ONLY by DERIVED (absence-of-evidence)
    records. Deliberately NOT a hard gate -- see execute_research/Loop 4 notes.
    A domain covered only by "no disclosure was found" is a legitimate,
    honestly-recorded research outcome (Section 24 of the handover; item 21
    applies the same non-punitive logic to individual findings), not
    something to force evidence into or forbid outright. Reported so a
    reviewer can see it, same as evidence_window_gap_days and the age
    buckets."""

    by_domain: dict[ResearchDomain, list[Evidence]] = {}
    for e in evidence:
        by_domain.setdefault(e.domain, []).append(e)
    numeric_disagreements: list[str] = []
    for domain, items in by_domain.items():
        for a, b in combinations(items, 2):
            result = _numeric_disagreement(a.claim, b.claim)
            if result is None:
                continue
            smaller, larger, pct = result
            numeric_disagreements.append(
                f"{domain.value}: {smaller:g} vs {larger:g} INR million "
                f"({pct:.0%} difference) -- {evidence_ref(a)} | {evidence_ref(b)}"
            )
    """Item 8 (Report 1 B1; Section 23 of the handover): NUMERIC_DISAGREEMENT_
    REVIEW_REQUIRED. Deliberately NOT a hard gate and never decides which
    figure is correct -- purely a flag for a human reviewer, per Section 23's
    explicit instruction. See _numeric_disagreement's docstring for why this
    is scoped to exact-value linkage within one domain rather than fuzzy
    topic matching."""

    audit = ResearchAudit(
        evidence_count=len(evidence),
        primary_evidence_count=sum(e.source_tier.value == "primary" for e in evidence),
        secondary_evidence_count=sum(e.source_tier.value == "secondary" for e in evidence),
        derived_evidence_count=sum(e.source_tier.value == "derived" for e in evidence),
        domain_count=len({e.domain for e in evidence}),
        contradiction_count=len(contradictions),
        causal_finding_count=len(causal),
        unresolved_question_count=len(unresolved),
        hypothesis_count=len(packet.plan.hypotheses),
        hypotheses_with_evidence=len(evidence_hypotheses),
        hypotheses_with_causal_analysis=len(causal_hypotheses),
        hypotheses_challenged=len(challenged_hypotheses),
        blockers=tuple(blockers),
        newest_evidence_anchor=newest_anchor,
        evidence_age_within_90d=age_within_90d,
        evidence_age_91_to_180d=age_91_180d,
        evidence_age_181_to_365d=age_181_365d,
        evidence_age_over_365d=age_over_365d,
        evidence_age_unanchored=age_unanchored,
        causal_findings_absence_based=causal_absence_based,
        contradictions_absence_based=contradictions_absence_based,
        derived_only_domains=derived_only_domains,
        numeric_disagreements=tuple(numeric_disagreements),
    )

    return ResearchDossier(
        snapshot_as_of=snapshot.as_of,
        candidate=candidate,
        plan=packet.plan,
        item=item,
        causal_findings=causal,
        contradictions=contradictions,
        unresolved_questions=unresolved,
        monitoring_questions=monitoring,
        audit=audit,
    )


def judge_dossier(dossier: ResearchDossier) -> None:
    """Publication gate: raise on material structural/research-process failures."""
    audit = dossier.audit
    if audit.blockers:
        raise ValueError("research dossier blocked: " + "; ".join(audit.blockers))
    if audit.evidence_count == 0:
        raise ValueError("research dossier has no evidence")
    if audit.hypotheses_with_causal_analysis == 0:
        raise ValueError("research dossier has no causal hypothesis analysis")
    if audit.hypotheses_challenged == 0:
        raise ValueError("research dossier has no contradiction challenge")
    if not dossier.unresolved_questions and not dossier.monitoring_questions:
        raise ValueError("research dossier has no explicit uncertainty or monitoring questions")
