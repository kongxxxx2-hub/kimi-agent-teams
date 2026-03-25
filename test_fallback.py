from fallback import fallback_dispatch


def _role(result):
    """Helper: get role from single dict or first item of list."""
    if isinstance(result, list):
        return result[0]["role"]
    return result["role"]


def _is_multi(result):
    return isinstance(result, list)


def test_coder_keywords():
    assert _role(fallback_dispatch("帮我写个选股脚本")) == "coder"
    assert _role(fallback_dispatch("修改 liuban.py")) == "coder"
    assert _role(fallback_dispatch("重构这段代码")) == "coder"


def test_reviewer_keywords():
    assert _role(fallback_dispatch("review 一下这个函数")) == "reviewer"
    assert _role(fallback_dispatch("检查代码质量")) == "reviewer"


def test_researcher_keywords():
    r = fallback_dispatch("搜索一下涨停板规则")
    assert _role(r) == "researcher"


def test_analyst_keywords():
    r = fallback_dispatch("分析这只股票的走势")
    assert _role(r) == "researcher"  # "分析" triggers research_analyze → list
    assert _is_multi(r)


def test_architect_keywords():
    assert _role(fallback_dispatch("设计系统架构")) == "architect"


def test_default_to_researcher():
    assert _role(fallback_dispatch("你好")) == "researcher"


def test_deep_work_triggers_3_steps():
    r = fallback_dispatch("深入调研CPO产业链")
    assert _is_multi(r)
    assert len(r) == 3
    assert r[0]["role"] == "researcher"
    assert r[1]["role"] == "analyst"
    assert r[2]["role"] == "reviewer"


def test_analyze_triggers_2_steps():
    r = fallback_dispatch("分析AI芯片竞争格局")
    assert _is_multi(r)
    assert len(r) == 2
    assert r[0]["role"] == "researcher"
    assert r[1]["role"] == "analyst"


def test_simple_lookup():
    r = fallback_dispatch("查一下今天原油价格")
    assert not _is_multi(r)
    assert r["role"] == "researcher"


def test_implement_review():
    r = fallback_dispatch("写一个MACD函数然后review")
    assert _is_multi(r)
    assert r[0]["role"] == "coder"
    assert r[1]["role"] == "reviewer"


def test_enriched_task():
    r = fallback_dispatch("调研一下CPO产业")
    # Should be multi-step (research_analyze matches "趋势" isn't here, but "调研" matches researcher)
    if _is_multi(r):
        assert "3000 字以上" in r[0]["task"]
    else:
        assert "3000 字以上" in r["task"]


if __name__ == "__main__":
    test_coder_keywords()
    test_reviewer_keywords()
    test_researcher_keywords()
    test_analyst_keywords()
    test_architect_keywords()
    test_default_to_researcher()
    test_deep_work_triggers_3_steps()
    test_analyze_triggers_2_steps()
    test_simple_lookup()
    test_implement_review()
    test_enriched_task()
    print("All fallback tests passed")
