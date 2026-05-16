import os
from dataclasses import dataclass, field


@dataclass
class Config:
    # LLM
    anthropic_api_key: str = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", ""))
    model: str = field(default_factory=lambda: os.getenv("OPENSRE_MODEL", "claude-sonnet-4-6"))

    # Slack
    slack_bot_token: str = field(default_factory=lambda: os.getenv("SLACK_BOT_TOKEN", ""))
    slack_app_token: str = field(default_factory=lambda: os.getenv("SLACK_APP_TOKEN", ""))
    slack_alert_channel: str = field(default_factory=lambda: os.getenv("SLACK_ALERT_CHANNEL", "#incidents"))

    # Monitor thresholds
    cpu_threshold_pct: float = field(default_factory=lambda: float(os.getenv("CPU_THRESHOLD_PCT", "85")))
    memory_threshold_pct: float = field(default_factory=lambda: float(os.getenv("MEMORY_THRESHOLD_PCT", "90")))
    slow_query_threshold_ms: int = field(default_factory=lambda: int(os.getenv("SLOW_QUERY_THRESHOLD_MS", "500")))
    poll_interval_seconds: int = field(default_factory=lambda: int(os.getenv("POLL_INTERVAL_SECONDS", "30")))

    # Storage
    db_path: str = field(default_factory=lambda: os.getenv("OPENSRE_DB_PATH", "opensre_incidents.db"))

    # AWS (optional)
    aws_region: str = field(default_factory=lambda: os.getenv("AWS_REGION", "us-east-1"))
    aws_access_key_id: str = field(default_factory=lambda: os.getenv("AWS_ACCESS_KEY_ID", ""))
    aws_secret_access_key: str = field(default_factory=lambda: os.getenv("AWS_SECRET_ACCESS_KEY", ""))

    # Simulation mode — runs without real AWS/K8s/DB
    simulation_mode: bool = field(default_factory=lambda: os.getenv("SIMULATION_MODE", "true").lower() == "true")

    def validate(self):
        if not self.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY is required. Set it in your .env file.")
        if not self.simulation_mode and not self.slack_bot_token:
            raise ValueError("SLACK_BOT_TOKEN is required when SIMULATION_MODE=false.")


config = Config()
