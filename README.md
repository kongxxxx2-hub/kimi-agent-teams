# Kimi Agent Teams

A multi-agent research system powered by [Kimi](https://kimi.ai) on Telegram. Send a task to your Agent Leader, and a team of specialized AI agents collaborates to produce publication-quality research reports.

## How It Works

```
You: @AgentLeader 调研中国人形机器人产业链

  📋 Leader assigns task
       ↓
  🔎 Researcher — searches the web, collects data, writes draft
       ↓
  📊 Analyst — evaluates data, adds quantitative analysis
       ↓
  🔍 Reviewer — checks completeness and accuracy
       ↓
  👑 Leader — reviews quality, sends back if needed
       ↓
  📁 Final report: Markdown + PDF
```

Each agent posts status updates to the Telegram group with their own bot avatar.

## Features

- **Smart Routing** — Intent detection assigns the right agents automatically
- **Multi-Agent Collaboration** — Researcher, Analyst, Reviewer, Coder, Architect
- **Quality Review Loop** — Leader reviews output, sends back for revision until satisfied
- **Search-Verified Reviews** — Leader must web-search to verify data before flagging errors
- **PDF Reports** — Clean, styled reports with Chinese font support
- **Persistent Listener** — Runs as a background service, always ready

## Task Routing

| You Say | Agents Activated |
|---------|-----------------|
| "查一下 XX" | 🔎 Researcher |
| "分析 XX" | 🔎 Researcher → 📊 Analyst |
| "对比 XX 竞争格局" | 🔎 Researcher → 📊 Analyst |
| "深入调研 XX 产业链" | 🔎 Researcher → 📊 Analyst → 🔍 Reviewer |
| "写代码然后 review" | 👨‍💻 Coder → 🔍 Reviewer |

## Setup

### Prerequisites

- Python 3.10+
- Telegram bots (one for Leader + optional per-role bots)
- [OpenClaw](https://github.com/nicepkg/openclaw) or compatible LLM gateway with Kimi model

### Install

```bash
git clone https://github.com/kongxxxx2-hub/kimi-agent-teams.git
cd kimi-agent-teams
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Configure

Copy `config.example.json` to `config.json`:

```json
{
  "gateway": {
    "url": "http://localhost:18789",
    "token": "<gateway-token>"
  },
  "telegram": {
    "group_chat_id": "<group-chat-id>",
    "bots": {
      "leader": {"token": "<bot-token>"},
      "researcher": {"token": "<bot-token>"},
      "analyst": {"token": "<bot-token>"},
      "reviewer": {"token": "<bot-token>"},
      "coder": {"token": "<bot-token>"},
      "architect": {"token": "<bot-token>"}
    }
  },
  "dispatcher": {
    "model": "kimi-coding/k2p5",
    "max_steps": 5,
    "step_timeout_seconds": 600,
    "max_context_bytes": 153600
  }
}
```

### Run

```bash
# Telegram listener (daemon)
python telegram_listener.py

# Single task (CLI)
python dispatcher.py "调研 CPO 产业链"

# View task history
python show_task.py --list
```

## Project Structure

```
kimi-agent-teams/
├── dispatcher.py          # Core orchestrator + Leader review loop
├── telegram_listener.py   # Telegram polling daemon
├── gateway_client.py      # LLM Gateway API client
├── fallback.py            # Intent-based task routing
├── telegram_display.py    # Group chat formatting (per-role emoji)
├── db.py                  # SQLite task/step logging
├── show_task.py           # CLI task viewer
├── roles/                 # Agent system prompts
│   ├── researcher.md      # Industry research specialist
│   ├── analyst.md         # Data analysis & evaluation
│   ├── reviewer.md        # Quality review
│   ├── coder.md           # Code implementation
│   └── architect.md       # System design
├── config.example.json
└── requirements.txt
```

## Design Decisions

- **Code-driven routing over LLM routing** — Kimi k2p5 couldn't reliably produce dispatch plans, so intent detection is pure Python regex. More reliable, faster, zero API calls wasted.
- **Search-verified reviews** — Leader must web-search to verify data before flagging errors. Prevents the "reviewer changes correct data to wrong data" problem.
- **Revision with re-search** — When revising, agents must re-search to verify feedback rather than blindly accepting review comments.
- **Clean PDF output** — Final report contains only the last content role's output. No review process, no revision metadata.

## Roadmap

- [ ] MCP Server integration for real-time data (stock prices, financial APIs)
- [ ] Debate mechanism (bullish vs bearish Researchers)
- [ ] Context summarization between agent steps
- [ ] Support for additional LLM backends (Claude, GPT-4)

## License

MIT
