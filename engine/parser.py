"""表达式解析器（解释器模式）。

把因子/信号表达式字符串解析成 AST（:mod:`engine.operands` 中的节点）。
自写词法分析 + 递归下降语法分析，**不使用 eval**，从根本上杜绝注入。

支持的语法：
- 字段：``open close high low volume``
- 数字：``5``、``1.5``、``-2``
- 函数调用：``mean(close, 5)``、``corr(rank(close), delta(volume,3), 12)``
- 算术 / 比较 / 逻辑运算符（含优先级与括号）：
  ``+ - * /``、``> <``、``&&  ||``、``( )``

文法（优先级由低到高）：

    expr    := or_expr
    or_expr := and_expr ( '||' and_expr )*
    and_expr:= cmp_expr ( '&&' cmp_expr )*
    cmp_expr:= add_expr ( ('>'|'<') add_expr )*
    add_expr:= mul_expr ( ('+'|'-') mul_expr )*
    mul_expr:= unary   ( ('*'|'/') unary )*
    unary   := '-' unary | primary
    primary := number | call | field | '(' expr ')'
    call    := NAME '(' [ expr ( ',' expr )* ] ')'
"""

from __future__ import annotations

import re
from typing import List, Optional

from .operands import Call, Const, Field, FIELDS, Node
from .operators import OPERATORS


class ParseError(ValueError):
    """表达式语法/语义错误，消息对用户友好。"""


# --- 词法 -----------------------------------------------------------------

_TOKEN_RE = re.compile(
    r"""
      (?P<NUMBER> \d+\.\d+ | \d+ )
    | (?P<NAME>   [A-Za-z_][A-Za-z0-9_]* )
    | (?P<OP>     \|\| | && | [()+\-*/,><] )
    | (?P<WS>     \s+ )
    """,
    re.VERBOSE,
)


class _Tok:
    __slots__ = ("kind", "value", "pos")

    def __init__(self, kind: str, value: str, pos: int):
        self.kind = kind
        self.value = value
        self.pos = pos


def tokenize(text: str) -> List[_Tok]:
    toks: List[_Tok] = []
    i = 0
    while i < len(text):
        m = _TOKEN_RE.match(text, i)
        if not m:
            raise ParseError(f"无法识别的字符 '{text[i]}'（位置 {i}）")
        kind = m.lastgroup
        value = m.group()
        if kind != "WS":
            toks.append(_Tok(kind, value, i))
        i = m.end()
    toks.append(_Tok("EOF", "", len(text)))
    return toks


# --- 语法（递归下降）------------------------------------------------------

# 二元运算符 -> 内部算子名
_BINOP = {
    "+": "__add__",
    "-": "__sub__",
    "*": "__mul__",
    "/": "__div__",
    ">": "__gt__",
    "<": "__lt__",
    "&&": "__and__",
    "||": "__or__",
}


class _Parser:
    def __init__(self, text: str):
        self.text = text
        self.toks = tokenize(text)
        self.i = 0

    @property
    def cur(self) -> _Tok:
        return self.toks[self.i]

    def _eat(self, value: Optional[str] = None) -> _Tok:
        t = self.cur
        if value is not None and t.value != value:
            raise ParseError(f"期望 '{value}'，却遇到 '{t.value or 'EOF'}'（位置 {t.pos}）")
        self.i += 1
        return t

    def parse(self) -> Node:
        if self.cur.kind == "EOF":
            raise ParseError("表达式为空")
        node = self._or()
        if self.cur.kind != "EOF":
            raise ParseError(
                f"表达式末尾有多余内容 '{self.cur.value}'（位置 {self.cur.pos}）"
            )
        return node

    def _binary(self, sub, ops):
        node = sub()
        while self.cur.value in ops:
            op = self._eat().value
            rhs = sub()
            node = Call(_BINOP[op], [node, rhs])
        return node

    def _or(self):
        return self._binary(self._and, {"||"})

    def _and(self):
        return self._binary(self._cmp, {"&&"})

    def _cmp(self):
        return self._binary(self._add, {">", "<"})

    def _add(self):
        return self._binary(self._mul, {"+", "-"})

    def _mul(self):
        return self._binary(self._unary, {"*", "/"})

    def _unary(self):
        if self.cur.value == "-":
            self._eat("-")
            return Call("__neg__", [self._unary()])
        return self._primary()

    def _primary(self):
        t = self.cur
        if t.kind == "NUMBER":
            self._eat()
            return Const(float(t.value))
        if t.value == "(":
            self._eat("(")
            node = self._or()
            self._eat(")")
            return node
        if t.kind == "NAME":
            # 函数调用 or 字段
            if self.toks[self.i + 1].value == "(":
                return self._call()
            self._eat()
            if t.value not in FIELDS:
                raise ParseError(
                    f"未知标识符 '{t.value}'（位置 {t.pos}）。"
                    f"可用字段：{', '.join(FIELDS)}"
                )
            return Field(t.value)
        raise ParseError(f"无法解析的记号 '{t.value or 'EOF'}'（位置 {t.pos}）")

    def _call(self):
        name_tok = self._eat()  # NAME
        name = name_tok.value
        self._eat("(")
        args: List[Node] = []
        if self.cur.value != ")":
            args.append(self._or())
            while self.cur.value == ",":
                self._eat(",")
                args.append(self._or())
        self._eat(")")

        if name not in OPERATORS:
            raise ParseError(
                f"未知函数 '{name}'（位置 {name_tok.pos}）。"
                f"可用函数见接口 /api 算子列表。"
            )
        _cat, arity, _func = OPERATORS[name]
        if len(args) != arity:
            raise ParseError(
                f"函数 '{name}' 需要 {arity} 个参数，却收到 {len(args)} 个"
                f"（位置 {name_tok.pos}）"
            )
        return Call(name, args)


def parse(text: str) -> Node:
    """解析表达式字符串为 AST 根节点。失败抛 :class:`ParseError`。"""
    return _Parser(text).parse()
