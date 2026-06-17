"""模块一：因子自动分析。

流程：因子表达式字符串 → 表达式引擎求值得因子值（MultiIndex date,asset）
→ alphalens ``get_clean_factor_and_forward_returns`` → ``create_full_tear_sheet``
出全套分析图（转 base64 PNG）+ 关键指标表（IC / 分位收益 / 换手）转 JSON。
"""

from __future__ import annotations

import base64
import io
import time

import compat  # noqa: F401  在 import alphalens 之前装好 pandas 3.0 shim

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

import pandas as pd  # noqa: E402

from alphalens.utils import get_clean_factor_and_forward_returns  # noqa: E402
from alphalens.tears import create_full_tear_sheet  # noqa: E402
from alphalens.performance import (  # noqa: E402
    factor_information_coefficient,
    mean_return_by_quantile,
)

from data_loader import load_stocks  # noqa: E402
from engine import Evaluator  # noqa: E402
from logging_conf import get_logger  # noqa: E402

logger = get_logger("factor_analysis")


def _figs_to_base64() -> list[str]:
    """把当前所有 matplotlib figure 转成 base64 PNG 字符串并关闭。"""
    images = []
    for num in plt.get_fignums():
        fig = plt.figure(num)
        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight", dpi=90)
        buf.seek(0)
        images.append(base64.b64encode(buf.read()).decode("ascii"))
    plt.close("all")
    return images


def _df_to_records(df: pd.DataFrame) -> dict:
    """DataFrame -> 前端易渲染的 {columns, index, rows} 结构。"""
    df = df.round(4)
    return {
        "columns": [str(c) for c in df.columns],
        "index": [str(i) for i in df.index],
        "rows": df.astype(object).where(pd.notnull(df), None).values.tolist(),
    }


def run_factor_analysis(
    expr: str,
    quantiles: int = 5,
    periods: tuple[int, ...] = (1, 3),
    max_loss: float = 0.35,
) -> dict:
    """对因子表达式做完整 alphalens 分析。

    Parameters
    ----------
    expr : str
        因子表达式，如 ``rank(-close)`` 或 ``mean(close,3)``。
    quantiles : int
        分位数（alphalens 分组数）。
    periods : tuple[int, ...]
        前瞻收益周期。
    max_loss : float
        alphalens 允许丢弃的最大数据比例。

    Returns
    -------
    dict
        成功：``{ok, images, tables, meta}``；失败：``{ok: False, error}``。
    """
    t0 = time.perf_counter()
    logger.info("因子分析请求: expr=%r quantiles=%s periods=%s", expr, quantiles, periods)
    try:
        data = load_stocks()

        ev = Evaluator(data, data_id="stocks")
        factor = ev.evaluate(expr)
        factor = factor.replace([float("inf"), float("-inf")], pd.NA).dropna()
        factor.index = factor.index.set_names(["date", "asset"])
        if factor.empty:
            return {"ok": False, "error": "因子在该数据上全为空/无效值，无法分析。"}

        # alphalens 需要价格宽表：index=date, columns=asset
        prices = data["close"].unstack("asset").sort_index()

        clean = get_clean_factor_and_forward_returns(
            factor,
            prices,
            quantiles=quantiles,
            periods=tuple(periods),
            max_loss=max_loss,
        )

        # 关键指标表（结构化，供前端表格）
        ic = factor_information_coefficient(clean)
        mean_quant, _ = mean_return_by_quantile(clean)

        ic_summary = pd.DataFrame(
            {
                "IC Mean": ic.mean(),
                "IC Std": ic.std(),
                "Risk-Adjusted IC": ic.mean() / ic.std(),
                "t-stat(IC)": ic.mean() / ic.std() * (len(ic) ** 0.5),
            }
        )

        # 完整 tear sheet（含全部分析图）
        plt.close("all")
        create_full_tear_sheet(clean)
        images = _figs_to_base64()

        result = {
            "ok": True,
            "images": images,
            "tables": {
                "ic_summary": _df_to_records(ic_summary),
                "mean_return_by_quantile_bps": _df_to_records(mean_quant * 10000),
            },
            "meta": {
                "expr": expr,
                "quantiles": quantiles,
                "periods": list(periods),
                "n_factor_values": int(len(factor)),
                "n_clean": int(len(clean)),
                "cache": ev.cache.stats(),
                "elapsed_ms": round((time.perf_counter() - t0) * 1000, 1),
            },
        }
        logger.info("因子分析完成: %s", result["meta"])
        return result

    except Exception as exc:  # noqa: BLE001 - 把错误友好地返回前端
        logger.exception("因子分析失败: %s", exc)
        plt.close("all")
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
