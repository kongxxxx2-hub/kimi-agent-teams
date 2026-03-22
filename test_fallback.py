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


def test_first_match_wins():
    # reviewer checked before coder, so "review" wins
    result = fallback_dispatch("写代码然后review")
    assert result["role"] == "reviewer"
    # pure coder task
    result = fallback_dispatch("写一个选股脚本")
    assert result["role"] == "coder"


def test_returns_single_step():
    result = fallback_dispatch("写代码然后review然后分析")
    assert isinstance(result, dict)
    assert "role" in result
    assert "task" in result


if __name__ == "__main__":
    test_coder_keywords()
    test_reviewer_keywords()
    test_researcher_keywords()
    test_analyst_keywords()
    test_architect_keywords()
    test_default_to_coder()
    test_first_match_wins()
    test_returns_single_step()
    print("All fallback tests passed")
