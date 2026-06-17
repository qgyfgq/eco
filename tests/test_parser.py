"""解析器单元测试：嵌套、运算符优先级、错误处理。"""

import pytest

from engine import parse
from engine.parser import ParseError


def test_parse_simple_field():
    node = parse("close")
    assert node.key == "F:close"


def test_parse_nested_call():
    node = parse("corr(rank(close), delta(volume, 3), 12)")
    assert node.op_name == "corr"
    assert node.key == "corr(rank(F:close),delta(F:volume,C:3),C:12)"


def test_operator_precedence():
    # a + b * c  应解析为 a + (b*c)
    node = parse("close + volume * 2")
    assert node.op_name == "__add__"
    assert node.args[1].op_name == "__mul__"


def test_unary_negation():
    node = parse("-close")
    assert node.op_name == "__neg__"


def test_parens_override_precedence():
    node = parse("(close + volume) * 2")
    assert node.op_name == "__mul__"


@pytest.mark.parametrize(
    "expr",
    [
        "",                       # 空表达式
        "mean(close)",            # 参数个数错误（需要 2 个）
        "unknown_fn(close)",      # 未知函数
        "foobar",                 # 未知字段
        "close +",                # 语法不完整
        "mean(close, 5))",        # 多余括号
        "@#$",                    # 非法字符
    ],
)
def test_invalid_expressions_raise(expr):
    with pytest.raises(ParseError):
        parse(expr)
