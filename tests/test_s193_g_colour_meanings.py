"""S193 item G (owner, 23 Nov 2026): caution means caution only, and one colour per series.

1. The caution colour is for stale data, warnings and "watch" states. Every use
   of it in the UI must sit in a rule or a line on the allowlist below; a chart,
   a series, a category fill or a marker may not take it.
2. A named series (tokens.SERIES) has one colour, set in tokens.py, and every
   chart reads it from there.
"""
from __future__ import annotations

import re
from pathlib import Path

from src.ui import tokens
from src.ui.tokens import C, PALETTE, SERIES, LINE_CYCLE, series_colour, series_var

ROOT = Path(__file__).resolve().parents[1]
SRC = [p for p in (ROOT / "src").rglob("*.py") if p.name != "tokens.py"]
KIT = ROOT / "static" / "dash_charts.js"
CAUTION = re.compile(r"caution|C\.caution|AMBER")

# Each line that may name caution, by a fragment it must contain: the warning
# selectors and functions. A new use of caution has to be added here, on purpose.
WARNING_USES = (
    ".hdr-pill-warn", ".stale-notice", ".mkt-strip .warn", ".pg-bar-t i.warn", ".xw-pill.watch",
    ".xw-g.tight", ".pg-callout.warn", ".badge-yellow", ".bt-warn", "in the caution colour",
    '<span style="color:var(--c-caution)">',        # ranking_view: a dataset that is behind
    ".dh .dh-h2 .watch", ".sp-t td.watch", ".sp-checks li.bad", ".dh-watch{", "h3.dh-watch",
    ".dh-qb-watch",                                  # RRG Weakening badge (unused rule; listed in the S193 G report)
    ".sp-ladder .dot.line",                          # the -20% filter line (listed in the S193 G report)
    'else "var(--c-caution)")',                      # rank trail: in but not rising (listed in the S193 G report)
    "--caution:var(--c-caution);--caution-soft",     # the chart frame's variables, read only by .watch
    ".watch{color:var(--caution)}",
    "color=C.caution,",                              # components: "Fewer than 20 pass" risk alert
    "C.caution if item[\"stale\"]",                  # components: a stale source
    "Amber for a stale source",
    '"var(--c-caution)" if gap_count',               # components: gap-filled closes
)

WARNING_BLOCKS = (".pg-note {",)


def test_caution_is_used_only_for_warnings():
    stray = []
    for p in SRC + [KIT]:
        block = False   # inside a multi-line warning rule (page_kit's one amber note, .pg-note)
        for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if any(b in line for b in WARNING_BLOCKS):
                block = True
            ok = block or line.lstrip().startswith("#") or any(w in line for w in WARNING_USES)
            if CAUTION.search(line) and not ok:
                stray.append(f"{p.relative_to(ROOT)}:{n}: {line.strip()[:120]}")
            if "}" in line:
                block = False
    assert not stray, "caution outside a warning:\n" + "\n".join(stray)


def test_the_chart_kit_draws_no_series_or_band_in_caution():
    js = KIT.read_text(encoding="utf-8")
    assert "--caution" not in js, "the chart kit must not draw in caution"
    # The only frame rule that reads --caution is the .watch text class.
    from src.ui.dash_charts import CSS
    uses = [m.start() for m in re.finditer(r"var\(--caution\)", CSS)]
    assert len(uses) == 1 and ".watch{color:var(--caution)}" in CSS


def test_caution_is_never_an_automatic_or_overlay_colour():
    from src.ui import lw_chart, stock_chart
    assert "var(--c-caution)" not in lw_chart.SPARE and C.caution not in lw_chart.SPARE
    assert C.caution not in stock_chart.MA_COLOURS.values()
    assert not hasattr(lw_chart, "AMBER")
    assert all(tok != "caution" for tok, _ in LINE_CYCLE)


