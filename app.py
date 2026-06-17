"""FastAPI 后端：量化分析平台。

提供两个模块的接口 + 静态前端：
- 模块一 因子分析：``/api/m1/meta``、``/api/m1/run``
- 模块二 策略回测：``/api/m2/instruments``、``/api/m2/run``

启动：``python -m uvicorn app:app --port 8000``
"""

from __future__ import annotations

import os

import compat  # noqa: F401  pandas 3.0 shim，必须最先 import

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from engine import OPERATOR_CATEGORIES, FIELDS
from data_loader import list_futures_instruments
from factor_analysis import run_factor_analysis
from backtest import run_backtest
from logging_conf import get_logger

logger = get_logger("app")

_BASE = os.path.dirname(os.path.abspath(__file__))
_STATIC = os.path.join(_BASE, "static")

app = FastAPI(title="金融量化投资平台", version="1.0")


# --- 请求模型 -------------------------------------------------------------

class FactorRequest(BaseModel):
    expr: str
    quantiles: int = 5
    periods: list[int] = [1, 3]
    max_loss: float = 0.35


class BacktestRequest(BaseModel):
    buy_expr: str
    sell_expr: str
    instruments: list[str] | None = None
    init_capital: float = 1_000_000.0
    fee: float = 0.0003


# --- 页面 -----------------------------------------------------------------

@app.get("/")
def index():
    return FileResponse(os.path.join(_STATIC, "index.html"))


# --- 模块一 ---------------------------------------------------------------

@app.get("/api/m1/meta")
def m1_meta():
    """返回可用字段与算子分类，供前端提示。"""
    return {"fields": list(FIELDS), "operators": OPERATOR_CATEGORIES}


@app.post("/api/m1/run")
def m1_run(req: FactorRequest):
    logger.info("收到模块一请求: %s", req.model_dump())
    return run_factor_analysis(
        req.expr,
        quantiles=req.quantiles,
        periods=tuple(req.periods),
        max_loss=req.max_loss,
    )


# --- 模块二 ---------------------------------------------------------------

@app.get("/api/m2/instruments")
def m2_instruments():
    """按流动性降序返回全部品种代码。"""
    inst = list_futures_instruments()
    return {"instruments": inst, "operators": OPERATOR_CATEGORIES, "fields": list(FIELDS)}


@app.post("/api/m2/run")
def m2_run(req: BacktestRequest):
    logger.info("收到模块二请求: %s", req.model_dump())
    return run_backtest(
        req.buy_expr,
        req.sell_expr,
        instruments=req.instruments,
        init_capital=req.init_capital,
        fee=req.fee,
    )


# 静态资源（放最后，避免覆盖上面的路由）
app.mount("/static", StaticFiles(directory=_STATIC), name="static")
