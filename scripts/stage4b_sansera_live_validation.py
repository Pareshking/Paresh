"""Run the real SANSERA Stage-4B packet through the canonical snapshot and judge.

The evidence packet was collected manually from primary/secondary sources on
2026-09-19. This script performs the deterministic execution/validation loop and
writes a machine-generated dossier artifact.
"""

from __future__ import annotations

from pathlib import Path

from agent.company_research import top_candidates
from agent.quant_hand_off import load_quant_snapshot
from agent.research_execution import execute_research, judge_dossier
from agent.sansera_research_packet import CUTOFF, sansera_packet


def main() -> None:
    snapshot = load_quant_snapshot(expected_as_of=CUTOFF)
    candidates = top_candidates(snapshot, limit=25)
    candidate = next((item for item in candidates if item.symbol == "SANSERA"), None)
    if candidate is None:
        raise SystemExit("SANSERA is not present in the canonical Top-25")

    dossier = execute_research(snapshot, candidate, sansera_packet())
    judge_dossier(dossier)

    out = Path("artifacts/stage4b_sansera_dossier.md")
    out.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "# Stage 4B — SANSERA Real Adaptive Execution",
        "",
        f"- Snapshot as-of: {dossier.snapshot_as_of.isoformat()}",
        f"- Symbol: {dossier.candidate.symbol}",
        f"- Rank: {dossier.candidate.rank}",
        f"- Score: {dossier.candidate.score:.6f}",
        f"- Company archetype: {dossier.plan.company_archetype}",
        "",
        "## Economic drivers",
        *[f"- {item}" for item in dossier.plan.economic_drivers],
        "",
        "## Selected material domains",
        *[f"- {item.value}" for item in dossier.plan.material_domains],
        "",
        "## Evidence audit",
        f"- Evidence: {dossier.audit.evidence_count}",
        f"- Primary: {dossier.audit.primary_evidence_count}",
        f"- Secondary: {dossier.audit.secondary_evidence_count}",
        f"- Derived: {dossier.audit.derived_evidence_count}",
        f"- Domains covered: {dossier.audit.domain_count}",
        f"- Primary-source share: {dossier.audit.primary_coverage:.1%}",
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
        (
            "- Single-sourced findings: "
            f"{dossier.audit.causal_findings_single_sourced} causal, "
            f"{dossier.audit.contradictions_single_sourced} contradiction "
            "(every cited evidence item resolves to the same publisher)"
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
        "## Single-sourced domains (item 25 -- reported, not a hard gate)",
        (
            "None detected."
            if not dossier.audit.domains_single_sourced
            else "Every non-DERIVED item in this domain resolves to the same publisher -- flagged for reviewer judgement, not a defect verdict."
        ),
        *[f"- {item}" for item in dossier.audit.domains_single_sourced],
        "",
        "## Evidence log",
    ]
    for evidence in dossier.item.positive_evidence + dossier.item.negative_evidence + dossier.item.unknowns:
        lines.extend(
            [
                f"- [{evidence.kind.value.upper()}] {evidence.domain.value}: {evidence.claim}",
                f"  - Source: {evidence.source}",
                f"  - Source tier: {evidence.source_tier.value}",
                f"  - Event date: {evidence.event_date.isoformat() if evidence.event_date else 'unknown'}",
                f"  - Published: {evidence.published_on.isoformat() if evidence.published_on else 'unknown'}",
                "",
            ]
        )

    lines.extend([
        "## Causal findings",
    ])

    for finding in dossier.causal_findings:
        lines.extend(
            [
                f"### {finding.hypothesis}",
                f"- Finding: {finding.finding}",
                f"- Mechanism: {finding.mechanism}",
                f"- Timing: {finding.timing}",
                f"- Uncertainty: {finding.uncertainty}",
                "",
            ]
        )

    lines.append("## Contradictions")
    for finding in dossier.contradictions:
        lines.extend(
            [
                f"### {finding.hypothesis}",
                f"- Original claim: {finding.original_claim}",
                f"- Counter-evidence: {finding.counter_evidence}",
                f"- Resolution: {finding.resolution}",
                "",
            ]
        )

    lines.extend(
        [
            "## Unresolved questions",
            *[f"- {item}" for item in dossier.unresolved_questions],
            "",
            "## Monitoring questions",
            *[f"- {item}" for item in dossier.monitoring_questions],
            "",
            "## Judge",
            "- STAGE4B_SANSERA_EXECUTION=PASS",
            "- The dossier passed deterministic structural, provenance and coverage validation. This is NOT the same as a full adversarial council review (item 6): it confirms the dossier is well-formed and sourced, not that every claim has been independently attacked and defended.",
            "- This is research intelligence, not an investment recommendation.",
        ]
    )

    out.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"STAGE4B_SANSERA_AS_OF={dossier.snapshot_as_of.isoformat()}")
    print(f"STAGE4B_SANSERA_RANK={dossier.candidate.rank}")
    print(f"STAGE4B_SANSERA_SCORE={dossier.candidate.score}")
    print(f"STAGE4B_SANSERA_EVIDENCE={dossier.audit.evidence_count}")
    print(f"STAGE4B_SANSERA_PRIMARY_COVERAGE={dossier.audit.primary_coverage:.3f}")
    print(f"STAGE4B_SANSERA_CAUSAL={dossier.audit.causal_finding_count}")
    print(f"STAGE4B_SANSERA_CONTRADICTIONS={dossier.audit.contradiction_count}")
    print(f"STAGE4B_SANSERA_EVIDENCE_WINDOW_GAP_DAYS={dossier.evidence_window_gap_days}")
    print(
        "STAGE4B_SANSERA_EVIDENCE_AGE_BUCKETS="
        f"{dossier.audit.evidence_age_within_90d}/"
        f"{dossier.audit.evidence_age_91_to_180d}/"
        f"{dossier.audit.evidence_age_181_to_365d}/"
        f"{dossier.audit.evidence_age_over_365d}/"
        f"{dossier.audit.evidence_age_unanchored}"
    )
    print(
        "STAGE4B_SANSERA_ABSENCE_BASED_FINDINGS="
        f"{dossier.audit.causal_findings_absence_based}/"
        f"{dossier.audit.contradictions_absence_based}"
    )
    print(f"STAGE4B_SANSERA_NUMERIC_DISAGREEMENTS={len(dossier.audit.numeric_disagreements)}")
    for item in dossier.audit.numeric_disagreements:
        print(f"STAGE4B_SANSERA_NUMERIC_DISAGREEMENT_DETAIL={item}")
    print(f"STAGE4B_SANSERA_STALE_EVIDENCE={len(dossier.audit.stale_evidence)}")
    for item in dossier.audit.stale_evidence:
        print(f"STAGE4B_SANSERA_STALE_EVIDENCE_DETAIL={item}")
    print(
        "STAGE4B_SANSERA_STALE_ONLY_FINDINGS="
        f"{dossier.audit.causal_findings_stale_only}/"
        f"{dossier.audit.contradictions_stale_only}"
    )
    print(f"STAGE4B_SANSERA_SINGLE_SOURCED_DOMAINS={len(dossier.audit.domains_single_sourced)}")
    for item in dossier.audit.domains_single_sourced:
        print(f"STAGE4B_SANSERA_SINGLE_SOURCED_DOMAIN_DETAIL={item}")
    print(
        "STAGE4B_SANSERA_SINGLE_SOURCED_FINDINGS="
        f"{dossier.audit.causal_findings_single_sourced}/"
        f"{dossier.audit.contradictions_single_sourced}"
    )
    print("STAGE4B_SANSERA_EXECUTION=PASS")


if __name__ == "__main__":
    main()
