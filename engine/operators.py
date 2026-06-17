"""算子注册表。

所有算子作用于「带 MultiIndex (date, asset) 的 pandas Series」，
或标量（数字常量）。算子按计算维度分三类（作业要求每类 >= 3 个）：

- **element_wise**：逐元素，直接作用每个数据点。
  `log abs sign sqrt pow if_else min2 max2`
- **time_series**：沿同一资产的时间轴滚动/平移（按 asset 分组）。
  `mean std sum max min delay shift delta corr cross_up cross_down`
- **cross_sectional**：在同一时间截面跨资产运算（按 date 分组）。
  `rank pctrank zscore demean scale`

算子函数接收的是**已求值**的实参（Series 或 float），由 evaluator 后序求值传入。
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# 工具
# ---------------------------------------------------------------------------

ASSET_LEVEL = -1  # MultiIndex 最后一层是 asset
DATE_LEVEL = 0    # 第一层是 date


def _template(*args):
    """从实参中取第一个 Series 作为对齐模板（索引来源）。"""
    for a in args:
        if isinstance(a, pd.Series):
            return a
    return None


def _as_series(x, template):
    """把标量广播成与 template 同索引的 Series；Series 原样返回。"""
    if isinstance(x, pd.Series):
        return x
    return pd.Series(float(x), index=template.index)


def _ts(s: pd.Series, func) -> pd.Series:
    """按 asset 分组、在时间轴上应用 func，保持原索引。"""
    return s.groupby(level=ASSET_LEVEL, group_keys=False).apply(func)


def _cs(s: pd.Series, func) -> pd.Series:
    """按 date 分组、在横截面上应用 func，保持原索引。"""
    return s.groupby(level=DATE_LEVEL, group_keys=False).apply(func)


# ---------------------------------------------------------------------------
# element_wise
# ---------------------------------------------------------------------------

def op_log(x):
    """自然对数（对非正数取 NaN，避免异常）。"""
    s = x if isinstance(x, pd.Series) else pd.Series([float(x)])
    return np.log(s.where(s > 0))


def op_abs(x):
    return x.abs() if isinstance(x, pd.Series) else abs(float(x))


def op_sign(x):
    return np.sign(x) if isinstance(x, pd.Series) else float(np.sign(x))


def op_sqrt(x):
    s = x if isinstance(x, pd.Series) else pd.Series([float(x)])
    return np.sqrt(s.where(s >= 0))


def op_pow(x, p):
    base = _template(x, p)
    if base is None:
        return float(x) ** float(p)
    xs = _as_series(x, base)
    return np.power(xs, float(p) if not isinstance(p, pd.Series) else p)


def op_if_else(cond, a, b):
    """cond 为真取 a，否则取 b（逐元素）。"""
    tpl = _template(cond, a, b)
    if tpl is None:
        return a if cond else b
    c = _as_series(cond, tpl).astype(bool)
    av = _as_series(a, tpl)
    bv = _as_series(b, tpl)
    return pd.Series(np.where(c, av, bv), index=tpl.index)


def op_min2(a, b):
    tpl = _template(a, b)
    if tpl is None:
        return min(float(a), float(b))
    return pd.concat([_as_series(a, tpl), _as_series(b, tpl)], axis=1).min(axis=1)


def op_max2(a, b):
    tpl = _template(a, b)
    if tpl is None:
        return max(float(a), float(b))
    return pd.concat([_as_series(a, tpl), _as_series(b, tpl)], axis=1).max(axis=1)


# ---------------------------------------------------------------------------
# time_series（窗口/平移，按 asset 分组）
# ---------------------------------------------------------------------------

def _win(w) -> int:
    n = int(round(float(w)))
    if n < 1:
        raise ValueError(f"窗口长度必须 >= 1，收到 {w}")
    return n


def op_ts_mean(x, w):
    n = _win(w)
    return _ts(x, lambda g: g.rolling(n, min_periods=n).mean())


def op_ts_std(x, w):
    n = _win(w)
    return _ts(x, lambda g: g.rolling(n, min_periods=n).std())


def op_ts_sum(x, w):
    n = _win(w)
    return _ts(x, lambda g: g.rolling(n, min_periods=n).sum())


def op_ts_max(x, w):
    n = _win(w)
    return _ts(x, lambda g: g.rolling(n, min_periods=n).max())


def op_ts_min(x, w):
    n = _win(w)
    return _ts(x, lambda g: g.rolling(n, min_periods=n).min())


def op_delay(x, w):
    """delay/shift：取 n 期之前的值。"""
    n = _win(w)
    return _ts(x, lambda g: g.shift(n))


def op_delta(x, w):
    """当前值减去 n 期之前的值。"""
    n = _win(w)
    return _ts(x, lambda g: g - g.shift(n))


def op_corr(a, b, w):
    """两序列在窗口 w 上的滚动相关系数（按 asset 分组）。"""
    n = _win(w)
    tpl = _template(a, b)
    av = _as_series(a, tpl)
    bv = _as_series(b, tpl)
    df = pd.DataFrame({"a": av, "b": bv})

    def _corr(g):
        return g["a"].rolling(n, min_periods=n).corr(g["b"])

    return df.groupby(level=ASSET_LEVEL, group_keys=False).apply(_corr)


def op_cross_up(a, b):
    """a 上穿 b：本期 a>b 且上期 a<=b。返回 0/1 信号。"""
    tpl = _template(a, b)
    av = _as_series(a, tpl)
    bv = _as_series(b, tpl)
    diff = av - bv
    prev = _ts(diff, lambda g: g.shift(1))
    return ((diff > 0) & (prev <= 0)).astype(float)


def op_cross_down(a, b):
    """a 下穿 b：本期 a<b 且上期 a>=b。返回 0/1 信号。"""
    tpl = _template(a, b)
    av = _as_series(a, tpl)
    bv = _as_series(b, tpl)
    diff = av - bv
    prev = _ts(diff, lambda g: g.shift(1))
    return ((diff < 0) & (prev >= 0)).astype(float)


# ---------------------------------------------------------------------------
# cross_sectional（按 date 分组）
# ---------------------------------------------------------------------------

def op_rank(x):
    """横截面排名（升序，1 为最小）。"""
    return _cs(x, lambda g: g.rank(method="average"))


def op_pctrank(x):
    """横截面百分位排名（0~1）。"""
    return _cs(x, lambda g: g.rank(method="average", pct=True))


def op_zscore(x):
    """横截面标准化 (x - mean) / std。"""
    return _cs(x, lambda g: (g - g.mean()) / g.std())


def op_demean(x):
    """横截面去均值。"""
    return _cs(x, lambda g: g - g.mean())


def op_scale(x):
    """横截面缩放：使绝对值之和为 1。"""
    return _cs(x, lambda g: g / g.abs().sum())


# ---------------------------------------------------------------------------
# 注册表：name -> (category, arity, func)
# arity 为参数个数；None 表示该位置接受任意，但这里全部定长。
# ---------------------------------------------------------------------------

OPERATORS = {
    # element_wise
    "log": ("element_wise", 1, op_log),
    "abs": ("element_wise", 1, op_abs),
    "sign": ("element_wise", 1, op_sign),
    "sqrt": ("element_wise", 1, op_sqrt),
    "pow": ("element_wise", 2, op_pow),
    "if_else": ("element_wise", 3, op_if_else),
    "min2": ("element_wise", 2, op_min2),
    "max2": ("element_wise", 2, op_max2),
    # time_series
    "mean": ("time_series", 2, op_ts_mean),
    "std": ("time_series", 2, op_ts_std),
    "sum": ("time_series", 2, op_ts_sum),
    "max": ("time_series", 2, op_ts_max),
    "min": ("time_series", 2, op_ts_min),
    "delay": ("time_series", 2, op_delay),
    "shift": ("time_series", 2, op_delay),  # shift 与 delay 同义
    "delta": ("time_series", 2, op_delta),
    "corr": ("time_series", 3, op_corr),
    "cross_up": ("time_series", 2, op_cross_up),
    "cross_down": ("time_series", 2, op_cross_down),
    # cross_sectional
    "rank": ("cross_sectional", 1, op_rank),
    "pctrank": ("cross_sectional", 1, op_pctrank),
    "zscore": ("cross_sectional", 1, op_zscore),
    "demean": ("cross_sectional", 1, op_demean),
    "scale": ("cross_sectional", 1, op_scale),
}

# 算术运算符（解析器把 + - * / 也映射成算子）
def op_add(a, b):
    tpl = _template(a, b)
    if tpl is None:
        return float(a) + float(b)
    return _as_series(a, tpl) + _as_series(b, tpl)


def op_sub(a, b):
    tpl = _template(a, b)
    if tpl is None:
        return float(a) - float(b)
    return _as_series(a, tpl) - _as_series(b, tpl)


def op_mul(a, b):
    tpl = _template(a, b)
    if tpl is None:
        return float(a) * float(b)
    return _as_series(a, tpl) * _as_series(b, tpl)


def op_div(a, b):
    tpl = _template(a, b)
    if tpl is None:
        return float(a) / float(b)
    return _as_series(a, tpl) / _as_series(b, tpl)


def op_neg(a):
    return -a


def op_gt(a, b):
    tpl = _template(a, b)
    if tpl is None:
        return float(a > b)
    return (_as_series(a, tpl) > _as_series(b, tpl)).astype(float)


def op_lt(a, b):
    tpl = _template(a, b)
    if tpl is None:
        return float(a < b)
    return (_as_series(a, tpl) < _as_series(b, tpl)).astype(float)


def op_and(a, b):
    tpl = _template(a, b)
    if tpl is None:
        return float(bool(a) and bool(b))
    return ((_as_series(a, tpl) != 0) & (_as_series(b, tpl) != 0)).astype(float)


def op_or(a, b):
    tpl = _template(a, b)
    if tpl is None:
        return float(bool(a) or bool(b))
    return ((_as_series(a, tpl) != 0) | (_as_series(b, tpl) != 0)).astype(float)


# 这些是运算符内部算子，不对外展示为"函数"，但同样走缓存。
INTERNAL_OPERATORS = {
    "__add__": ("element_wise", 2, op_add),
    "__sub__": ("element_wise", 2, op_sub),
    "__mul__": ("element_wise", 2, op_mul),
    "__div__": ("element_wise", 2, op_div),
    "__neg__": ("element_wise", 1, op_neg),
    "__gt__": ("element_wise", 2, op_gt),
    "__lt__": ("element_wise", 2, op_lt),
    "__and__": ("element_wise", 2, op_and),
    "__or__": ("element_wise", 2, op_or),
}

ALL_OPERATORS = {**OPERATORS, **INTERNAL_OPERATORS}


def list_operators():
    """按类别返回对外可用算子名（供前端提示）。"""
    cats: dict[str, list[str]] = {
        "element_wise": [],
        "time_series": [],
        "cross_sectional": [],
    }
    for name, (cat, _arity, _f) in OPERATORS.items():
        cats[cat].append(name)
    return cats


OPERATOR_CATEGORIES = list_operators()
