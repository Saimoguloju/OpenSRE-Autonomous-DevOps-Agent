# Contributing to OpenSRE

Thanks for your interest in improving OpenSRE! This is an open learning project and
contributions of all sizes are welcome — bug fixes, new monitors, new notification
channels, docs, and tests.

## Quick start

```bash
git clone https://github.com/Saimoguloju/OpenSRE-Autonomous-DevOps-Agent.git
cd OpenSRE-Autonomous-DevOps-Agent
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
cp .env.example .env              # set ANTHROPIC_API_KEY (SIMULATION_MODE=true is the default)
```

## Development workflow

1. **Fork** the repository and create a feature branch:
   ```bash
   git checkout -b feat/your-feature-name
   ```
2. **Make your change.** Keep it focused — one logical change per PR.
3. **Format** with Black (the CI enforces this):
   ```bash
   black .
   ```
4. **Lint** with flake8:
   ```bash
   flake8 . --exclude venv/
   ```
5. **Test** — all tests must pass and new behavior needs a test:
   ```bash
   pytest
   ```
6. **Commit** using [Conventional Commits](https://www.conventionalcommits.org/):
   `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`.
7. **Open a Pull Request** with a clear description of *what* changed and *why*.

## Running tests

The full suite runs offline against `SIMULATION_MODE=true` with a mocked
Anthropic API key — no real credentials or network calls are required:

```bash
pytest                 # run everything
pytest -q              # quiet
pytest --cov=. --cov-report=term-missing   # with coverage
```

## What makes a good first contribution

- **Add a monitor** (Redis, Nginx, Elasticsearch) — subclass `BaseMonitor` in `monitors/`.
- **Add a notification channel** (Discord, PagerDuty, MS Teams) — add a notifier in
  `notifications/` and register it in `dispatcher.py`.
- **Add a remediation tool** in `tools/` and wire it into `agent/nodes.execute_action`.
- **Improve test coverage** for any module.

See the **Extending OpenSRE** section of the [README](README.md) for code templates.

## Code style

- Python 3.12+, formatted with Black (line length 88).
- Type hints on public functions where practical.
- Prefer small, pure functions and keep side effects (network, disk) at the edges.
- New features that touch the agent pipeline should run in **simulation mode** without
  real cloud credentials.

## Reporting bugs / requesting features

Open an issue using the templates under `.github/ISSUE_TEMPLATE/`. For security
issues, please follow [SECURITY.md](SECURITY.md) instead of opening a public issue.
