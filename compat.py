"""pandas 3.0 兼容层。

本地 alphalens 源码在 pandas 3.0 上仅有一处不兼容：
``alphalens/plotting.py`` 调用了 pandas 1.x 时代的 ``DataFrame._append``，
该私有方法已在 pandas 3.0 中移除。

为满足"不修改 alphalens 文件夹"的约束，这里在运行时补回一个等价实现。
任何业务模块在 ``import alphalens`` **之前**先 ``import compat`` 即可。
"""

import pandas as pd


def _install_dataframe_append() -> None:
    """若缺失则补回 DataFrame._append（用 pd.concat 等价实现）。"""
    if hasattr(pd.DataFrame, "_append"):
        return

    def _append(self, other, ignore_index=False, verify_integrity=False, sort=False):
        # alphalens 里 other 既可能是 Series（追加一行）也可能是 DataFrame
        if isinstance(other, pd.Series):
            other = other.to_frame().T
        return pd.concat(
            [self, other],
            ignore_index=ignore_index,
            verify_integrity=verify_integrity,
            sort=sort,
        )

    pd.DataFrame._append = _append


_install_dataframe_append()
