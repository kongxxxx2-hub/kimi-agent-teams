import re

# Ordered list: first match wins
ROLE_RULES = [
    ("reviewer", re.compile(r"review|检查|审核|审查|校验|验证")),
    ("coder", re.compile(r"写|实现|脚本|代码|修改|重构|编写|开发|fix|bug|implement")),
    ("researcher", re.compile(r"搜索|调研|查找|查询|search|research|了解|研究|梳理|整理|消息|动态|趋势")),
    ("analyst", re.compile(r"分析|评估|对比|比较|统计|analyze|测算|估值")),
    ("architect", re.compile(r"设计|架构|方案|规划|design")),
]

# Patterns that suggest multi-step: "do X then Y", "X后Y", "X完Y"
MULTI_STEP_PATTERNS = [
    re.compile(r"然后|之后|接着|再|完了|完后|写完后|做完后|, ?then"),
]

# Keywords that imply deep work → auto-trigger researcher + analyst (2-step)
DEEP_WORK_KEYWORDS = re.compile(r"深入|深度|综合|全面|详细|产业链|竞争格局|投资|估值|对比分析|评估.*价值|分析.*趋势")

DEFAULT_ROLE = "researcher"  # 默认用 researcher 而不是 coder

# Role-specific task enrichment templates
ROLE_TASK_TEMPLATES = {
    "researcher": """请对以下主题进行深度调研，产出一份完整的产业调研报告：

【用户需求】{user_message}

【调研要求】
1. 报告总长度 3000 字以上，覆盖所有关键维度
2. 必须包含：核心结论速读、行业背景、关键事件时间线（表格）、核心玩家对比（表格）、技术路线演进、市场规模预测（表格）、供应链瓶颈、风险分析、趋势判断
3. 至少 3 个数据表格
4. 数据标注时间或来源
5. 用 blockquote 标注关键判断
6. 最后一句话总结核心观点""",

    "analyst": """请对以下主题进行专业分析：

【用户需求】{user_message}

【分析要求】
1. 先明确分析框架和维度
2. 用表格展示核心数据（至少 2 个表格）
3. 多方案对比时用评分矩阵（1-10 分）
4. 所有结论必须有数据支撑
5. 结论放在最前面（倒金字塔结构）
6. 附带风险提示""",

    "reviewer": """请审查以下内容：

【用户需求】{user_message}

【审查要求】
1. 检查准确性、完整性、逻辑性
2. 用表格列出所有发现的问题（严重程度 + 具体问题 + 修改建议）
3. 最后给出总体评价""",

    "coder": "{user_message}",

    "architect": """请对以下需求进行系统设计：

【用户需求】{user_message}

【设计要求】
1. 描述整体架构和关键组件
2. 定义模块间接口和数据流
3. 列出关键设计决策和理由
4. 用文字描述架构图""",
}


def _enrich_task(role, user_message):
    """Enrich the raw user message with role-specific instructions."""
    template = ROLE_TASK_TEMPLATES.get(role, "{user_message}")
    return template.format(user_message=user_message)


def fallback_dispatch(user_message):
    """Return dispatch plan based on keyword matching.
    Detects multi-step patterns like "写代码然后review".
    Returns: single dict or list of dicts with role/task/fallback keys.
    """
    # Check if message contains multi-step indicators or deep work keywords
    has_multi_step = any(p.search(user_message) for p in MULTI_STEP_PATTERNS)
    has_deep_work = bool(DEEP_WORK_KEYWORDS.search(user_message))

    # Deep work keywords auto-trigger researcher + analyst
    if has_deep_work and not has_multi_step:
        return [
            {"role": "researcher", "task": _enrich_task("researcher", user_message), "fallback": True},
            {"role": "analyst", "task": _enrich_task("analyst", user_message), "fallback": True},
        ]

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
                    steps.append({"role": role, "task": _enrich_task(role, user_message), "fallback": True})
            return steps

    # Single step: first match wins
    for role, pattern in ROLE_RULES:
        if pattern.search(user_message):
            return {"role": role, "task": _enrich_task(role, user_message), "fallback": True}
    return {"role": DEFAULT_ROLE, "task": _enrich_task(DEFAULT_ROLE, user_message), "fallback": True}
