"""三类算子的单元测试（每类至少覆盖 3 个）。"""

import numpy as np
import pandas as pd

from engine import evaluate


# ---------- element_wise ----------

def test_log(small_panel):
    out = evaluate("log(close)", small_panel)
    expected = np.log(small_panel["close"])
    pd.testing.assert_series_equal(out, expected, check_names=False)


def test_abs_and_sign(small_panel):
    out_abs = evaluate("abs(-close)", small_panel)
    pd.testing.assert_series_equal(out_abs, small_panel["close"], check_names=False)
    out_sign = evaluate("sign(close)", small_panel)
    assert (out_sign == 1.0).all()


def test_min2_max2(small_panel):
    lo = evaluate("min2(open, close)", small_panel)
    hi = evaluate("max2(open, close)", small_panel)
    assert (lo <= hi).all()
    # open < close 恒成立（夹具里 close=open+0.5）
    pd.testing.assert_series_equal(lo, small_panel["open"], check_names=False)


def test_if_else(small_panel):
    # close>open 恒真 -> 取 high，否则 low
    out = evaluate("if_else(close > open, high, low)", small_panel)
    pd.testing.assert_series_equal(out, small_panel["high"], check_names=False)


# ---------- time_series ----------

def test_ts_mean(small_panel):
    out = evaluate("mean(close, 2)", small_panel)
    # 每个资产首期应为 NaN（窗口不足）
    a = out.xs("A", level="asset")
    assert np.isnan(a.iloc[0])
    assert not np.isnan(a.iloc[1])


def test_delay_and_delta(small_panel):
    delayed = evaluate("delay(close, 1)", small_panel)
    delta = evaluate("delta(close, 1)", small_panel)
    a_close = small_panel["close"].xs("A", level="asset")
    a_delay = delayed.xs("A", level="asset")
    assert a_delay.iloc[1] == a_close.iloc[0]
    # delta = close - delay
    a_delta = delta.xs("A", level="asset")
    assert abs(a_delta.iloc[1] - (a_close.iloc[1] - a_close.iloc[0])) < 1e-9


def test_cross_up_down():
    # 构造一个明确的上穿/下穿场景（单资产）
    dates = pd.date_range("2021-01-31", periods=4, freq="ME")
    idx = pd.MultiIndex.from_product([dates, ["X"]], names=["date", "asset"])
    df = pd.DataFrame(
        {
            "open": [1, 1, 1, 1.0],
            "close": [1.0, 3.0, 1.0, 3.0],  # 围绕 2 上下穿
            "high": [1, 3, 1, 3.0],
            "low": [1, 3, 1, 3.0],
            "volume": [1, 1, 1, 1.0],
        },
        index=idx,
    )
    up = evaluate("cross_up(close, 2)", df).xs("X", level="asset")
    down = evaluate("cross_down(close, 2)", df).xs("X", level="asset")
    assert list(up.values) == [0.0, 1.0, 0.0, 1.0]
    assert list(down.values) == [0.0, 0.0, 1.0, 0.0]


# ---------- cross_sectional ----------

def test_rank(small_panel):
    out = evaluate("rank(close)", small_panel)
    # 每个日期内 3 个资产，排名应为 {1,2,3}
    first_date = out.index.get_level_values("date")[0]
    vals = sorted(out.xs(first_date, level="date").values)
    assert vals == [1.0, 2.0, 3.0]


def test_zscore_demean(small_panel):
    z = evaluate("zscore(close)", small_panel)
    dm = evaluate("demean(close)", small_panel)
    # 每个截面去均值后求和应接近 0
    for d in small_panel.index.get_level_values("date").unique():
        assert abs(dm.xs(d, level="date").sum()) < 1e-9
        assert abs(z.xs(d, level="date").mean()) < 1e-9


def test_scale(small_panel):
    out = evaluate("scale(close)", small_panel)
    for d in small_panel.index.get_level_values("date").unique():
        assert abs(out.xs(d, level="date").abs().sum() - 1.0) < 1e-9
