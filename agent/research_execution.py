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
