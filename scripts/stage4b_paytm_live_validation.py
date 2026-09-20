"""Live third-archetype acceptance execution for the adaptive Stage-4B engine."""

from __future__ import annotations

from pathlib import Path

from agent.quant_hand_off import load_quant_snapshot
from agent.company_research import top_candidates
from agent.research_execution import execute_research, judge_dossier
from agent.paytm_research_packet import CUTOFF, paytm_packet

snapshot = load_quant_snapshot(expected_as_of=CUTOFF)
candidate = next((c for c in top_candidates(snapshot, limit=25) if c.symbol == "PAYTM"), None)
if candidate is None:
    raise RuntimeError("PAYTM is not present in the canonical Top-25 snapshot")

dossier = execute_research(snapshot, candidate, paytm_packet())
judge_dossier(dossier)

out = Path("artifacts/stage4b_paytm_dossier.md")
out.parent.mkdir(parents=True, exist_ok=True)
lines = [
    "# Stage-4B Adaptive Third-Archetype Dossier — PAYTM",
    "",
    f"- Snapshot as-of: {dossier.snapshot_as_of.isoformat()}",
    f"- Symbol: {dossier.candidate.symbol}",
    f"- Rank: {dossier.candidate.rank}",
    f"- Score: {dossier.candidate.score:.6f}",
    f"- Company archetype: {dossier.plan.company_archetype}",
    f"- Evidence: {dossier.audit.evidence_count}",
    f"- Primary evidence: {dossier.audit.primary_evidence_count}",
    f"- Secondary evidence: {dossier.audit.secondary_evidence_count}",
    f"- Derived evidence: {dossier.audit.derived_evidence_count}",
    f"- Domains: {dossier.audit.domain_count}",
    f"- Causal findings: {dossier.audit.causal_finding_count}",
    f"- Contradictions: {dossier.audit.contradiction_count}",
    f"- Unresolved questions: {dossier.audit.unresolved_question_count}",
    f"- Evidence window gap: {dossier.evidence_window_gap_days} days (newest evidence vs. snapshot as-of)",
    (
        "- Evidence age: "
        f"<=90d {dossier.audit.evidence_age_within_90d}, "
        f"91-180d {dossier.audit.evidence_age_91_to_180d}, "
        f"181-365d {dossier.audit.evidence_age_181_to_365d}, "
        f">365d {dossier.audit.evidence_age_over_365d}, "
        f"unanchored {dossier.audit.evidence_age_unanchored}"
    ),
    (
        "- Absence-based findings: "
        f"{dossier.audit.causal_findings_absence_based} causal, "
        f"{dossier.audit.contradictions_absence_based} contradiction "
        "(support rests only on \"no disclosure was found\", not on contradicting evidence)"
    ),
    (
        "- Stale-only findings: "
        f"{dossier.audit.causal_findings_stale_only} causal, "
        f"{dossier.audit.contradictions_stale_only} contradiction "
        "(support rests only on evidence past its domain's half-life)"
    ),
    "",
    "## Numeric disagreements (NUMERIC_DISAGREEMENT_REVIEW_REQUIRED)",
    (
        "None detected."
        if not dossier.audit.numeric_disagreements
        else "Not auto-resolved -- flagged for reviewer judgement, not a defect verdict."
    ),
    *[f"- {item}" for item in dossier.audit.numeric_disagreements],
    "",
    "## Stale evidence (item 11/14 -- reported, not a hard gate)",
    (
        "None detected."
        if not dossier.audit.stale_evidence
        else "Past its domain's default or archetype-overridden half-life -- flagged for reviewer judgement, not a defect verdict."
    ),
    *[f"- {item}" for item in dossier.audit.stale_evidence],
    "",
    "## Selected economic drivers",
]
lines.extend(f"- {item}" for item in dossier.plan.economic_drivers)
lines.extend(["", "## Material domains"])
lines.extend(f"- {item.value}" for item in dossier.plan.material_domains)
lines.extend(["", "## Causal findings"])
for finding in dossier.causal_findings:
    lines.extend([
        f"### {finding.hypothesis}",
        f"- Finding: {finding.finding}",
        f"- Mechanism: {finding.mechanism}",
        f"- Timing: {finding.timing}",
        f"- Uncertainty: {finding.uncertainty}",
    ])
