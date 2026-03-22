# Agent Teams V2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python-based multi-agent task dispatch system that receives tasks via Clawdbot Leader agent, splits them into role-based steps via k2p5, executes each step via OpenResponses API, and displays concise summaries in Telegram group chat.

**Architecture:** A Python dispatcher script serves as the central coordinator. It registers as a Clawdbot skill (dispatch_task tool) for the Leader agent. When invoked, it calls the OpenResponses API to analyze tasks and execute role-based steps sequentially. Each role bot posts a one-line summary to the Telegram group. Full logs go to SQLite.

**Tech Stack:** Python 3, requests, SQLite3 (stdlib), Clawdbot Gateway OpenResponses API

**Spec:** `docs/superpowers/specs/2026-03-22-agent-teams-v2-design.md`

---

## File Map

| File | Responsibility |
|------|---------------|
| `~/Desktop/agent-teams/config.json` | All configuration: gateway, telegram bots, dispatcher settings |
| `~/Desktop/agent-teams/db.py` | SQLite schema + CRUD for tasks and steps |
| `~/Desktop/agent-teams/gateway_client.py` | OpenResponses API client (POST /v1/responses) |
| `~/Desktop/agent-teams/fallback.py` | Keyword-based role matching when k2p5 fails |
| `~/Desktop/agent-teams/telegram_display.py` | Send concise summaries via role bot tokens |
| `~/Desktop/agent-teams/dispatcher.py` | Core orchestrator: analyze → dispatch → collect → summarize |
| `~/Desktop/agent-teams/roles/coder.md` | Coder system prompt |
| `~/Desktop/agent-teams/roles/reviewer.md` | Reviewer system prompt |
| `~/Desktop/agent-teams/roles/researcher.md` | Researcher system prompt |
| `~/Desktop/agent-teams/roles/analyst.md` | Analyst system prompt |
| `~/Desktop/agent-teams/roles/architect.md` | Architect system prompt |
| `~/.clawdbot/skills/agent-teams/SKILL.md` | Skill doc for Leader LLM |
| `~/.clawdbot/skills/agent-teams/_meta.json` | Skill registry metadata |
| `~/.clawdbot/skills/agent-teams/dispatch.sh` | Shell wrapper calling dispatcher.py |
| `~/.clawdbot/agents/main/SOUL.md` | Updated Leader persona (replaces 太子) |

---

### Task 1: Project Setup — venv, config, git init

**Files:**
- Create: `~/Desktop/agent-teams/requirements.txt`
- Create: `~/Desktop/agent-teams/config.json`
- Create: `~/Desktop/agent-teams/.gitignore`

- [ ] **Step 1: Initialize git repo**

```bash
cd ~/Desktop/agent-teams
git init
```

- [ ] **Step 2: Create .gitignore**

```
venv/
data/
__pycache__/
*.pyc
config.json
```

Note: config.json is gitignored because it contains bot tokens. A config.example.json will be committed instead.

- [ ] **Step 3: Create venv and install dependencies**

```bash
cd ~/Desktop/agent-teams
python3 -m venv venv
source venv/bin/activate
pip install requests
pip freeze > requirements.txt
```

- [ ] **Step 4: Create config.json with real values**

Read gateway token from `~/.clawdbot/clawdbot.json` (line 141): `<gateway-token>`
Read bot tokens from `~/.clawdbot/clawdbot.json` (lines 106, 109).
5 role bot tokens need to be obtained from user — use placeholders for now.

```json
{
  "gateway": {
    "url": "http://localhost:18789",
    "token": "<gateway-token>"
  },
  "telegram": {
    "group_chat_id": "-1003716709219",
    "bots": {
      "private-bot": {"token": "<bob-bot-token>"},
      "leader": {"token": "<leader-bot-token>"},
      "coder": {"token": "TODO"},
      "reviewer": {"token": "TODO"},
      "researcher": {"token": "TODO"},
      "analyst": {"token": "TODO"},
      "architect": {"token": "TODO"}
    }
  },
  "dispatcher": {
    "model": "kimi-coding/k2p5",
    "max_steps": 5,
    "step_timeout_seconds": 120,
    "max_context_bytes": 153600
  }
}
```

- [ ] **Step 5: Create config.example.json (committed to git)**

Same structure but with all tokens replaced by `"<your-token-here>"`.

- [ ] **Step 6: Create data/ directory**

```bash
mkdir -p ~/Desktop/agent-teams/data
```

- [ ] **Step 7: Commit**

```bash
cd ~/Desktop/agent-teams
git add .gitignore requirements.txt config.example.json
git commit -m "init: project setup with venv and config"
```

---

### Task 2: SQLite Database Layer (db.py)

**Files:**
- Create: `~/Desktop/agent-teams/db.py`
- Create: `~/Desktop/agent-teams/test_db.py`

- [ ] **Step 1: Write test for db module**

