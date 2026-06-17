"""模块二：策略指标自定义回测。

买入/卖出信号均为表达式字符串，经表达式引擎求值为布尔信号。
回测规则（按 PDF）：
- **只做多、不做空**；每支合约**各自独立满仓**回测，最后等权汇总成组合。
- 无持仓 且 买入信号为真 → 按**下一根** bar 的开盘价满仓买入（扣手续费）。
- 持仓中 且 卖出信号为真 → 按下一根 bar 的开盘价全部卖出（扣手续费）。
- 信号在 T 日成立，T+1 成交，避免未来函数。

输出：总收益、年化收益、最大回撤、胜率、盈亏比、交易次数、组合权益曲线、
各品种明细表。
"""

from __future__ import annotations

import base64
import io
import time

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from data_loader import load_futures, list_futures_instruments  # noqa: E402
from engine import Evaluator  # noqa: E402
from logging_conf import get_logger  # noqa: E402

logger = get_logger("backtest")

TRADING_DAYS = 252


def _max_drawdown(equity: pd.Series) -> float:
    """最大回撤（正数，0.2 表示 -20%）。"""
    if equity.empty:
        return 0.0
    running_max = equity.cummax()
    dd = equity / running_max - 1.0
    return float(-dd.min())


def _backtest_one(
    prices: pd.DataFrame,
    buy_sig: pd.Series,
    sell_sig: pd.Series,
    init_capital: float,
    fee: float,
) -> dict:
    """对单支合约做满仓多头回测。

    prices: 单合约 DataFrame，索引为 date，含 open/close 列（已按日期升序）。
    buy_sig/sell_sig: 同索引布尔信号。
    返回该合约的权益序列与交易统计。
    """
    open_px = prices["open"].to_numpy(dtype=float)
    close_px = prices["close"].to_numpy(dtype=float)
    dates = prices.index
    n = len(prices)

    buy = buy_sig.reindex(dates).fillna(0).to_numpy() != 0
    sell = sell_sig.reindex(dates).fillna(0).to_numpy() != 0

    cash = float(init_capital)
    shares = 0.0
    position = False
    entry_value = 0.0  # 本次持仓买入时的市值（含费后），用于算单笔盈亏

    equity = np.empty(n, dtype=float)
    trades: list[float] = []  # 每笔平仓的收益率

    for t in range(n):
        # 先按信号在 T+1（即本根 open）成交：用上一根的信号
        if t > 0:
            if (not position) and buy[t - 1]:
                # 满仓买入
                price = open_px[t]
                if price > 0 and np.isfinite(price):
                    invest = cash
                    shares = invest * (1 - fee) / price
                    entry_value = invest
                    cash = 0.0
                    position = True
            elif position and sell[t - 1]:
                # 全部卖出
                price = open_px[t]
                if price > 0 and np.isfinite(price):
                    proceeds = shares * price * (1 - fee)
                    trades.append(proceeds / entry_value - 1.0)
                    cash = proceeds
                    shares = 0.0
                    position = False

        # 当日收盘市值
        mkt = shares * close_px[t] if position else 0.0
        equity[t] = cash + mkt

    # 末日若仍持仓，按最后收盘价平仓计入交易
    if position and entry_value > 0:
        proceeds = shares * close_px[-1] * (1 - fee)
        trades.append(proceeds / entry_value - 1.0)

    equity_s = pd.Series(equity, index=dates)
    n_trades = len(trades)
    wins = [r for r in trades if r > 0]
    losses = [r for r in trades if r <= 0]
    win_rate = len(wins) / n_trades if n_trades else 0.0
    avg_win = float(np.mean(wins)) if wins else 0.0
    avg_loss = float(np.mean(losses)) if losses else 0.0
    profit_factor = (sum(wins) / -sum(losses)) if losses and sum(losses) != 0 else (
        float("inf") if wins else 0.0
    )
    total_ret = equity[-1] / init_capital - 1.0

    return {
        "equity": equity_s,
        "total_return": float(total_ret),
        "max_drawdown": _max_drawdown(equity_s),
        "n_trades": n_trades,
        "win_rate": win_rate,
        "profit_factor": float(profit_factor),
        "avg_win": avg_win,
        "avg_loss": avg_loss,
    }


def _annualized(total_return: float, n_days: int) -> float:
    if n_days <= 0:
        return 0.0
    years = n_days / TRADING_DAYS
    if years <= 0:
        return 0.0
    return (1.0 + total_return) ** (1.0 / years) - 1.0


def _equity_plot_base64(equity: pd.Series) -> str:
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(equity.index, equity.values, color="#2563eb", lw=1.5)
    ax.set_title("Portfolio Equity Curve")
    ax.set_ylabel("Equity")
    ax.grid(True, alpha=0.3)
    fig.autofmt_xdate()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", dpi=90)
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("ascii")


