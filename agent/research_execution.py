"""Stage-4B adaptive research execution and adversarial compilation.

This module is deliberately deterministic. It does not browse the web, fetch prices,
calculate rankings, or call an external AI API. A research-capable provider supplies
the evidence/analysis packet; this module validates, attacks, reconciles, and compiles
that packet into a publication-gated dossier.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
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
    evidence_refs: tuple[str, ...]


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


def _validate_contradictions(
    plan: ResearchPlan,
    contradictions: Iterable[ContradictionFinding],
    evidence_by_ref: dict[str, Evidence],
) -> None:
    allowed = set(plan.hypotheses)
    for finding in contradictions:
        if finding.hypothesis not in allowed:
            raise ValueError("contradiction references an unknown hypothesis")
        if not finding.original_claim.strip() or not finding.counter_evidence.strip():
            raise ValueError("contradiction requires original and counter claims")
        if not finding.resolution.strip():
            raise ValueError("contradiction requires a resolution or unresolved statement")
        if isinstance(finding.evidence_refs, str) or not isinstance(finding.evidence_refs, tuple):
            raise ValueError("contradiction evidence_refs must be a tuple[str, ...]")
        if not finding.evidence_refs:
            raise ValueError("contradiction requires evidence provenance")
        for ref in finding.evidence_refs:
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
