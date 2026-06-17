"""模块二回测逻辑单元测试（用确定性合成数据）。"""

import numpy as np
import pandas as pd

from backtest import _backtest_one, _max_drawdown, run_backtest


def _single_asset_prices(opens, closes):
    n = len(opens)
    dates = pd.date_range("2021-01-01", periods=n, freq="D")
    return pd.DataFrame({"open": opens, "close": closes}, index=dates)


def test_buy_and_hold_profit():
    # 第0天买入信号，价格一路上涨，末日平仓应盈利
    opens = [10.0, 11, 12, 13, 14]
    closes = [10.0, 11, 12, 13, 14]
    prices = _single_asset_prices(opens, closes)
    buy = pd.Series([1, 0, 0, 0, 0], index=prices.index)   # T0 买入 -> T1 成交
    sell = pd.Series([0, 0, 0, 0, 0], index=prices.index)
    res = _backtest_one(prices, buy, sell, init_capital=1000.0, fee=0.0)
    # T1 以 11 买入，末日 14 -> 收益 (14/11 - 1)
    assert res["n_trades"] == 1
    assert res["total_return"] > 0
    assert abs(res["total_return"] - (14 / 11 - 1)) < 1e-6


def test_sell_signal_closes_position():
    opens = [10.0, 10, 20, 20]
    closes = [10.0, 10, 20, 20]
    prices = _single_asset_prices(opens, closes)
    buy = pd.Series([1, 0, 0, 0], index=prices.index)
    sell = pd.Series([0, 1, 0, 0], index=prices.index)  # T1 卖出 -> T2 成交
    res = _backtest_one(prices, buy, sell, init_capital=1000.0, fee=0.0)
    # T1 买入价 10，T2 卖出价 20 -> 收益 ~100%
    assert res["n_trades"] == 1
    assert abs(res["total_return"] - 1.0) < 1e-6
    assert res["win_rate"] == 1.0


def test_fee_reduces_return():
    opens = closes = [10.0, 10, 10, 10]
    prices = _single_asset_prices(opens, closes)
    buy = pd.Series([1, 0, 0, 0], index=prices.index)
    sell = pd.Series([0, 0, 1, 0], index=prices.index)
    res = _backtest_one(prices, buy, sell, init_capital=1000.0, fee=0.01)
    # 价格不变但有买卖手续费 -> 亏损
    assert res["total_return"] < 0


def test_no_short_selling():
    # 只有卖出信号、从未买入 -> 不应有任何交易或持仓
    opens = closes = [10.0, 9, 8, 7]
    prices = _single_asset_prices(opens, closes)
    buy = pd.Series([0, 0, 0, 0], index=prices.index)
    sell = pd.Series([1, 1, 1, 1], index=prices.index)
    res = _backtest_one(prices, buy, sell, init_capital=1000.0, fee=0.0)
    assert res["n_trades"] == 0
    assert abs(res["total_return"]) < 1e-12  # 资金原封不动


def test_max_drawdown():
    eq = pd.Series([100, 120, 90, 110.0])
    # 峰值 120 -> 谷 90 => 回撤 25%
    assert abs(_max_drawdown(eq) - 0.25) < 1e-9


def test_run_backtest_invalid_expr_returns_error():
    res = run_backtest("not_a_function(close)", "close < 0", instruments=["RB"])
    assert res["ok"] is False
    assert "error" in res
