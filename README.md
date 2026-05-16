<div align="center">

<h1>🤖 OpenSRE</h1>
<h3>Autonomous DevOps Agent</h3>

**OpenSRE — Autonomous DevOps Agent**

*An AI-powered Site Reliability Engineer that monitors your infrastructure, detects incidents, performs root cause analysis with Claude AI, and notifies your team across Slack, Telegram, and WhatsApp — with a human-in-the-loop approval step before taking any action.*

[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=flat&logo=python&logoColor=white)](https://python.org)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2+-1C1C1C?style=flat&logo=chainlink&logoColor=white)](https://github.com/langchain-ai/langgraph)
[![Claude AI](https://img.shields.io/badge/Claude-Anthropic-D97706?style=flat&logo=anthropic&logoColor=white)](https://anthropic.com)
[![Docker](https://img.shields.io/badge/Docker-ready-2496ED?style=flat&logo=docker&logoColor=white)](https://hub.docker.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-22c55e?style=flat)](LICENSE)
[![Simulation Mode](https://img.shields.io/badge/Simulation%20Mode-enabled-8b5cf6?style=flat)](#simulation-mode)

[![GitHub stars](https://img.shields.io/github/stars/Saimoguloju/OpenSRE-Autonomous-DevOps-Agent?style=social)](https://github.com/Saimoguloju/OpenSRE-Autonomous-DevOps-Agent/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/Saimoguloju/OpenSRE-Autonomous-DevOps-Agent?style=social)](https://github.com/Saimoguloju/OpenSRE-Autonomous-DevOps-Agent/network/members)

</div>

---

## 📋 Table of Contents

- [How It Works](#-how-it-works)
- [Features](#-features)
- [Architecture](#-architecture)
- [Quick Start](#-quick-start)
- [Notification Channels](#-notification-channels)
  - [Slack Setup](#slack)
  - [Telegram Setup](#telegram)
  - [WhatsApp Setup](#whatsapp-via-twilio)
- [Configuration Reference](#-configuration-reference)
- [Project Structure](#-project-structure)
- [Simulation Mode](#-simulation-mode)
- [Extending OpenSRE](#-extending-opensre)
- [Roadmap](#-roadmap)
- [Contributing](#-contributing)
- [License](#-license)

---

## ⚡ How It Works

```
Infrastructure                    OpenSRE Agent                     Your Team
─────────────      ───────────────────────────────────────     ──────────────────
  CPU / Mem    →   Monitor → Deduplicate → LangGraph Pipeline
  Database     →       ↓            ↓            ↓             → 📱 Slack
  Kubernetes   →    Detect    Fingerprint   Claude AI RCA      → 💬 Telegram
                       ↓                        ↓              → 📲 WhatsApp
                    Persist              Recommend Fix
                   (SQLite)                    ↓
                                     Human Approval?
                                     ↙            ↘
                               Fix It ✅       Ignore 🚫
                                  ↓
                         Execute Remediation
                         (kubectl / psql / AWS)
```

1. **Monitors** poll CPU, memory, databases, and Kubernetes every 30 seconds
2. **Deduplication** suppresses repeated alerts for the same ongoing issue (5-min cooldown)
3. **LangGraph** runs each breach through a `DETECT → ANALYZE → DECIDE → ACT` state machine
4. **Claude AI** reads the metrics and writes a structured root cause + recommended fix
5. **Dispatcher** fans out alert cards to **all enabled channels simultaneously** (Slack + Telegram + WhatsApp)
6. On approval, OpenSRE executes the fix (scale deployment, kill query, restart pod)
7. Resolution notifications are sent to all channels automatically

---

## ✨ Features

| Feature | Description |
|---|---|
| 🤖 **AI Root Cause Analysis** | Claude AI analyzes each incident and writes a structured root cause + recommended remediation |
| 🔁 **LangGraph State Machine** | Stateful `DETECT → ANALYZE → DECIDE → ACT` pipeline — no spaghetti if/else |
| 🛡️ **Human-in-the-Loop** | All medium/high/critical incidents require explicit human approval before any action is taken |
| 📢 **Multi-Channel Alerts** | Slack (interactive buttons), Telegram (Markdown cards), WhatsApp (via Twilio) — all in parallel |
| 🔇 **Alert Deduplication** | Fingerprint-based cooldown suppresses duplicate alerts for the same ongoing incident |
| 🗄️ **Incident Persistence** | Every incident is stored in SQLite with full lifecycle tracking (detected → resolved / ignored) |
| 🎮 **Simulation Mode** | Runs the full pipeline without any real cloud credentials — perfect for demos and development |
| 🐳 **One-Command Docker** | `docker-compose up` starts the entire agent with a single command |
| 🔌 **Extensible by Design** | Add new monitors, tools, or notification channels in minutes |

---

## 🏗️ Architecture

```
opensre/
├── main.py                     # Entry point — asyncio event loop + monitor_loop
├── config.py                   # All configuration via environment variables
│
├── agent/                      # LangGraph state machine
│   ├── state.py                # IncidentState & Metric TypedDicts
│   ├── graph.py                # Node wiring: DETECT→ANALYZE→DECIDE→ACT
│   └── nodes.py                # Claude AI analysis, decision, execution logic
│
├── monitors/                   # Infrastructure polling
│   ├── base.py                 # BaseMonitor ABC + severity() formula
│   ├── cpu.py                  # CPU & memory (real, via psutil)
│   ├── database.py             # Slow query detection (simulated or real PostgreSQL)
│   └── kubernetes.py           # Pod crash detection (simulated or real kubectl)
│
├── tools/                      # Remediation action executors
│   ├── k8s_tools.py            # kubectl: restart pod, scale deployment, rollout
│   ├── db_tools.py             # psycopg2: kill slow queries, EXPLAIN ANALYZE
│   └── aws_tools.py            # boto3: CloudWatch metrics, EC2 describe
│
├── notifications/              # Alert channels
│   ├── dispatcher.py           # Multi-channel fan-out (asyncio.gather)
│   ├── slack_bot.py            # Slack Block Kit + interactive Fix It / Ignore buttons
│   ├── telegram_notifier.py    # Telegram Bot API (Markdown messages)
│   └── whatsapp_notifier.py    # WhatsApp via Twilio REST API
│
└── storage/
    └── incidents.py            # SQLite persistence with upsert + full CRUD
```

### LangGraph Flow

```mermaid
graph LR
    A([🔍 analyze_root_cause\nClaude AI]) --> B([⚖️ decide_action])
    B -->|low severity + sim mode| C([⚙️ execute_action])
    B -->|medium / high / critical| D([⏳ await_human\nSlack · Telegram · WhatsApp])
    D -->|✅ Fix It| C
    D -->|🚫 Ignore| E([🚫 mark_ignored])
    C --> F([END])
    E --> F
```

---

## 🚀 Quick Start

### Prerequisites

- Python 3.12+
- An [Anthropic API key](https://console.anthropic.com/) (Claude)
- At least one notification channel token *(or use console fallback — no tokens needed)*

### 1. Clone & Install

```bash
git clone https://github.com/Saimoguloju/OpenSRE-Autonomous-DevOps-Agent.git
cd OpenSRE-Autonomous-DevOps-Agent
pip install -r requirements.txt
```

### 2. Configure

```bash
cp .env.example .env
# Open .env and set your ANTHROPIC_API_KEY
# Optionally add Slack / Telegram / WhatsApp tokens
```

**Minimum `.env` to run:**
```env
ANTHROPIC_API_KEY=sk-ant-...your-key...
SIMULATION_MODE=true
```

### 3. Run

```bash
python main.py
```

You'll see the ASCII banner and then live incident logs in your terminal. Alerts will fire to every configured channel.

### Docker (one command)

```bash
cp .env.example .env   # fill in ANTHROPIC_API_KEY at minimum
docker-compose up
```

---

## 📢 Notification Channels

OpenSRE supports **three notification channels** out of the box. Each is **optional and independent** — if none are configured, alerts print to the console (great for local development).

All enabled channels receive alerts **simultaneously** using `asyncio.gather`, so a failure in one channel never blocks the others.

---

### Slack

> **Best for:** Teams already using Slack. Provides interactive "Fix It" / "Ignore" buttons for human approval directly in Slack.

**Setup:**

1. Go to [api.slack.com/apps](https://api.slack.com/apps) → **Create New App** → From scratch
2. Enable **Socket Mode** under Settings → Get your `SLACK_APP_TOKEN` (`xapp-...`)
3. Go to **OAuth & Permissions** → Add scopes: `chat:write`, `channels:read`
4. Click **Install to Workspace** → Copy the `Bot User OAuth Token` (`xoxb-...`)
5. Subscribe to `block_actions` event under **Event Subscriptions**
6. Invite the bot to your alert channel: `/invite @YourBotName`

```env
SLACK_BOT_TOKEN=xoxb-...
SLACK_APP_TOKEN=xapp-...
SLACK_ALERT_CHANNEL=#incidents
```

**What it looks like:**

```
🔴 OpenSRE Incident — CRITICAL
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Metric:  pod_crash_loop
Host:    production/api-deployment-7d9f8b-xk2p
Value:   8 restarts (threshold: 5)
ID:      a3f2c1d4

Root Cause:
  Pod is in CrashLoopBackOff — likely OOMKill or failed readiness probe.

Recommended Action:
  kubectl delete pod api-deployment-7d9f8b-xk2p -n production

[ ✅ Fix It ]  [ 🚫 Ignore ]
```

---

### Telegram

> **Best for:** Personal projects, small teams, or when you need free mobile push notifications worldwide.

**Setup:**

1. Open Telegram → search **@BotFather** → send `/newbot`
2. Follow the prompts → copy your bot token
3. Add the bot to your group or channel and make it an **admin**
4. Get your `chat_id`:
   - Send any message in the group
   - Visit: `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates`
   - Look for `"chat": {"id": -100XXXXXXXXXX}` — that is your chat ID

```env
TELEGRAM_BOT_TOKEN=1234567890:AAxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TELEGRAM_CHAT_ID=-100xxxxxxxxxx
```

**What it looks like:**

```
🔴 OpenSRE Incident — CRITICAL

📋 ID: a3f2c1d4
📊 Metric: pod_crash_loop
🖥️ Host: production/api-deployment-7d9f8b-xk2p
📈 Value: 8 count (threshold: 5.0)
⏳ Status: Awaiting Approval

🔎 Root Cause:
Pod is in CrashLoopBackOff due to repeated OOMKill events.

🛠️ Recommended Action:
kubectl delete pod api-deployment-7d9f8b-xk2p -n production
```

---

### WhatsApp (via Twilio)

> **Best for:** Reaching on-call engineers on their personal phones without requiring them to install another app.

**Setup (Free Sandbox — no credit card needed for testing):**

1. Create a free account at [twilio.com](https://www.twilio.com)
2. In the Twilio Console → **Messaging** → **Try it out** → **Send a WhatsApp message**
3. Follow the sandbox instructions: send the join keyword from your WhatsApp to the Twilio sandbox number
4. Copy your **Account SID** and **Auth Token** from [console.twilio.com](https://console.twilio.com)
5. Add all on-call numbers as `whatsapp:+<country_code><number>` (comma-separated for multiple)

```env
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_auth_token_here
TWILIO_WHATSAPP_FROM=whatsapp:+14155238886
WHATSAPP_ALERT_NUMBERS=whatsapp:+91XXXXXXXXXX,whatsapp:+44XXXXXXXXXX
```

> **Note:** For production use beyond the sandbox, register a [WhatsApp Business number](https://www.twilio.com/whatsapp) through Twilio. Pre-approved message templates are required for proactive outbound messages.

---

## ⚙️ Configuration Reference

All configuration is done via environment variables. Set them in your `.env` file.

| Variable | Default | Required | Description |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | — | **Yes** | Your Claude API key from [console.anthropic.com](https://console.anthropic.com) |
| `OPENSRE_MODEL` | `claude-sonnet-4-6` | No | Claude model to use for analysis |
| `SIMULATION_MODE` | `true` | No | `true` = no real cloud credentials needed |
| `POLL_INTERVAL_SECONDS` | `30` | No | How often to poll all monitors |
| `ALERT_COOLDOWN_SECONDS` | `300` | No | Seconds to suppress duplicate alerts for same metric+host |
| `CPU_THRESHOLD_PCT` | `85` | No | Alert when CPU exceeds this % |
| `MEMORY_THRESHOLD_PCT` | `90` | No | Alert when memory exceeds this % |
| `SLOW_QUERY_THRESHOLD_MS` | `500` | No | Alert on DB queries slower than this |
| `OPENSRE_DB_PATH` | `opensre_incidents.db` | No | SQLite file path for incident storage |
| `DATABASE_URL` | — | No | PostgreSQL URL for real DB mode (e.g. `postgresql://user:pass@host/db`) |
| `SLACK_BOT_TOKEN` | — | No | Slack bot token (`xoxb-...`) |
| `SLACK_APP_TOKEN` | — | No | Slack app token for Socket Mode (`xapp-...`) |
| `SLACK_ALERT_CHANNEL` | `#incidents` | No | Slack channel to post alerts |
| `TELEGRAM_BOT_TOKEN` | — | No | Telegram bot token from @BotFather |
| `TELEGRAM_CHAT_ID` | — | No | Telegram chat/group/channel ID |
| `TWILIO_ACCOUNT_SID` | — | No | Twilio Account SID |
| `TWILIO_AUTH_TOKEN` | — | No | Twilio Auth Token |
| `TWILIO_WHATSAPP_FROM` | `whatsapp:+14155238886` | No | WhatsApp sender number |
| `WHATSAPP_ALERT_NUMBERS` | — | No | Comma-separated WhatsApp recipients (`whatsapp:+1XXX,...`) |
| `AWS_REGION` | `us-east-1` | No | AWS region for CloudWatch / EC2 |
| `AWS_ACCESS_KEY_ID` | — | No | AWS access key (real mode only) |
| `AWS_SECRET_ACCESS_KEY` | — | No | AWS secret key (real mode only) |

---

## 🎮 Simulation Mode

With `SIMULATION_MODE=true` (the default), OpenSRE generates realistic synthetic incidents so you can see the full pipeline without any real infrastructure:

| Monitor | Simulation Behaviour |
|---|---|
| **CPU / Memory** | Reads real values from your local machine via `psutil` |
| **Database** | Triggers a random slow query every ~5 poll cycles |
| **Kubernetes** | Reports a `CrashLoopBackOff` pod every ~8 poll cycles |
| **Tools** | All `kubectl`, `psql`, and AWS actions are logged as `[SIMULATION] → OK` |

This means you can run a complete demo — incidents, Claude analysis, Slack/Telegram/WhatsApp alerts, and approval flow — on your laptop with only an Anthropic API key.

---

## 🔌 Extending OpenSRE

### Add a new monitor

```python
# monitors/redis.py
from monitors.base import BaseMonitor
from agent.state import Metric

class RedisMonitor(BaseMonitor):
    name = "redis"

    def poll(self) -> list[Metric]:
        # Connect to Redis, check memory/latency, return list of Metric
        ...
```

Register it in `main.py`:
```python
from monitors.redis import RedisMonitor
monitors = [CpuMonitor(), DatabaseMonitor(), KubernetesMonitor(), RedisMonitor()]
```

### Add a new remediation tool

```python
# tools/redis_tools.py
def flush_redis_cache(db: int = 0) -> str:
    # Execute FLUSHDB on the target Redis instance
    ...
```

Call it from `agent/nodes.py` inside `execute_action()`:
```python
elif metric["source"] == "redis":
    from tools.redis_tools import flush_redis_cache
    result = flush_redis_cache()
```

### Add a new notification channel

```python
# notifications/pagerduty_notifier.py
class PagerDutyNotifier:
    async def send_alert(self, incident: IncidentState) -> bool: ...
    async def send_update(self, incident: IncidentState) -> bool: ...
```

Register it in `notifications/dispatcher.py`:
```python
from notifications.pagerduty_notifier import PagerDutyNotifier
self.pagerduty = PagerDutyNotifier()
# add to asyncio.gather() calls
```

---

## 🛣️ Roadmap

### ✅ v1.0 — Core Agent (Complete)
- [x] LangGraph state machine (DETECT → ANALYZE → DECIDE → ACT)
- [x] Claude AI root cause analysis
- [x] Human-in-the-loop via Slack interactive buttons
- [x] SQLite incident persistence
- [x] Docker + docker-compose
- [x] Simulation mode

### 🚧 v1.1 — Multi-Channel Alerts (Complete)
- [x] Telegram notifications
- [x] WhatsApp notifications via Twilio
- [x] Multi-channel dispatcher (parallel fan-out)
- [x] Alert deduplication with fingerprint cooldown
- [x] Bug fixes (async callback, class variable, db_url)

### 🔮 v1.2 — Observability Stack (Planned)
- [ ] Prometheus `/metrics` endpoint (incident counters, MTTD, MTTR, Claude latency)
- [ ] Pre-built Grafana dashboard (docker-compose included)
- [ ] OpenTelemetry distributed tracing across LangGraph nodes

### 🔮 v1.3 — Smarter AI (Planned)
- [ ] Confidence scoring — low-confidence analysis always requires human approval
- [ ] RAG on past incidents — Claude reads similar historical incidents before analyzing
- [ ] Auto post-mortem generation after incident resolution
- [ ] Incident correlation — group related alerts into a single incident

### 🔮 v1.4 — Production Hardening (Planned)
- [ ] Web dashboard with live incident feed
- [ ] GitHub Actions CI pipeline (lint, test, Docker build)
- [ ] Real AWS CloudWatch monitor integration
- [ ] Open Policy Agent (OPA) guardrails for remediation actions
- [ ] Unit test suite

---

## 🤝 Contributing

Contributions are welcome and appreciated! This is an open learning project — whether you're fixing a bug, adding a new monitor, or improving documentation, all PRs are reviewed.

**Getting Started:**

1. Fork the repository
2. Create a feature branch: `git checkout -b feat/your-feature-name`
3. Make your changes and ensure the agent starts correctly with `python main.py`
4. Commit using conventional commits: `feat:`, `fix:`, `docs:`, `refactor:`
5. Open a Pull Request with a clear description of what you changed and why

**Good first issues:**
- Add a new monitor (Redis, Nginx, Elasticsearch)
- Add a new notification channel (Discord, PagerDuty, Microsoft Teams)
- Write unit tests for `storage/incidents.py` or `monitors/base.py`
- Improve the Grafana dashboard JSON

---

## 📚 Tech Stack

| Technology | Role |
|---|---|
| **Python 3.12** + **asyncio** | Core runtime and async I/O |
| **LangGraph** | Stateful multi-node agent pipeline |
| **Anthropic Claude** | Root cause analysis and remediation recommendations |
| **Slack Bolt** | Interactive Slack bot with button callbacks |
| **python-telegram-bot** | Telegram Bot API client |
| **Twilio** | WhatsApp message delivery |
| **psutil** | Local CPU and memory monitoring |
| **SQLite** | Zero-setup incident storage and persistence |
| **Docker** | Containerised deployment |

---

## 📄 License

MIT License — free to use, modify, and distribute.
See [LICENSE](LICENSE) for the full text.

---

<div align="center">

**Built with ❤️ to automate infrastructure reliability**

If this project helped you, consider giving it a ⭐ on GitHub!

[![GitHub stars](https://img.shields.io/github/stars/Saimoguloju/OpenSRE-Autonomous-DevOps-Agent?style=for-the-badge&logo=github)](https://github.com/Saimoguloju/OpenSRE-Autonomous-DevOps-Agent/stargazers)

</div>
