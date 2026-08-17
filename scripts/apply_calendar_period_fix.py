from pathlib import Path

path = Path("app.py")
text = path.read_text()

old_import = "from src.engine.momentum import MomentumEngine\n"
new_import = old_import + "from src.engine.calendar_momentum import apply_calendar_momentum\n"
if old_import not in text:
    raise SystemExit("MomentumEngine import anchor not found")
if "apply_calendar_momentum" not in text:
    text = text.replace(old_import, new_import, 1)

old_call = "    calc.calculate_sharpe_momentum()\n"
if text.count(old_call) != 1:
    raise SystemExit(f"Expected exactly one calculate_sharpe_momentum call, found {text.count(old_call)}")
text = text.replace(old_call, "    apply_calendar_momentum(calc)\n", 1)

old_version = '        "v3_dd6m_revised",\n'
new_version = '        "v4_calendar_periods",\n'
if old_version in text:
    text = text.replace(old_version, new_version, 1)
elif '"v4_calendar_periods"' not in text:
    raise SystemExit("Pipeline version anchor not found")

path.write_text(text)
