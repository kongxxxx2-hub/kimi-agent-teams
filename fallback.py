import re

# Ordered list: first match wins
ROLE_RULES = [
    ("reviewer", re.compile(r"review|检查|审核|审查|校验|验证")),
    ("coder", re.compile(r"写|实现|脚本|代码|修改|重构|编写|开发|fix|bug|implement")),
    ("researcher", re.compile(r"搜索|调研|查找|查询|search|research")),
    ("analyst", re.compile(r"分析|评估|对比|比较|统计|analyze")),
    ("architect", re.compile(r"设计|架构|方案|规划|design")),
]

DEFAULT_ROLE = "coder"


def fallback_dispatch(user_message):
    """Return a single-step dispatch plan based on keyword matching.
    Returns: {"role": str, "task": str, "fallback": True}
    """
    for role, pattern in ROLE_RULES:
        if pattern.search(user_message):
            return {"role": role, "task": user_message, "fallback": True}
    return {"role": DEFAULT_ROLE, "task": user_message, "fallback": True}
