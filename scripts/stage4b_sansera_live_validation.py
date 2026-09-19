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
        f"- Score: {dossier.candidate.score}",
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
        "",
        "## Causal findings",
    ]

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
            "- STAGE4B_SAN SERA_EXECUTION=PASS",
            "- The dossier passed structural validation, hypothesis coverage, provenance checks and the adversarial publication gate.",
            "- This is research intelligence, not an investment recommendation.",
        ]
    )

    out.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"STAGE4B_SAN SERA_AS_OF={dossier.snapshot_as_of.isoformat()}")
    print(f"STAGE4B_SAN SERA_RANK={dossier.candidate.rank}")
    print(f"STAGE4B_SAN SERA_SCORE={dossier.candidate.score}")
    print(f"STAGE4B_SAN SERA_EVIDENCE={dossier.audit.evidence_count}")
    print(f"STAGE4B_SAN SERA_PRIMARY_COVERAGE={dossier.audit.primary_coverage:.3f}")
    print(f"STAGE4B_SAN SERA_CAUSAL={dossier.audit.causal_finding_count}")
    print(f"STAGE4B_SAN SERA_CONTRADICTIONS={dossier.audit.contradiction_count}")
    print("STAGE4B_SANSERA_EXECUTION=PASS")


if __name__ == "__main__":
    main()
