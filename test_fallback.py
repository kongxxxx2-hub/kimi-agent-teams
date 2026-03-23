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
    assert fallback_dispatch("了解一下CPO趋势")["role"] == "researcher"
    assert fallback_dispatch("最近光模块消息")["role"] == "researcher"


def test_analyst_keywords():
    assert fallback_dispatch("分析这只股票的走势")["role"] == "analyst"
    assert fallback_dispatch("对比两个方案")["role"] == "analyst"


def test_architect_keywords():
    assert fallback_dispatch("设计系统架构")["role"] == "architect"


def test_default_to_researcher():
    # Default changed from coder to researcher
    assert fallback_dispatch("你好")["role"] == "researcher"


def test_enriched_task():
    # Researcher tasks should be enriched with detailed instructions
    result = fallback_dispatch("调研一下CPO产业")
    assert "3000 字以上" in result["task"]
    assert "核心结论" in result["task"]
    assert "CPO产业" in result["task"]


def test_coder_not_enriched():
    result = fallback_dispatch("写一个选股脚本")
    assert result["task"] == "写一个选股脚本"


def test_multi_step_detection():
    result = fallback_dispatch("写代码然后review")
    assert isinstance(result, list)
    assert len(result) == 2
    assert result[0]["role"] == "coder"
    assert result[1]["role"] == "reviewer"


def test_multi_step_enriched():
    result = fallback_dispatch("调研CPO然后分析投资价值")
    assert isinstance(result, list)
    assert result[0]["role"] == "researcher"
    assert "3000 字以上" in result[0]["task"]
    assert result[1]["role"] == "analyst"
    assert "评分矩阵" in result[1]["task"]


if __name__ == "__main__":
    test_coder_keywords()
    test_reviewer_keywords()
    test_researcher_keywords()
    test_analyst_keywords()
    test_architect_keywords()
    test_default_to_researcher()
    test_enriched_task()
    test_coder_not_enriched()
    test_multi_step_detection()
    test_multi_step_enriched()
    print("All fallback tests passed")