def run_backtest(
    buy_expr: str,
    sell_expr: str,
    instruments: list[str] | None = None,
    init_capital: float = 1_000_000.0,
    fee: float = 0.0003,
) -> dict:
    """对选定品种做"每支独立满仓多头"回测并汇总组合。

    Parameters
    ----------
    buy_expr, sell_expr : str
        买入/卖出信号表达式（结果非零视为信号成立）。
    instruments : list[str] | None
        品种代码列表；None 表示全部品种。
    init_capital : float
        每支合约的初始资金（独立账户）。
    fee : float
        单边手续费率。

    Returns
    -------
    dict
        ``{ok, image, metrics, per_instrument, meta}`` 或 ``{ok: False, error}``。
    """
    t0 = time.perf_counter()
    logger.info(
        "回测请求: buy=%r sell=%r n_instruments=%s init=%s fee=%s",
        buy_expr, sell_expr, len(instruments) if instruments else "ALL", init_capital, fee,
    )
    try:
        data = load_futures()
        all_inst = list_futures_instruments()
        if instruments:
            sel = [s for s in instruments if s in set(all_inst)]
            if not sel:
                return {"ok": False, "error": "所选品种均不存在于数据中。"}
        else:
            sel = all_inst

        subset = data[data.index.get_level_values("asset").isin(sel)]

        # 信号在整个子集上一次性求值（表达式引擎按 asset 分组处理时序算子）
        ev = Evaluator(subset, data_id="futures")
        buy_sig_all = ev.evaluate(buy_expr)
        sell_sig_all = ev.evaluate(sell_expr)

        per_inst = []
        equities = []
        for inst in sel:
            mask = subset.index.get_level_values("asset") == inst
            prices = subset[mask].reset_index(level="asset", drop=True).sort_index()
            if len(prices) < 2:
                continue
            buy_sig = buy_sig_all[mask].reset_index(level="asset", drop=True)
            sell_sig = sell_sig_all[mask].reset_index(level="asset", drop=True)

            res = _backtest_one(prices, buy_sig, sell_sig, init_capital, fee)
            equities.append(res["equity"].rename(inst))
            per_inst.append(
                {
                    "instrument": inst,
                    "total_return": round(res["total_return"], 4),
                    "max_drawdown": round(res["max_drawdown"], 4),
                    "n_trades": res["n_trades"],
                    "win_rate": round(res["win_rate"], 4),
                    "profit_factor": (
                        None if not np.isfinite(res["profit_factor"]) else round(res["profit_factor"], 4)
                    ),
                }
            )

        if not equities:
            return {"ok": False, "error": "没有可回测的品种（数据不足）。"}

        # 等权汇总：各品种独立账户的权益相加（按日期对齐，缺失前向填充）
        eq_df = pd.concat(equities, axis=1).sort_index()
        eq_df = eq_df.ffill().fillna(float(init_capital))
        portfolio = eq_df.sum(axis=1)

        total_capital = init_capital * len(equities)
        total_return = float(portfolio.iloc[-1] / total_capital - 1.0)
        ann_return = _annualized(total_return, len(portfolio))
        ann_vol = float(portfolio.pct_change().std() * np.sqrt(TRADING_DAYS))
        daily_ret = portfolio.pct_change().dropna()
        sharpe = float(daily_ret.mean() / daily_ret.std() * np.sqrt(TRADING_DAYS)) if daily_ret.std() else 0.0

        total_trades = sum(p["n_trades"] for p in per_inst)
        total_wins = sum(p["n_trades"] * p["win_rate"] for p in per_inst)
        agg_win_rate = total_wins / total_trades if total_trades else 0.0

        metrics = {
            "total_return": round(total_return, 4),
            "annual_return": round(ann_return, 4),
            "annual_volatility": round(ann_vol, 4),
            "sharpe": round(sharpe, 4),
            "max_drawdown": round(_max_drawdown(portfolio), 4),
            "win_rate": round(agg_win_rate, 4),
            "total_trades": int(total_trades),
            "n_instruments": len(equities),
        }

        result = {
            "ok": True,
            "image": _equity_plot_base64(portfolio),
            "metrics": metrics,
            "per_instrument": per_inst,
            "meta": {
                "buy_expr": buy_expr,
                "sell_expr": sell_expr,
                "init_capital": init_capital,
                "fee": fee,
                "cache": ev.cache.stats(),
                "elapsed_ms": round((time.perf_counter() - t0) * 1000, 1),
            },
        }
        logger.info("回测完成: %s", metrics)
        return result

    except Exception as exc:  # noqa: BLE001
        logger.exception("回测失败: %s", exc)
        plt.close("all")
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