```python
# test_db.py
import os
import tempfile
from db import Database

def test_create_task_and_steps():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        db = Database(db_path)
        task_id = db.create_task("AT-20260322-001", "帮我写个脚本", '{"steps":[]}')
        assert task_id == "AT-20260322-001"

        task = db.get_task(task_id)
        assert task["status"] == "pending"
        assert task["user_message"] == "帮我写个脚本"

        db.update_task_status(task_id, "running")
        task = db.get_task(task_id)
        assert task["status"] == "running"

        db.create_step(task_id, 1, "coder", "写代码", "代码写好了", 500, 3000, "completed")
        steps = db.get_steps(task_id)
        assert len(steps) == 1
        assert steps[0]["role"] == "coder"
        assert steps[0]["tokens_used"] == 500

        db.update_task_status(task_id, "completed")
        task = db.get_task(task_id)
        assert task["status"] == "completed"
        assert task["completed_at"] is not None
    finally:
        os.unlink(db_path)

def test_generate_task_id():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        db = Database(db_path)
        tid1 = db.generate_task_id()
        assert tid1.startswith("AT-")
        tid2 = db.generate_task_id()
        assert tid1 != tid2
    finally:
        os.unlink(db_path)

if __name__ == "__main__":
    test_create_task_and_steps()
    test_generate_task_id()
    print("All db tests passed")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd ~/Desktop/agent-teams && venv/bin/python test_db.py
```

Expected: ModuleNotFoundError for db

- [ ] **Step 3: Implement db.py**

```python
# db.py
import sqlite3
from datetime import datetime


class Database:
    def __init__(self, db_path="data/agent_teams.db"):
        self.db_path = db_path
        self._init_tables()

    def _conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_tables(self):
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    user_message TEXT NOT NULL,
                    dispatch_plan TEXT,
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS steps (
                    step_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL REFERENCES tasks(task_id),
                    step_order INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    input_prompt TEXT,
                    output TEXT,
                    tokens_used INTEGER DEFAULT 0,
                    duration_ms INTEGER DEFAULT 0,
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

    def generate_task_id(self):
        now = datetime.now()
        date_str = now.strftime("%Y%m%d")
        with self._conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) as c FROM tasks WHERE task_id LIKE ?",
                (f"AT-{date_str}-%",)
            ).fetchone()
            seq = (row["c"] or 0) + 1
        return f"AT-{date_str}-{seq:03d}"

    def create_task(self, task_id, user_message, dispatch_plan=None):
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO tasks (task_id, user_message, dispatch_plan) VALUES (?, ?, ?)",
                (task_id, user_message, dispatch_plan)
            )
        return task_id

    def get_task(self, task_id):
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
        return dict(row) if row else None

    def update_task_status(self, task_id, status):
        completed_at = datetime.now().isoformat() if status in ("completed", "failed", "partial") else None
        with self._conn() as conn:
            if completed_at:
                conn.execute(
                    "UPDATE tasks SET status = ?, completed_at = ? WHERE task_id = ?",
                    (status, completed_at, task_id)
                )
            else:
                conn.execute(
                    "UPDATE tasks SET status = ? WHERE task_id = ?",
                    (status, task_id)
                )

    def create_step(self, task_id, step_order, role, input_prompt, output, tokens_used, duration_ms, status):
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO steps (task_id, step_order, role, input_prompt, output, tokens_used, duration_ms, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (task_id, step_order, role, input_prompt, output, tokens_used, duration_ms, status)
            )

    def get_steps(self, task_id):
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM steps WHERE task_id = ? ORDER BY step_order", (task_id,)
            ).fetchall()
        return [dict(r) for r in rows]
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd ~/Desktop/agent-teams && venv/bin/python test_db.py
```

Expected: "All db tests passed"

- [ ] **Step 5: Commit**

```bash
cd ~/Desktop/agent-teams
git add db.py test_db.py
git commit -m "feat: add SQLite database layer for tasks and steps"
```

---

### Task 3: Gateway Client (gateway_client.py)

**Files:**
- Create: `~/Desktop/agent-teams/gateway_client.py`
- Create: `~/Desktop/agent-teams/test_gateway_client.py`

- [ ] **Step 1: Write test for gateway client**

