"""中间结果缓存。

实现"计算工厂"所需的缓存层：以节点签名（``node.key``）为键，
缓存已算出的中间结果。同一份源数据上，相同子表达式只计算一次。

缓存与具体数据绑定：键里混入了数据指纹（``data_id``），
不同 DataFrame 之间不会串用结果。
"""

from __future__ import annotations

from typing import Any, Dict


class ResultCache:
    """简单的进程内字典缓存，附命中/未命中统计（供日志与测试用）。"""

    def __init__(self, data_id: str):
        self.data_id = data_id
        self._store: Dict[str, Any] = {}
        self.hits = 0
        self.misses = 0

    def _full_key(self, node_key: str) -> str:
        return f"{self.data_id}::{node_key}"

    def get(self, node_key: str):
        k = self._full_key(node_key)
        if k in self._store:
            self.hits += 1
            return self._store[k], True
        self.misses += 1
        return None, False

    def put(self, node_key: str, value: Any) -> None:
        self._store[self._full_key(node_key)] = value

    def stats(self) -> dict:
        return {"hits": self.hits, "misses": self.misses, "size": len(self._store)}
