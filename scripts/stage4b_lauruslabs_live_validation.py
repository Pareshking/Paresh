"""Live canonical-snapshot execution for the LAURUSLABS Stage-4B packet."""
from pathlib import Path

from agent.quant_hand_off import load_quant_snapshot
from agent.company_research import top_candidates
from agent.research_execution import execute_research, judge_dossier
from agent.lauruslabs_research_packet import CUTOFF, lauruslabs_packet

snapshot = load_quant_snapshot(expected_as_of=CUTOFF)
candidate = next((c for c in top_candidates(snapshot, limit=25) if c.symbol == "LAURUSLABS"), None)
if candidate is None:
    raise RuntimeError("LAURUSLABS is not present in the canonical Top-25 snapshot")

dossier = execute_research(snapshot, candidate, lauruslabs_packet())
judge_dossier(dossier)

out = Path("artifacts/stage4b_lauruslabs_dossier.md")
out.parent.mkdir(parents=True, exist_ok=True)
lines = [
    "# Stage-4B Batch-1 Dossier — LAURUSLABS",
    "",
    f"- Snapshot as-of: {dossier.snapshot_as_of.isoformat()}",
    f"- Symbol: {dossier.candidate.symbol}",
    f"- Rank: {dossier.candidate.rank}",
    f"- Score: {dossier.candidate.score:.6f}",
    f"- Archetype: {dossier.plan.company_archetype}",
    f"- Evidence: {dossier.audit.evidence_count}",
    f"- Primary / Secondary / Derived: {dossier.audit.primary_evidence_count} / {dossier.audit.secondary_evidence_count} / {dossier.audit.derived_evidence_count}",
    f"- Domains: {dossier.audit.domain_count}",
    f"- Causal findings: {dossier.audit.causal_finding_count}",
    f"- Contradictions: {dossier.audit.contradiction_count}",
    f"- Unresolved questions: {dossier.audit.unresolved_question_count}",
    f"- Evidence window gap: {dossier.evidence_window_gap_days} days",
    f"- Numeric disagreements: {len(dossier.audit.numeric_disagreements)}",
    f"- Stale evidence: {len(dossier.audit.stale_evidence)}",
    f"- Single-sourced domains: {len(dossier.audit.domains_single_sourced)}",
    "",
    "## Economic drivers",
]
lines.extend(f"- {x}" for x in dossier.plan.economic_drivers)
lines.extend(["", "## Material domains"])
lines.extend(f"- {x.value}" for x in dossier.plan.material_domains)
lines.extend(["", "## Causal findings"])
for f in dossier.causal_findings:
    lines += [f"### {f.hypothesis}", f"- Finding: {f.finding}", f"- Mechanism: {f.mechanism}", f"- Timing: {f.timing}", f"- Uncertainty: {f.uncertainty}", ""]
lines.extend(["## Contradictions"])
for f in dossier.contradictions:
    lines += [f"### {f.hypothesis}", f"- Original: {f.original_claim}", f"- Counter: {f.counter_evidence}", f"- Resolution: {f.resolution}", ""]
lines.extend(["## Unresolved questions"])
lines.extend(f"- {x}" for x in dossier.unresolved_questions)
lines.extend(["", "## Monitoring questions"])
lines.extend(f"- {x}" for x in dossier.monitoring_questions)
lines.extend(["", "STAGE4B_LAURUSLABS_EXECUTION=PASS"])
out.write_text("\n".join(lines), encoding="utf-8")

print(f"STAGE4B_LAURUSLABS_AS_OF={snapshot.as_of.isoformat()}")
print(f"STAGE4B_LAURUSLABS_RANK={candidate.rank}")
print(f"STAGE4B_LAURUSLABS_SCORE={candidate.score:.6f}")
print(f"STAGE4B_LAURUSLABS_EVIDENCE={dossier.audit.evidence_count}")
print(f"STAGE4B_LAURUSLABS_PRIMARY={dossier.audit.primary_evidence_count}")
print(f"STAGE4B_LAURUSLABS_DOMAINS={dossier.audit.domain_count}")
print(f"STAGE4B_LAURUSLABS_CAUSAL={dossier.audit.causal_finding_count}")
print(f"STAGE4B_LAURUSLABS_CONTRADICTIONS={dossier.audit.contradiction_count}")
print(f"STAGE4B_LAURUSLABS_EXECUTION=PASS")
