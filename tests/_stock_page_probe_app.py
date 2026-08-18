"""Drive the real stock page through Streamlit's AppTest."""
import numpy as np, pandas as pd, streamlit as st
from src.engine.momentum import MomentumEngine
from src.ui.views.ranking_view import render_ranking_view

n, cols = 400, 8
idx = pd.bdate_range(end="2026-08-18", periods=n)
rng = np.random.default_rng(4)
px = pd.DataFrame(100*np.exp(np.cumsum(rng.normal(0.0004,0.012,(n,cols)),axis=0)),
                  index=idx, columns=[f"S{i}" for i in range(cols)])
info = pd.DataFrame({"Symbol":[f"S{i}" for i in range(cols)],
                     "Industry":["IT","Bank"]*(cols//2), "Indices":["NIFTY 50"]*cols})
calc = MomentumEngine(px, high_df=px*1.01, low_df=px*0.99, close_df=px,
                      volume_df=pd.DataFrame(1e5, index=idx, columns=px.columns))
rank_df = calc.get_rankings(info, pd.Series(1e4, index=px.columns),
                            close_prices_df=px, high_prices_df=px*1.01)
rank_df["TV_Sector"] = "Tech"
render_ranking_view(rank_df, px, high_prices=px*1.01, low_prices=px*0.99,
                    volume_data=pd.DataFrame(1e5, index=idx, columns=px.columns))
