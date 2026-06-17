"""统一日志配置。

记录：运行时间、异常信息、输入信息、计算信息等（作业要求项）。
日志同时输出到控制台和 ``logs/app.log``。
"""

import logging
import os
import sys

_LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
_LOG_FILE = os.path.join(_LOG_DIR, "app.log")

_configured = False


def setup_logging(level: int = logging.INFO) -> None:
    """初始化根日志器（幂等，可重复调用）。"""
    global _configured
    if _configured:
        return

    os.makedirs(_LOG_DIR, exist_ok=True)

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root = logging.getLogger()
    root.setLevel(level)

    # 文件 handler（UTF-8，避免中文乱码）
    fh = logging.FileHandler(_LOG_FILE, encoding="utf-8")
    fh.setFormatter(fmt)
    root.addHandler(fh)

    # 控制台 handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(fmt)
    root.addHandler(ch)

    _configured = True


def get_logger(name: str) -> logging.Logger:
    """获取一个已配置的 logger。"""
    setup_logging()
    return logging.getLogger(name)
