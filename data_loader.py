"""数据加载（带进程内缓存）。

两个素材数据集统一加载为「MultiIndex (date, asset) 的长表 DataFrame」，
列名归一化为 open/close/high/low/volume，供表达式引擎直接使用。
"""

from __future__ import annotations

import os
from functools import lru_cache

import pandas as pd

from logging_conf import get_logger

logger = get_logger("data_loader")

_BASE = os.path.dirname(os.path.abspath(__file__))
STOCK_PATH = os.path.join(_BASE, "data1", "data1", "stocks_sample_monthly.parquet")
FUTURE_PATH = os.path.join(_BASE, "data2", "domant_price.parquet")


@lru_cache(maxsize=1)
def load_stocks() -> pd.DataFrame:
    """模块一：491 只股票月频数据。

    返回索引 MultiIndex (date, asset)，列 open/close/high/low/volume。
    """
    df = pd.read_parquet(STOCK_PATH)
    df = df.rename(columns={"order_book_id": "asset"})
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index(["date", "asset"]).sort_index()
    out = df[["open", "close", "high", "low", "volume"]].astype(float)
    logger.info("加载股票数据: %s 行, %d 只股票", len(out), out.index.get_level_values("asset").nunique())
    return out


@lru_cache(maxsize=1)
def load_futures() -> pd.DataFrame:
    """模块二：97 个主力连续合约日频数据。

    返回索引 MultiIndex (date, asset)，列 open/close/high/low/volume。
    asset 取 underlying_symbol（品种代码）。
    """
    df = pd.read_parquet(FUTURE_PATH)
    df = df.rename(
        columns={
            "datetime": "date",
            "underlying_symbol": "asset",
            "open_price": "open",
            "close_price": "close",
            "high_price": "high",
            "low_price": "low",
        }
    )
    # 去掉时区，统一为 naive 日期
    df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)
    df = df.set_index(["date", "asset"]).sort_index()
    out = df[["open", "close", "high", "low", "volume"]].astype(float)
    logger.info("加载期货数据: %s 行, %d 个品种", len(out), out.index.get_level_values("asset").nunique())
    return out


def list_futures_instruments() -> list[str]:
    """按平均成交量降序返回品种代码列表（供前端默认选最活跃的几个）。"""
    df = load_futures()
    order = (
        df["volume"].groupby(level="asset").mean().sort_values(ascending=False).index.tolist()
    )
    return order
