"""计算工厂缓存测试：重复子表达式只计算一次。"""

from engine import Evaluator


def test_cache_reuses_subexpression(small_panel):
    ev = Evaluator(small_panel, data_id="t")
    # 子表达式 mean(close,3) 出现两次，应只计算一次
    ev.evaluate("corr(mean(close,3), mean(close,3), 3)")
    stats = ev.cache.stats()
    # 至少命中一次（第二个 mean(close,3) 命中缓存）
    assert stats["hits"] >= 1


def test_cache_hit_on_repeat_eval(small_panel):
    ev = Evaluator(small_panel, data_id="t")
    ev.evaluate("rank(close)")
    hits_before = ev.cache.hits
    ev.evaluate("rank(close)")  # 整棵树都应命中缓存
    assert ev.cache.hits > hits_before


def test_distinct_subexpr_not_cached(small_panel):
    ev = Evaluator(small_panel, data_id="t")
    ev.evaluate("mean(close,2) + mean(close,3)")
    # 两个不同窗口的 mean 都是 miss
    assert ev.cache.misses >= 2
