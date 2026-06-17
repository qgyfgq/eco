"""模块一端到端冒烟测试（用真实股票数据，但只验证流程返回结构）。"""

from factor_analysis import run_factor_analysis


def test_factor_analysis_runs():
    res = run_factor_analysis("rank(-close)", quantiles=5, periods=(1,))
    assert res["ok"] is True
    assert len(res["images"]) >= 1            # 至少出一张 tear sheet 图
    assert "ic_summary" in res["tables"]
    assert res["meta"]["n_clean"] > 0


def test_factor_analysis_invalid_expr_returns_error():
    res = run_factor_analysis("bad_fn(close)")
    assert res["ok"] is False
    assert "error" in res