def test_spare_and_cycle_colours_carry_no_series_meaning():
    series_vars = {f"var(--c-{k})" for k in SERIES.values()} | {"var(--c-teal)", "var(--c-violet)"}
    from src.ui import lw_chart
    assert not set(lw_chart.SPARE) & series_vars
    assert not {tok for tok, _ in LINE_CYCLE} & set(SERIES.values())


def test_every_series_is_a_palette_colour_away_from_up_down_and_caution():
    for name, key in SERIES.items():
        hexv = PALETTE[key]
        assert key.startswith("s_"), name
        assert hexv.upper() not in {C.up.upper(), C.down.upper(), C.caution.upper()}, name
        assert series_colour(name) == hexv and series_var(name) == f"var(--c-{key})"


def _lum(h: str) -> float:
    c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    c = [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def test_every_series_line_is_at_least_3_to_1_on_white():
    for name, key in SERIES.items():
        ratio = 1.05 / (_lum(PALETTE[key]) + 0.05)
        assert ratio >= 3.0, (name, PALETTE[key], round(ratio, 2))


def test_charts_take_a_named_series_colour_from_series():
    from src.ui import stock_chart
    for name, colour in stock_chart.MA_COLOURS.items():
        assert colour == series_colour(name), name
    js = KIT.read_text(encoding="utf-8")
    # The kit names these series itself; each must read its series variable.
    for name, var in (("The book", "--s-book"), ("Nifty500 Momentum 50", "--s-mom50"),
                      ("Nifty Total Market", "--s-market"), ("Nifty 500", "--s-n500")):
        for m in re.finditer(r"\{name: '" + re.escape(name) + r"', color: css\('([^']+)'\)", js):
            # a drawdown pane draws the book's fall in the down colour: that is its meaning
            assert m.group(1) in (var, "--down"), (name, m.group(1))
    from src.ui.dash_charts import CSS
    for key in ("s_book", "s_market", "s_n500", "s_mom50", "s_dii"):
        assert f"--{key.replace('_', '-')}:var(--c-{key})" in CSS
    # Python chart specs: a series named in SERIES carries its series colour.
    for p in (ROOT / "src" / "ui" / "views").glob("*.py"):
        src = p.read_text(encoding="utf-8")
        for name, colour in re.findall(r'\{"name": "([^"]+)",[^{}]*?"color": "([a-z0-9_-]+)"', src):
            if name in SERIES:
                assert colour == SERIES[name].replace("_", "-"), (p.name, name, colour)


def test_turning_and_sizes_are_neutral():
    from src.ui.views import dashboard_home_view as dh
    src = Path(dh.__file__).read_text(encoding="utf-8")
    turning = re.findall(r"\.dh-(?:seg|card)-turning\{[^}]*\}|\.dh-g-turning\{[^}]*\}", src)
    assert turning and all("caution" not in r for r in turning)
    sizes = re.findall(r"\.dh-sz-[a-z-]+\{[^}]*\}", src)
    assert sizes and all("caution" not in r for r in sizes)
    ramp = [PALETTE[f"size_{i}"] for i in range(1, 7)]
    assert [_lum(h) for h in ramp] == sorted(_lum(h) for h in ramp), "the size ramp runs dark to light"


def test_the_chart_kit_and_chart_modules_write_no_hex():
    for p in [KIT, ROOT / "src" / "ui" / "dash_charts.py", ROOT / "src" / "ui" / "lw_chart.py",
              ROOT / "src" / "ui" / "stock_chart.py"]:
        assert not re.findall(r"#[0-9A-Fa-f]{6}\b", p.read_text(encoding="utf-8")), p.name


def test_the_app_is_light_only():
    import tomllib
    theme = tomllib.loads((ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8"))["theme"]
    assert theme.get("base") == "light"
    assert "prefers-color-scheme: dark" not in (ROOT / "src" / "ui" / "theme.py").read_text(encoding="utf-8")
    assert tokens.SERIES  # imported for the module's side of the contract
