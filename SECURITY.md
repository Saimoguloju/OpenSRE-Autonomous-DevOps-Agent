# Security Policy

## Supported versions

OpenSRE is an active open-source project; security fixes target the `main` branch.

## Reporting a vulnerability

**Please do not open a public issue for security vulnerabilities.**

Instead, use GitHub's [private vulnerability reporting](https://github.com/Saimoguloju/OpenSRE-Autonomous-DevOps-Agent/security/advisories/new)
(Security → Report a vulnerability), or email the maintainer at
`sai.moguloju@elisiontec.com` with:

- a description of the issue and its impact,
- steps to reproduce, and
- any suggested remediation.

You can expect an acknowledgement within **5 business days** and a coordinated
disclosure once a fix is available.

## Security model & hardening notes

OpenSRE executes remediation actions against real infrastructure when
`SIMULATION_MODE=false`. Keep these in mind when deploying:

- **Secrets** live only in `.env` (git-ignored). Never commit real tokens. Rotate any
  credential that is accidentally exposed.
- **Guardrails** (`agent/guardrails.py`) deterministically block destructive commands
  (`rm -rf`, `DROP DATABASE`, system-namespace deletes, command chaining) before any
  tool runs. Treat them as defense-in-depth, not a substitute for least-privilege
  credentials.
- **Human-in-the-loop** is the default: with `AUTO_REMEDIATE` unset, every incident
  requires explicit human approval before any action is taken.
- **Least privilege**: give the agent's AWS / kubectl / database credentials only the
  permissions required for the remediation tools you enable.
