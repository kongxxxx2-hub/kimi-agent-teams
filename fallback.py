import re

# Ordered list: first match wins
ROLE_RULES = [
    ("reviewer", re.compile(r"review|检查|审核|审查|校验|验证")),
    ("coder", re.compile(r"写|实现|脚本|代码|修改|重构|编写|开发|fix|bug|implement")),
    ("researcher", re.compile(r"搜索|调研|查找|查询|search|research")),
    ("analyst", re.compile(r"分析|评估|对比|比较|统计|analyze")),
    ("architect", re.compile(r"设计|架构|方案|规划|design")),
]

# Patterns that suggest multi-step: "do X then Y", "X后Y", "X完Y"
MULTI_STEP_PATTERNS = [
    re.compile(r"然后|之后|接着|再|完了|完后|写完后|做完后|, ?then"),
]

DEFAULT_ROLE = "coder"


def fallback_dispatch(user_message):
    """Return dispatch plan based on keyword matching.
    Detects multi-step patterns like "写代码然后review".
    Returns: single dict or list of dicts with role/task/fallback keys.
    """
    # Check if message contains multi-step indicators
    has_multi_step = any(p.search(user_message) for p in MULTI_STEP_PATTERNS)

    if has_multi_step:
        # Find ALL matching roles in order of appearance in text
        matched_roles = []
        for role, pattern in ROLE_RULES:
            match = pattern.search(user_message)
            if match:
                matched_roles.append((match.start(), role))

        if len(matched_roles) >= 2:
            # Sort by position in text to get natural order
            matched_roles.sort(key=lambda x: x[0])
            seen = set()
            steps = []
            for _, role in matched_roles:
                if role not in seen:
                    seen.add(role)
                    steps.append({"role": role, "task": user_message, "fallback": True})
            return steps

    # Single step: first match wins
    for role, pattern in ROLE_RULES:
        if pattern.search(user_message):
            return {"role": role, "task": user_message, "fallback": True}
    return {"role": DEFAULT_ROLE, "task": user_message, "fallback": True}
