# Agent Teams V2 — Design Spec

## Overview

基于 Clawdbot Gateway 的多 Agent 动态任务分派系统。用户通过 Telegram 发送任务给 Leader，调度脚本自动拆分任务、分派给角色 agent 执行、汇总结果，群聊展示精简流转过程。

## Goals

- 动态任务分派：Leader 分析任务后自动拆分、分派给合适的角色 agent
- 代码控制调度：Python 调度脚本作为中枢，不依赖 LLM 自觉执行 tool chain
- Telegram 群聊展示：各角色 bot 发精简摘要，干净可读
- 文件 I/O 由代码处理：不让 k2p5 自己读文件，避免读错

## Non-Goals

- 不做 Web Dashboard（群聊即 Dashboard）
- 不做 parallel 执行（先 sequential，后续迭代）
- 不改动现有 Clawdbot 5 个角色 bot 配置（保留给方案 A 迁移用）

## Architecture

```
用户 Telegram 消息
       ↓
  Leader Bot (Clawdbot 原生 agent, private/leader 账户)
       ↓
  Leader 调用 dispatch_task tool
       ↓
  调度脚本 dispatcher.py (Python, 核心中枢)
       ↓
  1. 调 OpenResponses API 让 k2p5 分析任务
     → 输出分派计划 JSON
     → JSON 解析失败则 fallback 到关键词规则
  2. 按计划依次为每个角色调 OpenResponses API
     - 调度脚本先读取相关文件
     - 组装角色 system prompt (instructions) + 文件 context + 任务
     - POST /v1/responses → 收结果
  3. 各角色 bot 往群聊发精简摘要
  4. 上一步输出作为下一步输入
  5. Leader bot 发最终汇总给用户
  6. 完整日志存 SQLite
```

## Gateway API Reference

### HTTP REST — OpenResponses API

**Endpoint**: `POST http://localhost:18789/v1/responses`

**Headers**:
```
Authorization: Bearer <gateway_token>
Content-Type: application/json
```

**Request Schema**:
```json
{
  "model": "kimi-coding/k2p5",
  "stream": false,
  "instructions": "角色 system prompt (来自 roles/*.md)",
  "input": [
    {
      "type": "message",
      "role": "user",
      "content": "任务描述 + 文件 context"
    }
  ],
  "max_output_tokens": 32768
}
```

**Response Schema**:
```json
{
  "id": "resp_<uuid>",
  "status": "completed|incomplete|failed",
  "output": [
    {
      "type": "message",
      "role": "assistant",
      "content": [{"type": "output_text", "text": "..."}]
    }
  ],
  "usage": {
    "input_tokens": 0,
    "output_tokens": 0,
    "total_tokens": 0
  }
}
```

### WebSocket RPC (Leader Agent 用)

**Endpoint**: `ws://localhost:18789/`

关键方法：
- `chat.send` — 给 agent session 发消息
- `sessions.list` — 列出所有 session
- `chat.history` — 获取 session 历史

Leader agent 通过 Clawdbot 原生机制使用 WebSocket，调度脚本通过 HTTP REST 调用角色 agent。

## Components

### 1. Leader Agent (Clawdbot 原生)

- 已有的 `main` agent，绑定 private（私聊）+ leader（群聊）
- 新增 `dispatch_task` tool，注册到 agent 的 tool 列表
- 简单闲聊直接回复，复杂任务调 dispatch_task
- **需要更新 SOUL.md**：从"太子"角色改为 Leader dispatcher 角色

**Tool 注册方式**: Clawdbot 的 tool 通过 skill 机制注册。在 `~/.clawdbot/skills/` 下创建 `agent-teams` skill 目录，包含 `_meta.json`（定义 tool schema）和对应的执行脚本。Leader 调用 tool 时，Clawdbot 执行脚本并返回结果。

```
~/.clawdbot/skills/agent-teams/
├── _meta.json          # skill 元数据 + tool 定义
├── SKILL.md            # skill 说明（给 LLM 看）
└── dispatch.sh         # tool 执行入口，调用 dispatcher.py
```

**Leader agent 配置修正**: 当前 `clawdbot.json` 中 `leader` 绑定的 agentId 是 `"leader"`，但 agents 列表里只有 `"main"`。需要将 leader 账户的 agentId 改为 `"main"`，让同一个 agent 处理私聊和群聊。

