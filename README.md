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
[![Tests](https://img.shields.io/badge/tests-74%20passing-22c55e?style=flat&logo=pytest&logoColor=white)](tests/)
[![CI](https://img.shields.io/badge/CI-GitHub%20Actions-2088FF?style=flat&logo=githubactions&logoColor=white)](.github/workflows/ci.yml)
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
3. **LangGraph** runs each breach through an `ANALYZE → CRITIQUE → DECIDE → ACT` state machine
4. **Claude AI** reads the metrics and writes a structured root cause + recommended fix
5. **Self-critique** audits the proposed fix and scores confidence (0–100); low confidence always escalates to a human
6. **Dispatcher** fans out alert cards to **all enabled channels simultaneously** (Slack + Telegram + WhatsApp)
7. On approval (or autonomously, when `AUTO_REMEDIATE` is enabled for non-critical, high-confidence incidents), OpenSRE executes the fix (scale deployment, kill query, restart pod)
8. Resolution notifications are sent to all channels automatically

---

## ✨ Features

| Feature | Description |
|---|---|
| 🤖 **AI Root Cause Analysis** | The configured LLM analyzes each incident and writes a structured root cause + recommended remediation |
| 🔌 **Pluggable LLM Providers** | Swap between **Anthropic Claude**, **OpenAI** (and any OpenAI-compatible endpoint — Azure, Groq, OpenRouter, **Ollama**), and **Google Gemini** with a single `LLM_PROVIDER` env var — no code changes |
| 🧠 **Local Database RAG** | SQLite-based historical incident search feeds context of past resolutions to Claude for remediation consistency |
| 🔁 **LangGraph State Machine** | Stateful `DETECT → ANALYZE → DECIDE → ACT` pipeline — no spaghetti if/else |
| 🕵️‍♂️ **Agentic Self-Critique** | Separate LangGraph node audits proposed remediation safety/correctness and forces human approval if confidence is low (< 80) |
| 🛡️ **Human-in-the-Loop** | All medium/high/critical incidents require explicit human approval before any action is taken |
| 🔒 **Safety Guardrails** | Deterministic command validation preventing malicious or destructive actions (e.g. namespace deletion, `rm -rf`) |
| 📊 **Prometheus & Grafana** | Built-in SRE metrics server tracking active incidents, execution times, and Claude analysis latency |
| 📝 **Blameless Post-Mortems** | Automatic structured SRE post-mortem generation in markdown format after incident resolution |
| 📢 **Multi-Channel Alerts** | Slack & **Telegram** (interactive approve/ignore buttons), WhatsApp (Twilio) and **Discord** (webhook) — all fired in parallel |
| 🎛️ **Operable CLI** | `--once` (cron/CI), `--dry-run`, `--list-incidents`, `--provider` overrides, and graceful SIGINT/SIGTERM shutdown |
| 📈 **Rich Observability** | Prometheus metrics (active-incidents gauge, **MTTR**, approval latency, LLM/action latency), a `/healthz` probe, and an auto-provisioned Grafana dashboard |
| 🔇 **Alert Deduplication** | Fingerprint-based cooldown suppresses duplicate alerts for the same ongoing incident |
| 🗄️ **Incident Persistence** | Every incident is stored in SQLite with full lifecycle tracking (detected → resolved / ignored) |
| 🎮 **Simulation Mode** | Runs the full pipeline without any real cloud credentials — perfect for demos and development |
| 🐳 **One-Command Docker** | `docker-compose up` starts the entire agent, Prometheus metrics, and Grafana visualization |
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
│   ├── graph.py                # Node wiring: ANALYZE→CRITIQUE→DECIDE→ACT + resume
│   ├── guardrails.py           # Safety checks and command validation
│   ├── metrics.py              # Prometheus metrics declarations
│   └── nodes.py                # AI analysis, self-critique, decision, execution
│
├── llm/                        # Pluggable LLM provider layer
│   ├── base.py                 # LLMProvider interface (complete())
│   ├── anthropic_provider.py   # Claude (default)
│   ├── openai_provider.py      # OpenAI + OpenAI-compatible (Azure/Groq/Ollama…)
│   └── google_provider.py      # Google Gemini
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
├── observability.py            # /metrics + /healthz HTTP server
├── grafana/                    # Auto-provisioned datasource + OpenSRE dashboard
│
├── notifications/              # Alert channels
│   ├── dispatcher.py           # Multi-channel fan-out (asyncio.gather)
│   ├── slack_bot.py            # Slack Block Kit + interactive Fix It / Ignore buttons
│   ├── telegram_notifier.py    # Telegram Bot API + inline approve/ignore buttons
│   ├── whatsapp_notifier.py    # WhatsApp via Twilio REST API
│   └── discord_notifier.py     # Discord incoming webhook (notify-only)
│
├── storage/
│   └── incidents.py            # SQLite persistence with upsert + local RAG search
│
└── tests/                      # Offline pytest suite (simulation mode, mock Claude)
    ├── conftest.py             # Shared fixtures + hermetic test environment
    ├── test_agent.py           # Guardrails, storage, decision/critique, RAG
    ├── test_graph.py           # End-to-end LangGraph run with a mocked client
    ├── test_monitors.py        # Severity formula + per-monitor polling
    ├── test_config.py          # Config parsing & validation
    └── test_notifications.py   # Message builders + dispatcher fan-out
```

Project hygiene: [`LICENSE`](LICENSE) (MIT) · [`CONTRIBUTING.md`](CONTRIBUTING.md) · [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md) · [`SECURITY.md`](SECURITY.md) · [`CHANGELOG.md`](CHANGELOG.md) · [`pyproject.toml`](pyproject.toml) · GitHub issue/PR templates.

### LangGraph Flow

```mermaid
graph LR
    A([🔍 analyze_root_cause\nClaude AI]) --> G([🕵️ critique_remediation\nconfidence 0-100])
    G --> B([⚖️ decide_action])
    B -->|auto-remediate + high confidence + non-critical| C([⚙️ execute_action])
    B -->|otherwise| D([⏳ await_human\nSlack · Telegram · WhatsApp])
    D -->|✅ Fix It| C
    D -->|🚫 Ignore| E([🚫 mark_ignored])
    C --> F([END])
    E --> F
```

> **Safety default:** `AUTO_REMEDIATE` is **off** out of the box, so *every* incident waits for explicit human approval. Enable it only when you want hands-off remediation for non-critical, high-confidence incidents in simulation mode.

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

### Command-line options

```bash
python main.py                      # run continuously (default)
python main.py --once               # one poll cycle, then exit (cron / CI)
python main.py --dry-run            # one cycle, simulation, console-only (no listeners)
python main.py --list-incidents 20  # print recent incidents from the DB and exit
python main.py --provider openai    # override LLM_PROVIDER for this run
python main.py --version
```

`SIGINT` / `SIGTERM` (Ctrl-C, `docker stop`) trigger a **graceful shutdown** — the loop finishes its current work and exits cleanly.

### Docker (one command)

```bash
cp .env.example .env   # fill in ANTHROPIC_API_KEY at minimum
docker-compose up
```

This starts the agent (`:8000` metrics + health), Prometheus (`:9090`), and Grafana (`:3000`, admin/admin) with the **OpenSRE dashboard auto-provisioned**.

---

## 📈 Observability

OpenSRE exposes two endpoints on port `8000`:

| Endpoint | Purpose |
|---|---|
| `/metrics` | Prometheus exposition |
| `/healthz` | JSON liveness/readiness probe (`{status, simulation_mode, llm_provider, model, active_incidents}`) |

**Metrics tracked:** `opensre_incidents_total` (by source/severity/status), `opensre_active_incidents` (gauge), `opensre_incident_resolution_seconds` (**MTTR**), `opensre_approval_latency_seconds`, `opensre_claude_latency_seconds`, and `opensre_action_duration_seconds`. A ready-made Grafana dashboard ([`grafana/dashboards/opensre.json`](grafana/dashboards/opensre.json)) is provisioned automatically via docker-compose.

---

## 📢 Notification Channels

OpenSRE supports **four notification channels** out of the box. Each is **optional and independent** — if none are configured, alerts print to the console (great for local development). **Slack and Telegram** offer interactive approve/ignore buttons; WhatsApp and Discord are notify-only.

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

> **Best for:** Personal projects, small teams, or free mobile push notifications worldwide. Supports **interactive approve/ignore buttons** (inline keyboard) — a background poller resumes the pipeline on a button press, just like Slack.

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

[ ✅ Fix It ]  [ 🚫 Ignore ]
```

---

### Discord

> **Best for:** Teams living in Discord who want incident alerts in a channel. **Notify-only** — incoming webhooks can't render interactive buttons (that needs a full bot app), so approvals happen via Slack or Telegram.

**Setup:**

1. In your server: **Channel → Edit Channel → Integrations → Webhooks → New Webhook**
2. Copy the webhook URL

```env
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/xxxx/yyyy
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
| `LLM_PROVIDER` | `anthropic` | No | Which LLM backend to use: `anthropic`, `openai`, or `google` |
| `ANTHROPIC_API_KEY` | — | Yes¹ | Claude API key from [console.anthropic.com](https://console.anthropic.com) (required when `LLM_PROVIDER=anthropic`) |
| `OPENSRE_MODEL` | `claude-sonnet-4-6` | No | Claude model to use for analysis |
| `OPENAI_API_KEY` | — | Yes¹ | OpenAI key (required when `LLM_PROVIDER=openai`) |
| `OPENAI_MODEL` | `gpt-4o-mini` | No | OpenAI model to use |
| `OPENAI_BASE_URL` | — | No | OpenAI-compatible endpoint (Azure / Groq / OpenRouter / Ollama, e.g. `http://localhost:11434/v1`) |
| `GOOGLE_API_KEY` | — | Yes¹ | Google AI key (or `GEMINI_API_KEY`; required when `LLM_PROVIDER=google`) |
| `GEMINI_MODEL` | `gemini-2.0-flash` | No | Gemini model to use |
| `SIMULATION_MODE` | `true` | No | `true` = no real cloud credentials needed |
| `AUTO_REMEDIATE` | `false` | No | `true` lets the agent auto-execute fixes for non-critical, high-confidence incidents (simulation mode only). Default keeps human-in-the-loop for everything. |
| `AUTO_APPROVE_MIN_CONFIDENCE` | `80` | No | Minimum self-critique confidence (0–100) required for autonomous action |
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
| `DISCORD_WEBHOOK_URL` | — | No | Discord incoming webhook URL (notify-only channel) |
| `AWS_REGION` | `us-east-1` | No | AWS region for CloudWatch / EC2 |
| `AWS_ACCESS_KEY_ID` | — | No | AWS access key (real mode only) |
| `AWS_SECRET_ACCESS_KEY` | — | No | AWS secret key (real mode only) |

¹ Exactly one LLM API key is required — whichever matches your `LLM_PROVIDER`.

---

## 🔌 LLM Providers

OpenSRE is **provider-agnostic**. All AI work (root cause analysis, self-critique,
post-mortems) goes through a single `complete()` interface in the [`llm/`](llm/)
package, so switching vendors is a config change — never a code change.

| Provider | `LLM_PROVIDER` | Install | Key |
|---|---|---|---|
| **Anthropic Claude** *(default)* | `anthropic` | `pip install anthropic` (already in `requirements.txt`) | `ANTHROPIC_API_KEY` |
| **OpenAI** | `openai` | `pip install openai` | `OPENAI_API_KEY` |
| **OpenAI-compatible** (Azure, Groq, OpenRouter, **Ollama**, vLLM) | `openai` | `pip install openai` | `OPENAI_API_KEY` + `OPENAI_BASE_URL` |
| **Google Gemini** | `google` | `pip install google-genai` | `GOOGLE_API_KEY` |

**Examples:**

```env
# Claude (default)
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...

# OpenAI
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini

# Local Ollama (free, offline) — OpenAI-compatible
LLM_PROVIDER=openai
OPENAI_API_KEY=ollama          # any non-empty value
OPENAI_BASE_URL=http://localhost:11434/v1
OPENAI_MODEL=llama3.1

# Google Gemini
LLM_PROVIDER=google
GOOGLE_API_KEY=...
GEMINI_MODEL=gemini-2.0-flash
```

> **Add your own provider** in three steps: subclass `LLMProvider` in `llm/`, implement
> `complete(system, user, max_tokens)`, and register it in `llm/__init__.py`.

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

### 🚀 v1.2 — Observability Stack (Complete)
- [x] Prometheus `/metrics` endpoint (incident counters, execution metrics, Claude latency)
- [x] Pre-built Grafana service integrated inside docker-compose configuration
- [ ] OpenTelemetry distributed tracing across LangGraph nodes

### 🚀 v1.3 — Smarter AI (In Progress)
- [x] Confidence scoring — low-confidence analysis always requires human approval
- [x] RAG on past incidents — Claude reads similar historical incidents before analyzing
- [x] Auto post-mortem generation after incident resolution
- [x] Opt-in autonomous remediation gated on confidence + severity (`AUTO_REMEDIATE`)
- [ ] Incident correlation — group related alerts into a single incident

### 🚀 v1.4 — Production Hardening (In Progress)
- [x] Operable CLI (`--once`, `--dry-run`, `--list-incidents`, `--provider`) + graceful shutdown
- [x] `/healthz` health probe + active-incidents gauge, MTTR & approval-latency metrics
- [x] Auto-provisioned Grafana dashboard (datasource + panels)
- [x] Discord notification channel; interactive approval on Telegram (not just Slack)
- [x] Pluggable multi-provider LLM layer (Anthropic / OpenAI / Gemini)
- [ ] Web dashboard with live incident feed
- [x] GitHub Actions CI pipeline (black linting, syntax checking, test runner workflow)
- [ ] Real AWS CloudWatch monitor integration
- [x] Custom Safety Guardrails preventing destructive action execution (similar to OPA)
- [x] Comprehensive PyTest unit test suite (covering storage, guardrails, nodes)

---

## 🧪 Testing

OpenSRE ships with a comprehensive offline test suite — **74 tests** covering safety
guardrails, the SQLite store, the local RAG ranking, the decision/critique logic, an
end-to-end LangGraph run (with a mocked LLM provider), the pluggable provider layer,
the monitors, config validation, the notification builders, Telegram approval logic,
the Discord channel, and the observability metrics/health. Everything runs in
**simulation mode with a mock API key** — no real credentials or network calls.

```bash
pip install -r requirements-dev.txt
pytest                                   # run the suite
pytest --cov=. --cov-report=term-missing # with coverage
```

The same suite runs in CI on Python 3.12 and 3.13, gated by `black` formatting and
`flake8` linting — see [`.github/workflows/ci.yml`](.github/workflows/ci.yml).

---

## 🤝 Contributing

Contributions are welcome and appreciated! This is an open learning project — whether you're fixing a bug, adding a new monitor, or improving documentation, all PRs are reviewed. See **[CONTRIBUTING.md](CONTRIBUTING.md)** for the full workflow, and our **[Code of Conduct](CODE_OF_CONDUCT.md)**.

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
| **Anthropic Claude / OpenAI / Google Gemini** | Pluggable LLM backends for root cause analysis and remediation recommendations |
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