```python
# test_gateway_client.py
import json
from unittest.mock import patch, MagicMock
from gateway_client import GatewayClient

def test_call_success():
    client = GatewayClient("http://localhost:18789", "fake-token", "kimi-coding/k2p5")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "id": "resp_123",
        "status": "completed",
        "output": [
            {
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": "Hello world"}]
            }
        ],
        "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}
    }

    with patch("requests.post", return_value=mock_resp) as mock_post:
        result = client.call("You are a coder", "Write hello world")
        assert result["text"] == "Hello world"
        assert result["tokens"] == 15
        assert result["status"] == "completed"

        call_args = mock_post.call_args
        body = call_args[1]["json"]
        assert body["instructions"] == "You are a coder"
        assert body["input"][0]["content"] == "Write hello world"

def test_call_failure():
    client = GatewayClient("http://localhost:18789", "fake-token", "kimi-coding/k2p5")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "id": "resp_456",
        "status": "failed",
        "output": [],
        "usage": {"input_tokens": 10, "output_tokens": 0, "total_tokens": 10}
    }

    with patch("requests.post", return_value=mock_resp):
        result = client.call("system", "task")
        assert result["status"] == "failed"
        assert result["text"] == ""

def test_call_timeout():
    client = GatewayClient("http://localhost:18789", "fake-token", "kimi-coding/k2p5", timeout=5)

    import requests
    with patch("requests.post", side_effect=requests.Timeout("timeout")):
        result = client.call("system", "task")
        assert result["status"] == "timeout"
        assert result["text"] == ""

if __name__ == "__main__":
    test_call_success()
    test_call_failure()
    test_call_timeout()
    print("All gateway_client tests passed")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd ~/Desktop/agent-teams && venv/bin/python test_gateway_client.py
```

Expected: ModuleNotFoundError

- [ ] **Step 3: Implement gateway_client.py**

```python
# gateway_client.py
import requests


class GatewayClient:
    def __init__(self, url, token, model, timeout=120):
        self.url = url.rstrip("/")
        self.token = token
        self.model = model
        self.timeout = timeout

    def call(self, system_prompt, user_message):
        """Call OpenResponses API. Returns dict with text, tokens, status, duration_ms."""
        import time
        start = time.time()

        try:
            resp = requests.post(
                f"{self.url}/v1/responses",
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "stream": False,
                    "instructions": system_prompt,
                    "input": [
                        {
                            "type": "message",
                            "role": "user",
                            "content": user_message,
                        }
                    ],
                    "max_output_tokens": 32768,
                },
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.Timeout:
            return {"text": "", "tokens": 0, "status": "timeout",
                    "duration_ms": int((time.time() - start) * 1000)}
        except requests.RequestException as e:
            return {"text": "", "tokens": 0, "status": "error",
                    "duration_ms": int((time.time() - start) * 1000), "error": str(e)}

        duration_ms = int((time.time() - start) * 1000)
        status = data.get("status", "unknown")
        tokens = data.get("usage", {}).get("total_tokens", 0)

        text = ""
        for output_item in data.get("output", []):
            if output_item.get("type") == "message":
                for part in output_item.get("content", []):
                    if part.get("type") == "output_text":
                        text += part.get("text", "")

        return {"text": text, "tokens": tokens, "status": status, "duration_ms": duration_ms}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd ~/Desktop/agent-teams && venv/bin/python test_gateway_client.py
```

Expected: "All gateway_client tests passed"

- [ ] **Step 5: Commit**

```bash
cd ~/Desktop/agent-teams
git add gateway_client.py test_gateway_client.py
git commit -m "feat: add Gateway OpenResponses API client"
```

---

### Task 4: Fallback Rules (fallback.py)

**Files:**
- Create: `~/Desktop/agent-teams/fallback.py`
- Create: `~/Desktop/agent-teams/test_fallback.py`

- [ ] **Step 1: Write test**

```python
# test_fallback.py
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
    # "写代码然后review" — first match is coder
    result = fallback_dispatch("写代码然后review")
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd ~/Desktop/agent-teams && venv/bin/python test_fallback.py
```

- [ ] **Step 3: Implement fallback.py**

```python
# fallback.py
import re

# Ordered list: first match wins
ROLE_RULES = [
    ("coder", re.compile(r"写|实现|脚本|代码|修改|重构|编写|开发|fix|bug|implement")),
    ("reviewer", re.compile(r"review|检查|审核|审查|校验|验证")),
    ("researcher", re.compile(r"查|搜索|调研|找|search|research")),
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
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd ~/Desktop/agent-teams && venv/bin/python test_fallback.py
```

Expected: "All fallback tests passed"

- [ ] **Step 5: Commit**

```bash
cd ~/Desktop/agent-teams
git add fallback.py test_fallback.py
git commit -m "feat: add keyword-based fallback dispatch rules"
```

---

### Task 5: Telegram Display (telegram_display.py)

**Files:**
- Create: `~/Desktop/agent-teams/telegram_display.py`
- Create: `~/Desktop/agent-teams/test_telegram_display.py`

- [ ] **Step 1: Write test**

