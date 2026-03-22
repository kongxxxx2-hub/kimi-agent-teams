from fallback import fallback_dispatch


def test_coder_keywords():
    assert fallback_dispatch("帮我写个选股脚本")["role"] == "coder"
    assert fallback_dispatch("修改 liuban.py")["role"] == "coder"
    assert fallback_dispatch("重构这段代码")["role"] == "coder"


def test_reviewer_keywords():
    assert fallback_dispatch("review 一下这个函数")["role"] == "reviewer"
    assert fallback_dispatch("检查代码质量")["role"] == "reviewer"


def test_researcher_keywords():
    assert fallback_dispatch("搜索一下涨停板规则")["role"] == "researcher"
    assert fallback_dispatch("调研竞品方案")["role"] == "researcher"


def test_analyst_keywords():
    assert fallback_dispatch("分析这只股票的走势")["role"] == "analyst"
    assert fallback_dispatch("对比两个方案")["role"] == "analyst"


def test_architect_keywords():
    assert fallback_dispatch("设计系统架构")["role"] == "architect"


def test_default_to_coder():
    assert fallback_dispatch("你好")["role"] == "coder"
    assert fallback_dispatch("随便做点什么")["role"] == "coder"


def test_first_match_wins_single():
    # pure coder task, no multi-step pattern
    result = fallback_dispatch("写一个选股脚本")
    assert isinstance(result, dict)
    assert result["role"] == "coder"


def test_multi_step_detection():
    # "然后" triggers multi-step: coder first (写), then reviewer (review)
    result = fallback_dispatch("写代码然后review")
    assert isinstance(result, list)
    assert len(result) == 2
    assert result[0]["role"] == "coder"
    assert result[1]["role"] == "reviewer"


def test_multi_step_three_roles():
    result = fallback_dispatch("写代码然后review然后分析")
    assert isinstance(result, list)
    assert len(result) == 3
    assert result[0]["role"] == "coder"
    assert result[1]["role"] == "reviewer"
    assert result[2]["role"] == "analyst"


def test_multi_step_with_after():
    result = fallback_dispatch("写完后让reviewer审查")
    assert isinstance(result, list)
    assert len(result) == 2
    assert result[0]["role"] == "coder"
    assert result[1]["role"] == "reviewer"


if __name__ == "__main__":
    test_coder_keywords()
    test_reviewer_keywords()
    test_researcher_keywords()
    test_analyst_keywords()
    test_architect_keywords()
    test_default_to_coder()
    test_first_match_wins_single()
    test_multi_step_detection()
    test_multi_step_three_roles()
    test_multi_step_with_after()
    print("All fallback tests passed")