### 2. 调度脚本 dispatcher.py

核心中枢，职责：

- **任务分析**：调 OpenResponses API，用 k2p5 分析任务，输出分派计划 JSON
- **Fallback 规则**：k2p5 返回的 JSON 解析失败或格式不对时，用关键词匹配兜底
- **角色执行**：为每个角色调 OpenResponses API，带上角色 system prompt (instructions) + context
- **文件 I/O**：调度脚本读取用户提到的文件，作为 context 塞进 prompt，不让 k2p5 自己读
- **结果汇总**：收集各角色输出，组装最终结果
- **日志记录**：完整输入输出存 SQLite

### 3. 分派计划 JSON 格式

```json
{
  "task_id": "AT-20260322-001",
  "summary": "重构选股脚本并 review",
  "steps": [
    {
      "role": "coder",
      "task": "重构 liuban.py 选股逻辑，新增3个筛选条件",
      "context_files": ["/path/to/example.py"]
    },
    {
      "role": "reviewer",
      "task": "review 重构后的代码，检查逻辑正确性"
    }
  ],
  "mode": "sequential"
}
```

### 4. Fallback 规则 (fallback.py)

当 k2p5 返回的分派计划无法解析时：

| 关键词 | 角色 |
|--------|------|
| 写/实现/脚本/代码/修改/重构 | coder |
| review/检查/审核/审查 | reviewer |
| 查/搜索/调研/找 | researcher |
| 分析/评估/对比 | analyst |
| 设计/架构/方案 | architect |
| 无匹配 | coder (默认) |

- 单步任务：跳过拆分，直接派给匹配的角色
- 多关键词命中：取第一个匹配的角色作为单步任务（fallback 不尝试多步拆分，避免顺序错误）
- Fallback 触发时在群聊注明：`⚠ 自动分析失败，使用规则分派`

### 5. 角色 System Prompts (roles/*.md)

每个角色一个 markdown 文件，定义：
- 角色身份和职责
- 输出格式要求
- 可用能力描述

角色列表：
- **Coder**: 写代码、修 bug、重构
- **Reviewer**: 代码审查、质量检查
- **Researcher**: 信息搜索、资料整理
- **Analyst**: 数据分析、方案评估
- **Architect**: 系统设计、架构决策

### 6. Telegram 群聊展示 (telegram_display.py)

- 各角色 bot 用自己的 bot token 发送精简摘要到群聊
- 摘要格式：`✓ 完成 [任务简述]，[关键结论/结果]`
- Leader bot 发任务开始/结束的总结
- 不发完整代码或完整 review 报告
- 不用感叹号

Bot Token 配置：

| Bot | 用途 |
|-----|------|
| Bob (8418432363) | 私聊回复用户 |
| AgentLeader (8665589291) | 群聊任务播报 |
| Coder bot | 群聊发 Coder 摘要 |
| Reviewer bot | 群聊发 Reviewer 摘要 |
| Researcher bot | 群聊发 Researcher 摘要 |
| Analyst bot | 群聊发 Analyst 摘要 |
| Architect bot | 群聊发 Architect 摘要 |

注：5 个角色 bot 已创建但尚未加入群聊，实施时需将它们加入群聊并获取 token。

### 7. 日志存储 (db.py)

SQLite 数据库，表结构：

**tasks 表**:
- task_id TEXT PRIMARY KEY
- user_message TEXT
- dispatch_plan TEXT (JSON)
- status TEXT (pending/running/completed/failed/partial)
- created_at TIMESTAMP
- completed_at TIMESTAMP

**steps 表**:
- step_id INTEGER PRIMARY KEY
- task_id TEXT REFERENCES tasks
- step_order INTEGER
- role TEXT
- input_prompt TEXT
- output TEXT
- tokens_used INTEGER
- duration_ms INTEGER
- status TEXT (pending/running/completed/failed)
- created_at TIMESTAMP

## Session Lifecycle

