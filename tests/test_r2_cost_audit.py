from scripts.r2_cost_audit import main


def test_cost_audit_reports_inventory(monkeypatch, capsys):
    class Archive:
        def list_keys(self, prefix):
            return iter(
                [
                    "archive/manifests/d/2026-01-01/current.json",
                    "archive/manifests/d/2026-01-01/revisions/" + "a" * 64 + ".json",
                ]
            )

        def head(self, key):
            return {"ContentLength": 123}

    monkeypatch.setattr("scripts.r2_cost_audit.R2Config.from_env", lambda: object())
    monkeypatch.setattr("scripts.r2_cost_audit.R2Archive", lambda cfg: Archive())
    assert main([]) == 0
    out = capsys.readouterr().out
    assert '"manifest_revision_bytes": 123' in out
    assert '"current_pointer_count": 1' in out
