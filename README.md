---
title: 金融量化投资平台
emoji: 📈
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---

# 金融量化投资平台

一个两模块、可相互切换的量化分析平台，前后端分离（HTML+CSS+JS 前端 + Python/FastAPI 后端）。
核心是一个**因子/信号表达式引擎**：把行情字段当操作数、运算当算子，用**解释器模式**解析字符串表达式，
用**计算工厂 + 中间结果缓存**避免重复计算。

- **模块一 · 因子分析**：输入因子表达式 → 引擎求值 → 调用本地 `alphalens` 的
  `create_full_tear_sheet()` 产出完整分析图与 IC/分位/换手指标。
- **模块二 · 策略回测**：输入买入/卖出信号表达式 → 每支期货主力连续合约**各自独立满仓多头**回测
  （只做多/空仓、禁止做空）→ 汇总组合绩效（总收益、年化、最大回撤、胜率、盈亏比、交易次数、权益曲线）。

> 素材文件夹 `alphalens/`、`data1/`、`data2/` 仅作只读使用，**未做任何修改**。

## 目录结构

```
eco/
  app.py                # FastAPI 后端：路由 + 静态 + 启动
  compat.py             # pandas 3.0 兼容 shim（补回 alphalens 用到的 DataFrame._append）
  logging_conf.py       # 统一日志（控制台 + logs/app.log）
  data_loader.py        # 两数据集加载并归一化为 MultiIndex(date, asset)
  factor_analysis.py    # 模块一逻辑
  backtest.py           # 模块二逻辑
  engine/               # 表达式引擎
    operands.py         #   操作数与 AST 节点（Field / Const / Call）
    operators.py        #   算子注册表（element_wise / time_series / cross_sectional）
    parser.py           #   解释器模式：词法 + 递归下降解析
    evaluator.py        #   计算工厂：后序求值 + 缓存
    cache.py            #   中间结果缓存
  static/               # 前端单页（双标签切换）
  tests/                # pytest 单元测试
  alphalens/ data1/ data2/   # 素材（只读，未改动）
```

## 安装

```bash
pip install -r requirements.txt
```

（alphalens 用仓库内置源码，无需单独安装。）

## 运行

```bash
python -m uvicorn app:app --port 8000
```

浏览器打开 <http://127.0.0.1:8000>，顶部标签切换两个模块。

## 测试

```bash
python -m pytest tests/ -q
```

覆盖：三类算子（每类 ≥3 个）、解析器（嵌套/优先级/错误处理）、缓存命中、两模块端到端。

## 表达式语法

- **操作数**：字段 `open close high low volume`，以及数字常量。
- **算子**（嵌套调用）：
  - `element_wise`（逐元素）：`log abs sign sqrt pow if_else min2 max2`
  - `time_series`（按品种沿时间轴滚动/平移）：`mean std sum max min delay shift delta corr cross_up cross_down`
  - `cross_sectional`（按日期跨标的截面）：`rank pctrank zscore demean scale`
- 还支持算术 `+ - * /`、比较 `> <`、逻辑 `&& ||` 与括号。

示例：

| 模块 | 表达式 |
| --- | --- |
| 因子 | `rank(-close)`、`zscore(delta(close,1))`、`corr(close, volume, 6)` |
| 买入信号 | `cross_up(close, mean(close,20))`、`close > mean(close,60)` |
| 卖出信号 | `cross_down(close, mean(close,20))` |

## 设计要点

- **解释器模式**：`engine/parser.py` 自写 tokenizer + 递归下降，将字符串解析为 AST；
  `engine/evaluator.py` 后序遍历求值。全程不使用 `eval`，无注入风险。
- **计算工厂 + 缓存**：每个 AST 节点有规范化签名 `key`，求值前先查 `ResultCache`；
  同一表达式中重复子式（如 `corr(mean(close,5), mean(close,5), 10)`）只计算一次。
  日志会打印缓存命中统计。
- **回测口径**：每支合约独立账户、满仓多头；信号 T 日成立、T+1 开盘成交，规避未来函数；
  末日仍持仓则按最后收盘价平仓计入交易统计；组合权益为各独立账户等权汇总。
- **日志**：记录请求输入、表达式、各阶段耗时、缓存统计、异常 traceback，输出到 `logs/app.log`。
- **错误处理**：表达式语法/语义错误与运行异常都会被捕获并以 `{ok: false, error}` 返回，前端展示。

## 兼容性说明

本地 `alphalens` 为 pandas 1.x 时代代码，在 pandas 3.0 上仅 `plotting.py` 用到的
`DataFrame._append` 被移除。为遵守"不修改素材"约束，`compat.py` 在运行时用 `pd.concat`
等价补回该方法；任何模块在 `import alphalens` 前先 `import compat` 即可。
