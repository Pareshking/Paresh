"""No banned synonym in src/ui's string literals (S173 (d)).

The banned words are the "Not" column of docs/GLOSSARY.md (and PAGE_DESIGN.md §3a rule 6), written as
patterns in tests/banned_synonyms.json, one place. Every string literal under src/ui is scanned (docstrings,
and CSS or HTML comments inside a literal, are not page text and are skipped).

What is there today is allow-listed in the same file, each entry with its row in
docs/archive/S173_LABEL_AUDIT_2026-11-24.md: most are data keys (the ranking frame's "Industry" column,
"Max DD 3M", "% 50 EMA") that a page never prints, a few are allowed uses (the "pts" explainer, the volume's
"20-day average"), and the rest are the audit's open mismatches, waiting for the owner (S173 (c)). An entry is
matched by file, rule and the words around the hit, not by line, so edits elsewhere in a file do not break it.

The test fails on any occurrence beyond those: a new label, sentence or key with a banned word. Fix the
wording to the glossary's word, or, for a data key or an allowed use, add an allow entry with its audit row.
The rendered pages are checked separately by scripts/glossary_audit.mjs (in CI); this test is the source-side
guard that catches a label before a page is drawn.
"""

from __future__ import annotations

import ast
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "tests" / "banned_synonyms.json"
AUDIT = ROOT / "docs" / "archive" / "S173_LABEL_AUDIT_2026-11-24.md"
CONTEXT = 25          # characters each side of a hit that identify it in the allow list
_COMMENT = re.compile(r"/\*.*?\*/|<!--.*?-->", re.S)


def load_spec() -> dict:
    return json.loads(SPEC.read_text(encoding="utf-8"))


def _rules(spec: dict) -> list[tuple[dict, re.Pattern]]:
    return [(r, re.compile(r["pattern"], re.I if "i" in r.get("flags", "") else 0),
             re.compile(r["unless_before"]) if r.get("unless_before") else None) for r in spec["rules"]]


def _docstring_ids(tree: ast.AST) -> set[int]:
    ids = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
                ids.add(id(first.value))
    return ids


def scan_source(text: str, rel: str, spec: dict) -> list[dict]:
    """Every banned-word hit in one file's string literals: file, line, rule, context."""
    tree = ast.parse(text)
    skip = _docstring_ids(tree)
    rules = _rules(spec)
    hits = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Constant) and isinstance(node.value, str)) or id(node) in skip:
            continue
        lit = re.sub(r"\s+", " ", _COMMENT.sub(" ", node.value))
        for rule, rx, unless in rules:
            for m in rx.finditer(lit):
                if unless is not None and unless.search(lit[:m.start()]):
                    continue    # e.g. "the market" after the index is named in the same literal (glossary 1)
                hits.append({"file": rel, "line": node.lineno, "rule": rule["id"],
                             "context": lit[max(0, m.start() - CONTEXT):m.end() + CONTEXT].strip()})
    return hits


def scan_ui(spec: dict) -> list[dict]:
    hits = []
    for path in sorted((ROOT / "src" / "ui").rglob("*.py")):
        hits += scan_source(path.read_text(encoding="utf-8"), path.relative_to(ROOT).as_posix(), spec)
    return hits


def _key(h: dict) -> tuple[str, str, str]:
    return h["file"], h["rule"], h["context"]


def new_occurrences(hits: list[dict], spec: dict) -> list[dict]:
    """Hits beyond the allow list's count for their (file, rule, context)."""
    allowed = Counter()
    for a in spec["allow"]:
        allowed[_key(a)] += int(a.get("count", 1))
    seen = Counter()
    out = []
    for h in sorted(hits, key=lambda h: (h["file"], h["line"])):
        seen[_key(h)] += 1
        if seen[_key(h)] > allowed[_key(h)]:
            out.append(h)
    return out


def test_no_new_banned_synonym_in_src_ui():
    spec = load_spec()
    write = {r["id"]: r["write"] for r in spec["rules"]}
    new = new_occurrences(scan_ui(spec), spec)
    assert not new, (
        "Banned synonym in src/ui (docs/GLOSSARY.md). Use the glossary's word, or, for a data key or an "
        "allowed use, add an entry to tests/banned_synonyms.json with its audit row:\n"
        + "\n".join(f"  {h['file']}:{h['line']} [{h['rule']}] ...{h['context']}...  -> write: {write[h['rule']]}\n"
                    f"    {json.dumps({k: h[k] for k in ('file', 'rule', 'context')}, ensure_ascii=False)}"
                    for h in new))


def test_every_allow_entry_names_an_audit_row_and_a_reason():
    spec = load_spec()
    audit = AUDIT.read_text(encoding="utf-8")
    rule_ids = {r["id"] for r in spec["rules"]}
    for a in spec["allow"]:
        assert a["rule"] in rule_ids, a
        assert spec["rows"].get(a.get("audit")), f"no reason for audit row {a.get('audit')} in 'rows': {a}"
        assert a.get("audit") and f"| {a['audit']} |" in audit, f"audit row {a.get('audit')} not in {AUDIT.name}: {a}"
        assert (ROOT / a["file"]).is_file(), a


def test_every_rule_points_at_a_glossary_entry():
    spec = load_spec()
    glossary = (ROOT / "docs" / "GLOSSARY.md").read_text(encoding="utf-8")
    entries = set(re.findall(r"^\| (\d+) \|", glossary, re.M))
    for r in spec["rules"]:
        assert str(r["glossary"]) in entries, r
        assert r["write"], r


def test_a_new_banned_word_is_caught():
    """Negative control: a new label with a banned word fails, the glossary's word passes."""
    spec = load_spec()
    bad = ('HEAD = "12-month return"\nNOTE = f"Max DD {3}M"\nX = "<th>Industry</th>"\n'
           'Y = "since inception"\nZ = "MTD %"\nW = "above its 50-day average"\nV = "₹1.2 crore"\n'
           'U = "<b>Total Market</b>"\nT = "Worst relative fall"\n')
    got = {h["rule"] for h in new_occurrences(scan_source(bad, "src/ui/probe.py", spec), spec)}
    assert {"G6-one-year", "G8-max-drawdown", "G2-industry", "G7-since-start", "G9-month-so-far",
            "G11-moving-average", "G5-crore", "G1-total-market"} <= got, got
    good = ('"""A docstring may say industry, crore and MTD."""\nHEAD = "12M return"\nNOTE = "6M max drawdown"\nX = "<th>Sector</th>"\nY = "Since 1 Jan 2026"\n'
            'Z = "Month so far · Nov"\nW = "above its 50D EMA"\nV = "₹1.2 Cr"\nU = "Nifty Total Market"\n'
            'S = "<style>/* an industry name, a CSS comment */</style>"\n')
    assert scan_source(good, "src/ui/probe.py", spec) == []
