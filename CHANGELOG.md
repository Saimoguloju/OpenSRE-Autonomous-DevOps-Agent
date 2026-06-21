# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Interactive Telegram approvals**: inline Approve/Ignore buttons + a background
  poller that resumes the pipeline on a button press (previously Slack-only).
- **Discord notification channel** via incoming webhook (notify-only).
- **Observability upgrade**: `opensre_active_incidents` gauge, MTTR
  (`opensre_incident_resolution_seconds`) and approval-latency histograms, a
  `/healthz` JSON probe served alongside `/metrics`, and an auto-provisioned
  Grafana dashboard + Prometheus datasource (`grafana/`).
- **Operable CLI**: `--once`, `--dry-run`, `--list-incidents`, `--provider`,
  `--version`, plus graceful SIGINT/SIGTERM shutdown of the asyncio loop.
- **Pluggable multi-provider LLM layer** (`llm/`): choose Anthropic Claude
  (default), OpenAI (and any OpenAI-compatible endpoint — Azure, Groq,
  OpenRouter, Ollama, vLLM — via `OPENAI_BASE_URL`), or Google Gemini with a
  single `LLM_PROVIDER` env var. Agent nodes now call a provider-agnostic
  `complete()` interface; optional SDKs are imported lazily.
- `config.active_model` and provider-aware `config.validate()`.
- Opt-in autonomous remediation (`AUTO_REMEDIATE`) that lets the agent execute
  fixes for non-critical, high-confidence incidents in simulation mode.
- `AUTO_APPROVE_MIN_CONFIDENCE` config to gate autonomous action on the
  self-critique confidence score.
- `resume_incident()` helper that continues an incident after human approval
  without re-running the Claude analysis (saves a second LLM round-trip).
- MIT `LICENSE`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`,
  `pyproject.toml`, dev dependencies, and GitHub issue/PR templates.
- Substantially expanded test suite: monitors, config validation, dispatcher
  fan-out, notifier message builders, the decision logic, and an end-to-end
  graph run with a mocked Claude client.

### Fixed
- Console output is forced to UTF-8, fixing a `UnicodeEncodeError` crash when
  printing the banner/emojis on a non-UTF-8 (cp1252) Windows console.
- WhatsApp alerts no longer instruct users to "reply approve" (there was no
  inbound handler); they now point to Slack/Telegram for approval.
- The decision node now ties autonomous action to the self-critique confidence
  score instead of an unreachable severity branch (monitors only emit breaches,
  so `severity == "low"` was never produced in the live loop).
- Human approval no longer re-runs the full LangGraph pipeline (and a second
  Claude call) — it routes directly to execution.
- `BaseMonitor.severity` is now a `@staticmethod` (removes the `__new__` hack in
  `main.py`) and guards against a zero threshold.

## [1.2.0]
- Prometheus `/metrics` endpoint and Grafana service in docker-compose.
- Automatic blameless post-mortem generation after incident resolution.

## [1.1.0]
- Telegram and WhatsApp notifications; multi-channel parallel dispatcher.
- Fingerprint-based alert deduplication.

## [1.0.0]
- Initial release: LangGraph state machine, Claude root cause analysis,
  Slack human-in-the-loop, SQLite persistence, Docker, simulation mode.