```python
# test_telegram_display.py
from unittest.mock import patch, MagicMock, AsyncMock
import asyncio
from telegram_display import TelegramDisplay

def test_format_step_summary():
    td = TelegramDisplay({}, "-1003716709219")
    summary = td.format_step_summary("coder", "重构 liuban.py 选股逻辑", "已完成重构，新增3个筛选条件")
    assert "✓" in summary
    assert len(summary) < 200  # concise

def test_format_task_start():
    td = TelegramDisplay({}, "-1003716709219")
    msg = td.format_task_start("AT-20260322-001", "重构选股脚本并 review", ["coder", "reviewer"])
    assert "AT-20260322-001" in msg
    assert "coder" in msg.lower() or "Coder" in msg

def test_format_task_end():
    td = TelegramDisplay({}, "-1003716709219")
    msg = td.format_task_end("AT-20260322-001", "completed", 2)
    assert "AT-20260322-001" in msg

def test_format_fallback_warning():
    td = TelegramDisplay({}, "-1003716709219")
    msg = td.format_fallback_warning()
    assert "⚠" in msg

if __name__ == "__main__":
    test_format_step_summary()
    test_format_task_start()
    test_format_task_end()
    test_format_fallback_warning()
    print("All telegram_display tests passed")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd ~/Desktop/agent-teams && venv/bin/python test_telegram_display.py
```

- [ ] **Step 3: Implement telegram_display.py**

```python
# telegram_display.py
import requests


class TelegramDisplay:
    """Send concise summaries to Telegram group chat via bot tokens."""

    TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"

    def __init__(self, bot_tokens, group_chat_id):
        """
        bot_tokens: dict like {"coder": "token...", "leader": "token...", ...}
        group_chat_id: str like "-1003716709219"
        """
        self.bot_tokens = bot_tokens
        self.group_chat_id = group_chat_id

    def format_step_summary(self, role, task_brief, result_brief):
        return f"✓ {task_brief} — {result_brief}"

    def format_task_start(self, task_id, summary, roles):
        role_chain = " → ".join(r.capitalize() for r in roles)
        return f"📋 {task_id}: {summary}\n流程: {role_chain}"

    def format_task_end(self, task_id, status, step_count):
        status_icon = "✓" if status == "completed" else "✗"
        return f"{status_icon} {task_id} 完成，共 {step_count} 步"

    def format_fallback_warning(self):
        return "⚠ 自动分析失败，使用规则分派"

    def format_error(self, task_id, step_order, role, error_msg):
        return f"✗ {task_id} 步骤 {step_order} ({role}) 失败: {error_msg}"

    def send(self, role, text, dry_run=False):
        """Send message to group chat using the specified role's bot token.
        Falls back to 'leader' token if role token not found.
        """
        if dry_run:
            print(f"[{role}] {text}")
            return True

        token = self.bot_tokens.get(role) or self.bot_tokens.get("leader")
        if not token or token == "TODO":
            print(f"[DRY-{role}] {text}")
            return False

        try:
            resp = requests.post(
                self.TELEGRAM_API.format(token=token),
                json={"chat_id": self.group_chat_id, "text": text},
                timeout=10,
            )
            return resp.ok
        except requests.RequestException:
            return False
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd ~/Desktop/agent-teams && venv/bin/python test_telegram_display.py
```

Expected: "All telegram_display tests passed"

- [ ] **Step 5: Commit**

```bash
cd ~/Desktop/agent-teams
git add telegram_display.py test_telegram_display.py
git commit -m "feat: add Telegram group chat display with concise summaries"
```

---

### Task 6: Role System Prompts (roles/*.md)

**Files:**
- Create: `~/Desktop/agent-teams/roles/coder.md`
- Create: `~/Desktop/agent-teams/roles/reviewer.md`
- Create: `~/Desktop/agent-teams/roles/researcher.md`
- Create: `~/Desktop/agent-teams/roles/analyst.md`
- Create: `~/Desktop/agent-teams/roles/architect.md`

- [ ] **Step 1: Create roles/ directory and all 5 prompt files**

**roles/coder.md:**
```markdown
你是 Coder，一个专业的软件开发者。

## 职责
- 编写、修改、重构代码
- 修复 bug
- 实现新功能

## 输出要求
- 输出完整的可运行代码，不要省略
- 代码前后加上文件路径说明
- 最后用一句话总结你做了什么改动

## 环境
- Python 项目为主
- 量化交易系统相关
- 使用 python 运行
```

**roles/reviewer.md:**
```markdown
你是 Reviewer，一个严格的代码审查者。

## 职责
- 审查代码的正确性、可读性、安全性
- 发现潜在 bug 和逻辑错误
- 提出具体的改进建议

## 输出要求
- 列出发现的问题（如有），按严重程度排序
- 每个问题给出具体的修改建议
- 最后给出总体评价：通过 / 需修改 / 不通过
- 一句话总结 review 结论
```

**roles/researcher.md:**
```markdown
你是 Researcher，一个信息搜索和整理专家。

## 职责
- 搜索和整理相关信息
- 总结技术文档和资料
- 提供背景知识和参考

## 输出要求
- 结构化呈现搜索结果
- 标注信息来源
- 最后一句话总结关键发现
```

