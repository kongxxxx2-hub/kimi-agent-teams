# Agent Teams

A multi-agent task dispatch system that orchestrates AI agents through Telegram, with automated research report generation.

## What It Does

Send a task to `@AgentLeader` in a Telegram group chat, and the system automatically:

1. **Analyzes** the task and assigns it to the right agents
2. **Executes** with specialized roles (Researcher, Analyst, Reviewer, etc.)
3. **Reviews** the output through a Leader quality review loop
4. **Produces** a clean PDF report saved to your desktop

Each agent posts concise status updates to the group chat with their own bot avatar.

## Architecture

```
User @AgentLeader in Telegram
         ↓
  Telegram Listener (Python)
         ↓
  Dispatcher (intent-based routing)
         ↓
  ┌──────────────┐
  │ Role Agents  │  Each calls LLM via Gateway API
  │ 🔎 Researcher │──→ Deep industry research
  │ 📊 Analyst    │──→ Data analysis & evaluation
  │ 🔍 Reviewer   │──→ Quality review
  │ 👨‍💻 Coder     │──→ Code implementation
  │ 🏗️ Architect  │──→ System design
  └──────────────┘
         ↓
  👑 Leader Review Loop
  (data validation + content completeness)
         ↓
  📁 Output: Markdown + PDF
```

## Smart Task Routing

The system uses intent-based detection to determine the right workflow — no LLM needed for routing:

| You Say | Workflow |
|---------|----------|
| "查一下 XX" (look up) | 🔎 Researcher |
| "分析 XX 趋势" (analyze trends) | 🔎 Researcher → 📊 Analyst |
| "对比 XX 竞争格局" (compare) | 🔎 Researcher → 📊 Analyst |
| "深入调研 XX 产业链" (deep research) | 🔎 Researcher → 📊 Analyst → 🔍 Reviewer |
| "写代码然后 review" | 👨‍💻 Coder → 🔍 Reviewer |

## Leader Review Loop

After all agents complete their work, the Leader reviews the output:

- Checks **data completeness** and **content coverage**
- Ignores style/formatting (only substance matters)
- Sends back for revision if key data or analysis is missing
- No fixed round limit — passes when quality is met

## Setup

### Prerequisites

- Python 3.10+
- A Telegram bot (for the Leader) + optional role bots
- [Clawdbot](https://clawdbot.com) or compatible LLM gateway

### Installation

```bash
git clone https://github.com/kongxxxx2-hub/agent-teams.git
cd agent-teams
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Configuration

Copy `config.example.json` to `config.json` and fill in:

```json
{
  "gateway": {
    "url": "http://localhost:18789",
    "token": "<your-gateway-token>"
  },
  "telegram": {
    "group_chat_id": "<your-group-chat-id>",
    "bots": {
      "leader": {"token": "<leader-bot-token>"},
      "researcher": {"token": "<researcher-bot-token>"},
      "analyst": {"token": "<analyst-bot-token>"},
      "reviewer": {"token": "<reviewer-bot-token>"},
      "coder": {"token": "<coder-bot-token>"},
      "architect": {"token": "<architect-bot-token>"}
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

### Usage

```bash
# Start the Telegram listener (daemon mode)
DYLD_LIBRARY_PATH=/opt/homebrew/lib venv/bin/python telegram_listener.py

# Or process one task and exit
DYLD_LIBRARY_PATH=/opt/homebrew/lib venv/bin/python telegram_listener.py --once

# Direct CLI usage (no Telegram)
DYLD_LIBRARY_PATH=/opt/homebrew/lib venv/bin/python dispatcher.py "调研一下 CPO 产业链"

# View task history
venv/bin/python show_task.py --list
venv/bin/python show_task.py AT-20260324-001
```

## Output

Reports are saved as Markdown + PDF to the configured output directory:

```
~/Desktop/AgentTeams_Output/
├── AT-20260324-001_调研CPO产业链.md
├── AT-20260324-001_调研CPO产业链.pdf
├── AT-20260324-002_分析AI芯片竞争格局.md
└── AT-20260324-002_分析AI芯片竞争格局.pdf
```

## Project Structure

```
agent-teams/
├── dispatcher.py          # Core orchestrator
├── telegram_listener.py   # Telegram polling + auto-dispatch
├── gateway_client.py      # LLM Gateway API client
├── fallback.py            # Intent-based task routing
├── telegram_display.py    # Group chat message formatting
├── db.py                  # SQLite task/step logging
├── show_task.py           # CLI task viewer
├── roles/                 # Agent role prompts
│   ├── researcher.md
│   ├── analyst.md
│   ├── reviewer.md
│   ├── coder.md
│   └── architect.md
├── config.example.json
├── requirements.txt
└── data/                  # SQLite DB + listener state
```

## Roadmap

- [ ] MCP Server integration (real-time data: stock prices, web search)
- [ ] Debate mechanism (bullish/bearish Researchers)
- [ ] Context summarization between steps
- [ ] Launchd service for persistent listener

## License

MIT
