from __future__ import annotations

import pandas as pd

from src.loaders.screener_loader import fetch_series


class _Response:
    status_code = 200

    def json(self):
        return {
            "datasets": [
                {
                    "metric": "Price",
                    "label": "Price on NSE",
                    "values": [
                        ["2016-09-30", "13.03"],
                        ["2016-10-07", "13.01"],
                        ["2026-09-23", "234.35"],
                    ],
                    "meta": {"is_weekly": True},
                },
                {
                    "metric": "DMA50",
                    "label": "50 DMA",
                    "values": [],
                },
                {
                    "metric": "Volume",
                    "label": "Volume",
                    "values": [
                        ["2016-09-30", "100"],
                        ["2016-10-07", "200"],
                        ["2026-09-23", "300"],
                    ],
                },
            ]
        }


class _Session:
    def get(self, *args, **kwargs):
        return _Response()


def test_fetch_series_accepts_screener_date_value_pairs():
    close, volume = fetch_series("1301", _Session(), days=3650)

    assert len(close) == 3
    assert close.index[0] == pd.Timestamp("2016-09-30")
    assert close.index[-1] == pd.Timestamp("2026-09-23")
    assert close.iloc[0] == 13.03
    assert close.iloc[-1] == 234.35

    assert len(volume) == 3
    assert volume.iloc[-1] == 300.0