**roles/analyst.md:**
```markdown
你是 Analyst，一个数据分析和方案评估专家。

## 职责
- 分析数据和趋势
- 评估和对比不同方案
- 提供量化的分析结论

## 输出要求
- 用数据说话，避免主观判断
- 对比分析用表格呈现
- 最后一句话总结分析结论
```

**roles/architect.md:**
```markdown
你是 Architect，一个系统设计和架构专家。

## 职责
- 设计系统架构和模块划分
- 定义接口和数据流
- 评估技术选型

## 输出要求
- 用文字描述架构，标注关键组件和数据流向
- 列出关键设计决策和理由
- 最后一句话总结架构方案
```

- [ ] **Step 2: Commit**

```bash
cd ~/Desktop/agent-teams
git add roles/
git commit -m "feat: add role system prompts for 5 agent roles"
```

---

### Task 7: Core Dispatcher (dispatcher.py)

This is the core module. It ties everything together.

**Files:**
- Create: `~/Desktop/agent-teams/dispatcher.py`
- Create: `~/Desktop/agent-teams/test_dispatcher.py`

- [ ] **Step 1: Write test for dispatcher**

```python
# test_dispatcher.py
import os
import json
import tempfile
from unittest.mock import patch, MagicMock
from dispatcher import Dispatcher

MOCK_CONFIG = {
    "gateway": {"url": "http://localhost:18789", "token": "fake"},
    "telegram": {
        "group_chat_id": "-1003716709219",
        "bots": {"leader": {"token": "fake"}, "coder": {"token": "fake"}, "reviewer": {"token": "fake"},
                 "researcher": {"token": "fake"}, "analyst": {"token": "fake"}, "architect": {"token": "fake"}}
    },
    "dispatcher": {"model": "kimi-coding/k2p5", "max_steps": 5, "step_timeout_seconds": 120, "max_context_bytes": 153600}
}

def make_dispatcher(db_path):
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(MOCK_CONFIG, f)
        config_path = f.name
    return Dispatcher(config_path=config_path, db_path=db_path, dry_run=True, roles_dir=os.path.join(os.path.dirname(__file__), "roles"))

def test_parse_dispatch_plan_valid():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        d = make_dispatcher(db_path)
        plan_json = json.dumps({
            "summary": "写代码并review",
            "steps": [
                {"role": "coder", "task": "写脚本"},
                {"role": "reviewer", "task": "审查代码"}
            ]
        })
        plan = d.parse_dispatch_plan(plan_json)
        assert plan is not None
        assert len(plan["steps"]) == 2
        assert plan["steps"][0]["role"] == "coder"
    finally:
        os.unlink(db_path)

def test_parse_dispatch_plan_invalid():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        d = make_dispatcher(db_path)
        assert d.parse_dispatch_plan("not json") is None
        assert d.parse_dispatch_plan('{"steps":"not a list"}') is None
        assert d.parse_dispatch_plan('{"steps":[{"role":"unknown","task":"x"}]}') is None
    finally:
        os.unlink(db_path)

def test_parse_dispatch_plan_max_steps():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        d = make_dispatcher(db_path)
        plan_json = json.dumps({
            "summary": "big task",
            "steps": [{"role": "coder", "task": f"step {i}"} for i in range(10)]
        })
        plan = d.parse_dispatch_plan(plan_json)
        assert len(plan["steps"]) == 5  # capped at max_steps
    finally:
        os.unlink(db_path)

def test_read_context_files():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write("print('hello')\n" * 10)
        tmp_file = f.name
    try:
        d = make_dispatcher(db_path)
        context = d.read_context_files([tmp_file, "/nonexistent/file.py"])
        assert "hello" in context
        assert "/nonexistent" not in context or "跳过" in context or context.count("hello") > 0
    finally:
        os.unlink(db_path)
        os.unlink(tmp_file)

if __name__ == "__main__":
    test_parse_dispatch_plan_valid()
    test_parse_dispatch_plan_invalid()
    test_parse_dispatch_plan_max_steps()
    test_read_context_files()
    print("All dispatcher tests passed")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd ~/Desktop/agent-teams && venv/bin/python test_dispatcher.py
```

- [ ] **Step 3: Implement dispatcher.py**

