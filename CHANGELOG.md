# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
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
