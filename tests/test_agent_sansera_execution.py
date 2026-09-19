"""Executable acceptance test for the SANSERA Stage-4B packet.

Mirrors tests/test_agent_anandrathi_execution.py. The ANANDRATHI archetype
originally shipped with only a declarative (`_plan`) test and no test that
actually executed `_packet()` through `execute_research` -- which is exactly
how a broken evidence packet (refs[16] IndexError, then a missing material
domain) passed 1138+ green tests. SANSERA had the same gap: no test in this
suite called `sansera_packet()` at all. This closes it symmetrically.

See agent/STAGE_4B_IMPROVEMENT_TRACKER.md item 17 (E4) and Report 0 (S1).
"""
from datetime import date

from agent.company_research import ResearchCandidate
from agent.contracts import QuantSnapshot
from agent.research_execution import evidence_ref, execute_research
from agent.sansera_research_packet import CUTOFF, sansera_packet


def _snapshot():
    return QuantSnapshot(
        as_of=CUTOFF,
        benchmark="^CRSLDX",
        universe="NIFTY TOTAL MARKET",
        model="system-1",
        config_fingerprint="test",
        rows=(
            {"Symbol": "SANSERA", "Rank": 8, "Score": 2.139645},
        ),
    )


def test_sansera_packet_is_executable():
    """As of 2026-09-19, this is expected to FAIL.

    Three SANSERA evidence items (Bharat Forge AR, ACMA about-us page,
    Sansera's own FY2024-25 annual report) are tiered PRIMARY with no
    published_on, per improvement-tracker item 1 (A1). This test is meant to
    stay red until those three items get a real, verifiable publication date
    or an explicit, documented tier change -- not until this assertion is
    loosened or the item is skipped. A green unit-test suite is not
    sufficient if the real executable path is broken; a known-red executable
    test that names the exact defect is more honest than a suite that cannot
    see the defect at all.
    """
    packet = sansera_packet()
    dossier = execute_research(
        _snapshot(),
        ResearchCandidate(
            "SANSERA",
            8,
            2.139645,
            {"Symbol": "SANSERA", "Rank": 8, "Score": 2.139645},
        ),
        packet,
    )
    assert dossier.audit.evidence_count == 33
    assert dossier.audit.causal_finding_count == 5
    assert dossier.audit.contradiction_count == 4


# No test asserts "every SANSERA evidence item is cited by a finding" the way
# the ANANDRATHI test does. Measuring it directly: 17 of 33 SANSERA items
# (52%) are not referenced by any causal finding or contradiction -- e.g. the
# litigation settlement, the AGM disclosure, several peer-comparison and
# regulatory items. Unlike ANANDRATHI's single unused homepage citation, this
# is not obviously padding: SANSERA's plan declares 17 material domains
# (vs. ANANDRATHI's 6), and validate_research_coverage only requires a domain
# to have SOME evidence, not evidence tied to a specific finding. Applying
# ANANDRATHI's strict rule here would either be a false-positive test or would
# force 17 items into causal/contradiction refs they may not genuinely support
# -- exactly what improvement-tracker item 18 (E5) and the handover's Section
# 11 warn against ("do NOT blindly force it into a causal finding just to
# satisfy a test"). Resolving this needs the supporting-vs-background-evidence
# distinction item 18 already calls for, which is still TODO. Left unasserted
# here rather than decided unilaterally.