```python
# dispatcher.py
"""Agent Teams V2 — Core Dispatcher

Usage:
    venv/bin/python dispatcher.py "任务描述"
    venv/bin/python dispatcher.py --dry-run "任务描述"
"""
import json
import os
import re
import sys

from db import Database
from gateway_client import GatewayClient
from fallback import fallback_dispatch
from telegram_display import TelegramDisplay

VALID_ROLES = {"coder", "reviewer", "researcher", "analyst", "architect"}

ANALYSIS_PROMPT = """你是一个任务分析器。分析用户的任务，输出一个 JSON 分派计划。

规则：
- 拆分为 1-5 个步骤
- 每个步骤指定一个角色: coder, reviewer, researcher, analyst, architect
- 步骤按执行顺序排列
- 如果任务提到文件路径，放在 context_files 数组里

只输出 JSON，不要其他文字。格式：
{
  "summary": "一句话总结任务",
  "steps": [
    {"role": "coder", "task": "具体任务描述", "context_files": ["/path/to/file"]}
  ]
}"""


class Dispatcher:
    def __init__(self, config_path="config.json", db_path="data/agent_teams.db",
                 dry_run=False, roles_dir="roles"):
        with open(config_path) as f:
            self.config = json.load(f)

        self.db = Database(db_path)
        self.dry_run = dry_run
        self.roles_dir = roles_dir

        gw = self.config["gateway"]
        disp = self.config["dispatcher"]
        self.client = GatewayClient(gw["url"], gw["token"], disp["model"], disp["step_timeout_seconds"])
        self.max_steps = disp["max_steps"]
        self.max_context_bytes = disp["max_context_bytes"]

        bot_tokens = {name: info["token"] for name, info in self.config["telegram"]["bots"].items()}
        group_id = self.config["telegram"]["group_chat_id"]
        self.display = TelegramDisplay(bot_tokens, group_id)

    def parse_dispatch_plan(self, raw_text):
        """Parse k2p5's response into a dispatch plan. Returns None if invalid."""
        # Try to extract JSON from the response (k2p5 might wrap it in markdown)
        json_match = re.search(r'\{[\s\S]*\}', raw_text)
        if not json_match:
            return None

        try:
            plan = json.loads(json_match.group())
        except json.JSONDecodeError:
            return None

        if not isinstance(plan.get("steps"), list) or len(plan["steps"]) == 0:
            return None

        # Validate roles
        for step in plan["steps"]:
            if step.get("role") not in VALID_ROLES:
                return None
            if not step.get("task"):
                return None

        # Cap steps
        if len(plan["steps"]) > self.max_steps:
            plan["steps"] = plan["steps"][:self.max_steps]

        return plan

    def read_context_files(self, file_paths):
        """Read files and return combined context string."""
        parts = []
        total_bytes = 0
        max_per_file = 50 * 1024  # 50KB

        for path in file_paths:
            if not os.path.isfile(path):
                continue
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read(max_per_file)
                size = len(content.encode("utf-8"))
                if total_bytes + size > self.max_context_bytes:
                    break
                total_bytes += size
                parts.append(f"--- {path} ---\n{content}")
            except OSError:
                continue

        return "\n\n".join(parts)

    def load_role_prompt(self, role):
        """Load system prompt for a role from roles/*.md."""
        path = os.path.join(self.roles_dir, f"{role}.md")
        if os.path.isfile(path):
            with open(path, "r") as f:
                return f.read()
        return f"你是 {role}，请完成用户给你的任务。"

    def analyze_task(self, user_message):
        """Use k2p5 to analyze task and create dispatch plan. Falls back to keywords."""
        result = self.client.call(ANALYSIS_PROMPT, user_message)

        if result["status"] == "completed":
            plan = self.parse_dispatch_plan(result["text"])
            if plan:
                return plan, False  # (plan, is_fallback)

        # Fallback
        step = fallback_dispatch(user_message)
        return {
            "summary": user_message[:50],
            "steps": [step],
        }, True

    def execute(self, user_message):
        """Main entry point: analyze task, dispatch to roles, collect results."""
        task_id = self.db.generate_task_id()

        # 1. Analyze
        plan, is_fallback = self.analyze_task(user_message)
        self.db.create_task(task_id, user_message, json.dumps(plan, ensure_ascii=False))
        self.db.update_task_status(task_id, "running")

        roles = [s["role"] for s in plan["steps"]]
        self.display.send("leader", self.display.format_task_start(
            task_id, plan.get("summary", user_message[:50]), roles
        ), dry_run=self.dry_run)

        if is_fallback:
            self.display.send("leader", self.display.format_fallback_warning(), dry_run=self.dry_run)

        # 2. Execute steps sequentially
        previous_output = ""
        completed_steps = 0
        final_status = "completed"

        for i, step in enumerate(plan["steps"]):
            role = step["role"]
            task_desc = step["task"]
            context_files = step.get("context_files", [])

            # Build user message for this role
            role_input_parts = [f"任务: {task_desc}"]
            if context_files:
                file_context = self.read_context_files(context_files)
                if file_context:
                    role_input_parts.append(f"相关文件:\n{file_context}")
            if previous_output:
                role_input_parts.append(f"上一步 ({plan['steps'][i-1]['role']}) 的输出:\n{previous_output}")

            role_input = "\n\n".join(role_input_parts)
            system_prompt = self.load_role_prompt(role)

            # Call API
            result = self.client.call(system_prompt, role_input)

            # Record step
            self.db.create_step(
                task_id, i + 1, role, role_input, result["text"],
                result.get("tokens", 0), result.get("duration_ms", 0), result["status"]
            )

            if result["status"] != "completed" or not result["text"]:
                error_msg = result.get("error", result["status"])
                self.display.send("leader", self.display.format_error(
                    task_id, i + 1, role, error_msg
                ), dry_run=self.dry_run)
                final_status = "partial" if completed_steps > 0 else "failed"
                break

            # Send concise summary to group
            # Extract last line as summary (role prompts ask for one-line summary at end)
            lines = result["text"].strip().split("\n")
            summary_line = lines[-1] if lines else result["text"][:100]
            self.display.send(role, self.display.format_step_summary(
                role, task_desc[:30], summary_line[:100]
            ), dry_run=self.dry_run)

            previous_output = result["text"]
            completed_steps += 1

        # 3. Finalize
        self.db.update_task_status(task_id, final_status)
        self.display.send("leader", self.display.format_task_end(
            task_id, final_status, completed_steps
        ), dry_run=self.dry_run)

        return {
            "task_id": task_id,
            "status": final_status,
            "steps_completed": completed_steps,
            "final_output": previous_output,
        }


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Agent Teams V2 Dispatcher")
    parser.add_argument("message", help="Task message to dispatch")
    parser.add_argument("--dry-run", action="store_true", help="Print to stdout instead of Telegram")
    parser.add_argument("--config", default="config.json", help="Config file path")
    parser.add_argument("--db", default="data/agent_teams.db", help="Database file path")
    args = parser.parse_args()

    # Ensure data dir exists
    os.makedirs(os.path.dirname(args.db) or ".", exist_ok=True)

    dispatcher = Dispatcher(
        config_path=args.config,
        db_path=args.db,
        dry_run=args.dry_run,
        roles_dir=os.path.join(os.path.dirname(os.path.abspath(__file__)), "roles"),
    )
    result = dispatcher.execute(args.message)

    if args.dry_run:
        print(f"\n--- Result ---")
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd ~/Desktop/agent-teams && venv/bin/python test_dispatcher.py
```

