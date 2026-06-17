"""求值器（计算工厂 + 缓存）。

对解析得到的 AST 做后序求值：
- :class:`Const` -> 标量 float
- :class:`Field` -> 取数据中对应列（pandas Series，MultiIndex (date, asset)）
- :class:`Call`  -> 先求子节点，再套用算子函数

**计算工厂**：每个节点求值前先查缓存（键为 ``node.key``）。
相同子表达式（如 ``mean(close,5)`` 在一个表达式里出现两次）只算一次。
求值过程记录日志：每个节点的计算耗时与缓存命中情况。
"""

from __future__ import annotations

import time

import pandas as pd

from logging_conf import get_logger
from .cache import ResultCache
from .operands import Call, Const, Field, Node
from .operators import ALL_OPERATORS
from .parser import parse

logger = get_logger("engine.evaluator")


class Evaluator:
    """在给定数据上对 AST 求值。

    Parameters
    ----------
    data : pandas.DataFrame
        含列 open/close/high/low/volume，索引为 MultiIndex (date, asset)。
    data_id : str
        数据指纹，用于隔离不同数据集的缓存。
    """

    def __init__(self, data: pd.DataFrame, data_id: str = "default"):
        self.data = data
        self.cache = ResultCache(data_id)

    def eval_node(self, node: Node):
        # 先查缓存（计算工厂的核心：复用中间结果）
        cached, ok = self.cache.get(node.key)
        if ok:
            logger.debug("缓存命中: %s", node.key)
            return cached

        t0 = time.perf_counter()
        if isinstance(node, Const):
            value = node.value
        elif isinstance(node, Field):
            value = self.data[node.name]
        elif isinstance(node, Call):
            args = [self.eval_node(a) for a in node.args]
            _cat, _arity, func = ALL_OPERATORS[node.op_name]
            value = func(*args)
        else:  # pragma: no cover - 不应发生
            raise TypeError(f"未知节点类型: {type(node)!r}")

        dt = (time.perf_counter() - t0) * 1000
        self.cache.put(node.key, value)
        logger.debug("计算 %s 耗时 %.2f ms", node.key, dt)
        return value

    def evaluate(self, expr: str) -> pd.Series:
        """解析并求值表达式字符串，返回结果 Series。"""
        t0 = time.perf_counter()
        ast = parse(expr)
        result = self.eval_node(ast)
        if not isinstance(result, pd.Series):
            # 纯常量表达式 -> 广播成全表
            result = pd.Series(float(result), index=self.data.index)
        dt = (time.perf_counter() - t0) * 1000
        logger.info(
            "求值完成 '%s' | 耗时 %.1f ms | 缓存 %s",
            expr, dt, self.cache.stats(),
        )
        return result


def evaluate(expr: str, data: pd.DataFrame, data_id: str = "default") -> pd.Series:
    """便捷函数：在 data 上求值表达式字符串。"""
    return Evaluator(data, data_id).evaluate(expr)
