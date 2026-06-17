"""操作数与 AST 节点定义。

操作数（operand）= 行情字段（open/close/high/low/volume）或数字常量。
算子（operator）= 对操作数的运算，可嵌套。三种节点共同构成表达式 AST：

- :class:`Const` —— 数字常量，求值为标量。
- :class:`Field` —— 字段引用，求值为一列序列（pandas Series）。
- :class:`Call`  —— 算子调用，对子节点求值后套用算子。

每个节点都暴露 ``key`` —— 一个规范化签名字符串，
供计算工厂在求值时做缓存（相同 key 的子表达式只算一次）。
"""

from __future__ import annotations

from typing import List

# 可用字段（操作数）。回测数据列名会先归一化到这套名字。
FIELDS = ("open", "close", "high", "low", "volume")


class Node:
    """AST 节点基类。"""

    #: 规范化签名，缓存键。子类必须设置。
    key: str

    def __repr__(self) -> str:  # pragma: no cover - 仅调试用
        return f"<{self.__class__.__name__} {self.key}>"


class Const(Node):
    """数字常量，例如 ``5`` 或 ``-1.5``。"""

    def __init__(self, value: float):
        self.value = float(value)
        # 整数常量去掉小数尾巴，便于 key 可读（5 而非 5.0）
        if self.value.is_integer():
            self.key = f"C:{int(self.value)}"
        else:
            self.key = f"C:{self.value}"


class Field(Node):
    """字段引用，例如 ``close``。"""

    def __init__(self, name: str):
        if name not in FIELDS:
            raise ValueError(
                f"未知字段 '{name}'，可用字段：{', '.join(FIELDS)}"
            )
        self.name = name
        self.key = f"F:{name}"


class Call(Node):
    """算子调用，例如 ``mean(close, 5)``。"""

    def __init__(self, op_name: str, args: List[Node]):
        self.op_name = op_name
        self.args = args
        self.key = f"{op_name}(" + ",".join(a.key for a in args) + ")"
