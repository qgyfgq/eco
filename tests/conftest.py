"""pytest 公共夹具：把项目根加入 sys.path，并提供小型测试数据。"""

import os
import sys

import numpy as np
import pandas as pd
import pytest

# 让测试能 import 项目根下的模块
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


@pytest.fixture
def small_panel():
    """3 个资产 × 8 个日期的小型面板，MultiIndex (date, asset)。"""
    dates = pd.date_range("2020-01-31", periods=8, freq="ME")
    assets = ["A", "B", "C"]
    idx = pd.MultiIndex.from_product([dates, assets], names=["date", "asset"])
    rng = np.arange(1, len(idx) + 1, dtype=float)
    df = pd.DataFrame(
        {
            "open": rng,
            "close": rng + 0.5,
            "high": rng + 1.0,
            "low": rng - 0.5,
            "volume": rng * 100,
        },
        index=idx,
    )
    return df
