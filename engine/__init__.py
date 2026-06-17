"""表达式引擎包。

把行情字段（open/close/high/low/volume）当操作数、运算当算子，
用**解释器模式**把字符串表达式解析成 AST，再用**计算工厂 + 缓存**求值。

对外主要接口：
- :func:`evaluate` —— 解析并求值一个表达式字符串。
- :func:`parse` —— 仅解析成 AST。
- :data:`OPERATORS` —— 全部已注册算子（按三类分组）。
"""

from .parser import parse, ParseError
from .evaluator import evaluate, Evaluator
from .operators import OPERATORS, OPERATOR_CATEGORIES, list_operators
from .operands import FIELDS

__all__ = [
    "parse",
    "ParseError",
    "evaluate",
    "Evaluator",
    "OPERATORS",
    "OPERATOR_CATEGORIES",
    "list_operators",
    "FIELDS",
]