Expected: "All dispatcher tests passed"

- [ ] **Step 5: Run dry-run integration test against live Gateway**

```bash
cd ~/Desktop/agent-teams && venv/bin/python dispatcher.py --dry-run "帮我写一个 hello world 脚本"
```

Expected: Prints task flow to stdout — analysis, role dispatch, summaries. Verify it works end-to-end with real k2p5 before adding Telegram.

- [ ] **Step 6: Commit**

```bash
cd ~/Desktop/agent-teams
git add dispatcher.py test_dispatcher.py
git commit -m "feat: add core dispatcher with task analysis, role execution, and dry-run mode"
```

---

### Task 8: Clawdbot Skill Registration

**Files:**
- Create: `~/.clawdbot/skills/agent-teams/_meta.json`
- Create: `~/.clawdbot/skills/agent-teams/SKILL.md`
- Create: `~/.clawdbot/skills/agent-teams/dispatch.sh`
- Modify: `~/.clawdbot/agents/main/SOUL.md`

- [ ] **Step 1: Create skill directory**

```bash
mkdir -p ~/.clawdbot/skills/agent-teams
```

- [ ] **Step 2: Create _meta.json**

```json
{
  "owner": "ik",
  "slug": "agent-teams",
  "displayName": "Agent Teams Dispatcher",
  "latest": {
    "version": "1.0.0"
  }
}
```

- [ ] **Step 3: Create SKILL.md**

```markdown
---
name: agent-teams
description: 多 Agent 任务分派系统，将复杂任务拆分给不同角色 agent 执行
---

# Agent Teams — 任务分派

当用户给你一个复杂任务（需要多步骤或多角色协作），使用 dispatch 命令分派任务。

## 使用方式

```bash
bash {baseDir}/dispatch.sh "用户的任务描述"
```

## 什么时候使用

- 用户明确要求多步骤协作（"写代码然后 review"）
- 任务涉及多个角色（coding + analysis + review）
- 用户说"分派"、"dispatch"、"团队处理"

## 什么时候不使用

- 简单闲聊和问答
- 单步骤简单任务（直接回答即可）
```

- [ ] **Step 4: Create dispatch.sh**

```bash
#!/bin/bash
cd ~/agent-teams
exec venv/bin/python dispatcher.py "$@"
```

```bash
chmod +x ~/.clawdbot/skills/agent-teams/dispatch.sh
```

- [ ] **Step 5: Update Leader SOUL.md**

Read current SOUL.md first, then replace with Leader dispatcher persona. Keep it concise:

```markdown
# Leader Agent

你是 Leader，Agent Teams 的调度者。

## 核心职责

1. **消息分类**：判断用户消息是闲聊还是任务
2. **闲聊**：直接简洁回复
3. **任务**：调用 agent-teams skill 的 dispatch 命令分派任务

## 判断标准

- 闲聊：问候、简单问答、不需要动手的对话
- 任务：需要写代码、分析、调研、review 等具体工作

## 回复风格

- 简洁直接
- 不用感叹号
- 中文为主
```

