# OpenSRE — Autonomous DevOps Agent

> An AI Site Reliability Engineer that monitors your infrastructure, detects incidents, finds root causes with Claude AI, and asks your team for approval before taking action.

## How It Works

```
Infrastructure → Monitor → LangGraph Agent → Claude AI → Slack Alert
     ↑                                                        ↓
     └──────────── Fix It / Ignore button ───────────────────┘
```

1. **Monitors** poll CPU, memory, databases, and Kubernetes every 30s
2. **LangGraph** runs the incident through a `DETECT → ANALYZE → DECIDE → ACT` pipeline
3. **Claude AI** reads the metrics and writes a root cause + recommended fix
4. **Slack** receives an alert card with "Fix It" and "Ignore" buttons
5. On approval, OpenSRE executes the fix (restart pod, kill query, scale deployment)

## Quick Start

### 1. Install dependencies
```bash
cd opensre
pip install -r requirements.txt
```

### 2. Configure
```bash
cp .env.example .env
# Edit .env — only ANTHROPIC_API_KEY is required to start
```

### 3. Run
```bash
python main.py
```

With `SIMULATION_MODE=true` (default), OpenSRE simulates CPU spikes, slow queries, and pod crashes — no real AWS or Kubernetes needed.

### Docker (one command)
```bash
cp .env.example .env  # fill in your API key
docker-compose up
```

## Configuration

| Variable | Default | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | required | Your Claude API key |
| `SIMULATION_MODE` | `true` | Simulate infrastructure events locally |
| `CPU_THRESHOLD_PCT` | `85` | Alert when CPU exceeds this % |
| `MEMORY_THRESHOLD_PCT` | `90` | Alert when memory exceeds this % |
| `SLOW_QUERY_THRESHOLD_MS` | `500` | Alert on queries slower than this |
| `POLL_INTERVAL_SECONDS` | `30` | How often to check metrics |
| `SLACK_BOT_TOKEN` | optional | Slack bot token for alerts |
| `SLACK_APP_TOKEN` | optional | Slack socket mode token |
| `SLACK_ALERT_CHANNEL` | `#incidents` | Channel to post alerts |

## Slack Setup (optional)

1. Create a Slack app at https://api.slack.com/apps
2. Enable **Socket Mode**
3. Add OAuth scopes: `chat:write`, `channels:read`
4. Subscribe to `block_actions` event
5. Set `SLACK_BOT_TOKEN` and `SLACK_APP_TOKEN` in `.env`

Without Slack tokens, alerts print to the console — useful for testing.

## Project Structure

```
opensre/
├── agent/          # LangGraph state machine (DETECT→ANALYZE→DECIDE→ACT)
├── monitors/       # CPU, memory, database, Kubernetes monitors
├── tools/          # AWS, Kubernetes, database action tools
├── notifications/  # Slack bot with button callbacks
├── storage/        # SQLite incident log
├── config.py       # All config via environment variables
└── main.py         # Entry point
```

## Extending OpenSRE

- **Add a monitor**: subclass `monitors/base.py:BaseMonitor` and implement `poll()`
- **Add a tool**: add a function to `tools/` and call it from `agent/nodes.py:execute_action`
- **Connect real AWS**: set `SIMULATION_MODE=false` and add AWS credentials to `.env`
- **Connect real K8s**: install `kubectl` and set `SIMULATION_MODE=false`

## Tech Stack

- **Python 3.12** + **asyncio**
- **LangGraph** — agent state machine
- **Anthropic Claude** — root cause analysis
- **Slack Bolt** — real-time bot with button interactions
- **psutil** — local CPU/memory monitoring
- **SQLite** — zero-setup incident storage
- **Docker** — one-command deployment

## License

MIT — free to use, modify, and deploy.
