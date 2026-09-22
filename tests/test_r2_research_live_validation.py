from scripts.r2_research_live_validation import main

def test_live_cli_requires_pin(monkeypatch):
    monkeypatch.setattr("sys.argv", ["r2_research_live_validation"])
    try:
        main()
    except SystemExit as exc:
        assert exc.code != 0