- [ ] **Step 6: Fix Leader agent binding in clawdbot.json**

Current binding has `"agentId": "leader"` but no `leader` agent exists. Change to `"agentId": "main"`:

In `~/.clawdbot/clawdbot.json` line 129, change:
```json
"agentId": "leader"
```
to:
```json
"agentId": "main"
```

**Important:** This change requires restarting the Clawdbot gateway to take effect.

- [ ] **Step 7: Commit skill files**

```bash
cd ~/.clawdbot
git add skills/agent-teams/ agents/main/SOUL.md 2>/dev/null || true
```

Note: If ~/.clawdbot is not a git repo, just verify files are in place.

---

### Task 9: Get Role Bot Tokens and Add to Group

This is a manual/interactive task.

- [ ] **Step 1: Get 5 role bot tokens**

User needs to provide the bot tokens for: Coder, Reviewer, Researcher, Analyst, Architect.
These bots were "already created" per memory. Check BotFather for their tokens.

Ask user to run:
```
In Telegram, message @BotFather:
/mybots → select each role bot → API Token
```

- [ ] **Step 2: Add role bots to group chat**

Each of the 5 bots needs to be added to the group chat (-1003716709219) as members with permission to send messages.

- [ ] **Step 3: Update config.json with real tokens**

Replace the `"TODO"` values in config.json with the real bot tokens.

- [ ] **Step 4: Test Telegram sending**

```bash
cd ~/Desktop/agent-teams
venv/bin/python -c "
from telegram_display import TelegramDisplay
import json
with open('config.json') as f:
    config = json.load(f)
bots = {k: v['token'] for k, v in config['telegram']['bots'].items()}
td = TelegramDisplay(bots, config['telegram']['group_chat_id'])
td.send('leader', '🤖 Agent Teams V2 已上线')
"
```

Expected: Message appears in group chat from Leader bot.

---

### Task 10: End-to-End Integration Test

- [ ] **Step 1: Run dry-run with multi-step task**

```bash
cd ~/Desktop/agent-teams
venv/bin/python dispatcher.py --dry-run "帮我写一个计算移动平均线的函数，然后 review 一下"
```

Verify:
- k2p5 produces a 2-step plan (coder → reviewer)
- Coder receives the task and produces code
- Reviewer receives Coder's output and reviews it
- Final summary is printed

- [ ] **Step 2: Run live test (with Telegram)**

```bash
cd ~/Desktop/agent-teams
venv/bin/python dispatcher.py "帮我写一个 hello world Python 脚本"
```

Verify:
- Messages appear in group chat from the correct bots
- Summaries are concise (one line each)
- Leader announces start and end

- [ ] **Step 3: Test fallback path**

```bash
cd ~/Desktop/agent-teams
# Use Gateway mock or temporarily make analysis fail
venv/bin/python dispatcher.py --dry-run "随便做点什么"
```

Verify fallback triggers and assigns to coder (default).

- [ ] **Step 4: Test from Telegram**

Send a message to Leader bot in the group chat (with @mention):
```
@AgentLeader 帮我写个选股脚本
```

Verify the full flow: Leader → dispatch_task tool → dispatcher.py → role execution → group chat summaries.

- [ ] **Step 5: Commit any fixes**

```bash
cd ~/Desktop/agent-teams
git add -A
git commit -m "fix: integration test fixes"
```

---

### Task 11: Restart Gateway and Final Verification

- [ ] **Step 1: Restart Clawdbot gateway**

```bash
# Restart to pick up new skill and binding changes
launchctl kickstart -k gui/$(id -u)/com.clawdbot.gateway
```

Wait 10 seconds, verify:
```bash
curl -s http://localhost:18789/v1/responses \
  -H "Authorization: Bearer <gateway-token>" \
  -H "Content-Type: application/json" \
  -d '{"model":"kimi-coding/k2p5","stream":false,"input":[{"type":"message","role":"user","content":"ping"}]}' | python3 -m json.tool
```

- [ ] **Step 2: Verify skill is loaded**

Check gateway logs for agent-teams skill loading:
```bash
tail -50 ~/.clawdbot/logs/gateway.log | grep -i "skill\|agent-teams"
```

- [ ] **Step 3: Full Telegram test**

Send a complex task via Telegram to @AgentLeader in the group:
```
@AgentLeader 帮我写一个计算 MACD 指标的函数，写完之后 review 一下
```

Expected flow in group chat:
1. Leader: `📋 AT-20260322-001: 计算 MACD 指标并 review` + `流程: Coder → Reviewer`
2. Coder: `✓ 计算 MACD 指标 — 已完成 MACD 函数实现，包含快慢线和信号线`
3. Reviewer: `✓ review 代码 — Review 通过，代码逻辑正确`
4. Leader: `✓ AT-20260322-001 完成，共 2 步`