- **创建**：调度脚本为每个角色步骤调用 `POST /v1/responses`，这是无状态调用，不需要管理 session 生命周期
- **超时**：每个角色调用设 120 秒超时，超时视为失败
- **响应校验**：检查 response.status == "completed" 且 output 非空
- **失败处理**：步骤失败时中止剩余步骤，报告已完成的部分结果，Leader bot 在群聊通知用户
- **重试策略**：V2 不重试，失败直接报告（避免复杂性）

## Context File Handling

- **路径校验**：context_files 中的路径必须存在，不存在的跳过并记录警告
- **大小限制**：单文件 50KB，总 context 150KB，超出时截取前 N 行
- **允许目录**：不限制（用户的文件都在本机），但记录读取了哪些文件

## Error Handling

| 场景 | 处理 |
|------|------|
| k2p5 分派计划 JSON 解析失败 | Fallback 到关键词规则 |
| 角色步骤超时 (>120s) | 标记失败，中止后续步骤 |
| 角色步骤返回 status != completed | 标记失败，中止后续步骤 |
| Gateway 不可达 | 在群聊通知用户，任务标记 failed |
| context_file 不存在 | 跳过该文件，继续执行 |
| 分派计划 steps > 5 | 截取前 5 步，群聊提示已简化 |

## File Structure

```
~/Desktop/agent-teams/
├── venv/                # 独立 Python 虚拟环境
├── requirements.txt     # 依赖: requests, python-telegram-bot
├── dispatcher.py        # 核心调度脚本 (支持 --dry-run 模式)
├── roles/
│   ├── coder.md
│   ├── reviewer.md
│   ├── researcher.md
│   ├── analyst.md
│   └── architect.md
├── fallback.py          # 关键词 fallback 规则
├── telegram_display.py  # 群聊精简摘要发送
├── db.py                # SQLite 日志存储
├── config.json          # bot tokens, 群聊 ID, gateway 配置
└── data/
    └── agent_teams.db   # SQLite 数据库文件

# Clawdbot skill 注册
~/.clawdbot/skills/agent-teams/
├── _meta.json
├── SKILL.md
└── dispatch.sh
```

## Config Format (config.json)

```json
{
  "gateway": {
    "url": "http://localhost:18789",
    "token": "<gateway auth token>"
  },
  "telegram": {
    "group_chat_id": "-1003716709219",
    "bots": {
      "private-bot": {"token": "<bob-bot-token>"},
      "leader": {"token": "<leader-bot-token>"},
      "coder": {"token": "<待获取>"},
      "reviewer": {"token": "<待获取>"},
      "researcher": {"token": "<待获取>"},
      "analyst": {"token": "<待获取>"},
      "architect": {"token": "<待获取>"}
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

## Key Design Decisions

1. **dispatch_task 通过 skill 机制注册** — 在 ~/.clawdbot/skills/agent-teams/ 下注册，Leader 调用 tool 时执行 dispatcher.py
2. **角色调用走 OpenResponses HTTP API** — 无状态 POST /v1/responses，不需要 session 管理，避开 sessions_send 的坑
3. **文件 I/O 全在调度脚本** — 调度脚本读文件、塞 context，k2p5 只做理解和生成
4. **Sequential 优先** — 一步步执行，前一步输出传给下一步，避免并发复杂性
5. **角色 prompt 是 markdown** — 方便迭代，改 prompt 不用改代码
6. **精简群聊摘要** — 群聊只展示一句话总结，完整内容在 SQLite 里
7. **独立 venv** — 不依赖 ths_api 或其他项目环境
8. **失败即中止** — 步骤失败时中止后续步骤，报告部分结果
9. **dry-run 模式** — `dispatcher.py --dry-run "任务描述"` 输出到 stdout，不发 Telegram

## Migration Path to Plan A

**触发条件**：当 k2p5 换成更强的模型（能通过 5 步 tool chain 测试）时考虑迁移。

迁移步骤：
1. 在 clawdbot.json agents 列表中启用 5 个角色 agent（配置已保留在 openclaw.json 中）
2. 为每个角色 agent 创建 workspace 目录和 SOUL.md（从 roles/*.md 迁移）
3. 调度脚本从 OpenResponses API 调用改为 WebSocket `chat.send` + `sessions_send`
4. 为每个角色 agent 绑定对应的 Telegram bot 账户
5. 其余逻辑（fallback、群聊展示、日志）保持不变