lines.extend(["", "## Contradictions"])
for finding in dossier.contradictions:
    lines.extend([
        f"### {finding.hypothesis}",
        f"- Original claim: {finding.original_claim}",
        f"- Counter-evidence: {finding.counter_evidence}",
        f"- Resolution: {finding.resolution}",
    ])
lines.extend(["", "## Unresolved questions"])
lines.extend(f"- {item}" for item in dossier.unresolved_questions)
lines.extend(["", "## Monitoring questions"])
lines.extend(f"- {item}" for item in dossier.monitoring_questions)
lines.extend(["", "## Evidence"])
for evidence in dossier.item.positive_evidence + dossier.item.negative_evidence + dossier.item.unknowns:
    lines.extend([
        f"### {evidence.kind.value.upper()} — {evidence.domain.value}",
        f"- Claim: {evidence.claim}",
        f"- Source tier: {evidence.source_tier.value}",
        f"- Source: {evidence.source}",
        f"- Event date: {evidence.event_date.isoformat() if evidence.event_date else 'unknown'}",
        f"- Hypothesis: {evidence.hypothesis}",
        "",
    ])
lines.append("STAGE4B_PAYTM_EXECUTION=PASS")
out.write_text("\n".join(lines), encoding="utf-8")

print(f"STAGE4B_PAYTM_AS_OF={snapshot.as_of.isoformat()}")
print(f"STAGE4B_PAYTM_RANK={candidate.rank}")
print(f"STAGE4B_PAYTM_SCORE={candidate.score:.6f}")
print(f"STAGE4B_PAYTM_EVIDENCE={dossier.audit.evidence_count}")
print(f"STAGE4B_PAYTM_PRIMARY={dossier.audit.primary_evidence_count}")
print(f"STAGE4B_PAYTM_DOMAINS={dossier.audit.domain_count}")
print(f"STAGE4B_PAYTM_CAUSAL={dossier.audit.causal_finding_count}")
print(f"STAGE4B_PAYTM_CONTRADICTIONS={dossier.audit.contradiction_count}")
print(f"STAGE4B_PAYTM_EVIDENCE_WINDOW_GAP_DAYS={dossier.evidence_window_gap_days}")
print(
    "STAGE4B_PAYTM_EVIDENCE_AGE_BUCKETS="
    f"{dossier.audit.evidence_age_within_90d}/"
    f"{dossier.audit.evidence_age_91_to_180d}/"
    f"{dossier.audit.evidence_age_181_to_365d}/"
    f"{dossier.audit.evidence_age_over_365d}/"
    f"{dossier.audit.evidence_age_unanchored}"
)
print(
    "STAGE4B_PAYTM_ABSENCE_BASED_FINDINGS="
    f"{dossier.audit.causal_findings_absence_based}/"
    f"{dossier.audit.contradictions_absence_based}"
)
print(f"STAGE4B_PAYTM_NUMERIC_DISAGREEMENTS={len(dossier.audit.numeric_disagreements)}")
for item in dossier.audit.numeric_disagreements:
    print(f"STAGE4B_PAYTM_NUMERIC_DISAGREEMENT_DETAIL={item}")
print(f"STAGE4B_PAYTM_STALE_EVIDENCE={len(dossier.audit.stale_evidence)}")
for item in dossier.audit.stale_evidence:
    print(f"STAGE4B_PAYTM_STALE_EVIDENCE_DETAIL={item}")
print(
    "STAGE4B_PAYTM_STALE_ONLY_FINDINGS="
    f"{dossier.audit.causal_findings_stale_only}/"
    f"{dossier.audit.contradictions_stale_only}"
)
print("STAGE4B_PAYTM_EXECUTION=PASS")
