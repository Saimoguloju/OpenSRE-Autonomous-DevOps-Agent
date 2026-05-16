import os
from dataclasses import dataclass, field


@dataclass
class Config:
    # ── LLM ────────────────────────────────────────────────────────────────
    anthropic_api_key: str = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", ""))
    model: str = field(default_factory=lambda: os.getenv("OPENSRE_MODEL", "claude-sonnet-4-6"))

    # ── Slack (optional) ────────────────────────────────────────────────────
    slack_bot_token: str = field(default_factory=lambda: os.getenv("SLACK_BOT_TOKEN", ""))
    slack_app_token: str = field(default_factory=lambda: os.getenv("SLACK_APP_TOKEN", ""))
    slack_alert_channel: str = field(default_factory=lambda: os.getenv("SLACK_ALERT_CHANNEL", "#incidents"))

    # ── Telegram (optional) ─────────────────────────────────────────────────
    # Get bot token from @BotFather on Telegram
    telegram_bot_token: str = field(default_factory=lambda: os.getenv("TELEGRAM_BOT_TOKEN", ""))
    # The chat_id where alerts will be sent (group, channel, or personal chat)
    telegram_chat_id: str = field(default_factory=lambda: os.getenv("TELEGRAM_CHAT_ID", ""))

    # ── WhatsApp via Twilio (optional) ──────────────────────────────────────
    # Sign up at twilio.com — sandbox is free for testing
    twilio_account_sid: str = field(default_factory=lambda: os.getenv("TWILIO_ACCOUNT_SID", ""))
    twilio_auth_token: str = field(default_factory=lambda: os.getenv("TWILIO_AUTH_TOKEN", ""))
    # Twilio sandbox number (default) or your approved WhatsApp Business number
    twilio_whatsapp_from: str = field(
        default_factory=lambda: os.getenv("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")
    )
    # Comma-separated WhatsApp numbers to alert e.g. "whatsapp:+91XXXXXXXXXX,whatsapp:+1XXXXXXXXXX"
    whatsapp_alert_numbers: str = field(
        default_factory=lambda: os.getenv("WHATSAPP_ALERT_NUMBERS", "")
    )

    # ── Monitor thresholds ──────────────────────────────────────────────────
    cpu_threshold_pct: float = field(default_factory=lambda: float(os.getenv("CPU_THRESHOLD_PCT", "85")))
    memory_threshold_pct: float = field(default_factory=lambda: float(os.getenv("MEMORY_THRESHOLD_PCT", "90")))
    slow_query_threshold_ms: int = field(default_factory=lambda: int(os.getenv("SLOW_QUERY_THRESHOLD_MS", "500")))
    poll_interval_seconds: int = field(default_factory=lambda: int(os.getenv("POLL_INTERVAL_SECONDS", "30")))

    # ── Alert deduplication ─────────────────────────────────────────────────
    # Suppress repeated alerts for the same metric+host for this many seconds
    alert_cooldown_seconds: int = field(
        default_factory=lambda: int(os.getenv("ALERT_COOLDOWN_SECONDS", "300"))
    )

    # ── Storage ─────────────────────────────────────────────────────────────
    db_path: str = field(default_factory=lambda: os.getenv("OPENSRE_DB_PATH", "opensre_incidents.db"))
    # PostgreSQL URL — only needed when SIMULATION_MODE=false and using real DB tools
    # Example: postgresql://user:password@localhost:5432/mydb
    db_url: str = field(default_factory=lambda: os.getenv("DATABASE_URL", ""))

    # ── AWS (optional) ──────────────────────────────────────────────────────
    aws_region: str = field(default_factory=lambda: os.getenv("AWS_REGION", "us-east-1"))
    aws_access_key_id: str = field(default_factory=lambda: os.getenv("AWS_ACCESS_KEY_ID", ""))
    aws_secret_access_key: str = field(default_factory=lambda: os.getenv("AWS_SECRET_ACCESS_KEY", ""))

    # ── Simulation mode — runs without real AWS/K8s/DB ──────────────────────
    simulation_mode: bool = field(
        default_factory=lambda: os.getenv("SIMULATION_MODE", "true").lower() == "true"
    )

    def validate(self):
        if not self.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY is required. Set it in your .env file.")

        # Warn if no notification channel is configured
        has_slack = bool(self.slack_bot_token)
        has_telegram = bool(self.telegram_bot_token and self.telegram_chat_id)
        has_whatsapp = bool(self.twilio_account_sid and self.whatsapp_alert_numbers)

        if not (has_slack or has_telegram or has_whatsapp):
            # Console fallback is still available — just warn, don't fail
            import logging
            logging.getLogger("opensre.config").warning(
                "No notification channel configured (Slack/Telegram/WhatsApp). "
                "Alerts will print to console only."
            )

        if not self.simulation_mode and not self.db_url:
            raise ValueError(
                "DATABASE_URL is required when SIMULATION_MODE=false and real DB tools are used. "
                "Example: postgresql://user:password@localhost:5432/mydb"
            )

    @property
    def whatsapp_recipients(self) -> list[str]:
        """Return list of WhatsApp 'whatsapp:+XXXX' strings."""
        if not self.whatsapp_alert_numbers:
            return []
        return [n.strip() for n in self.whatsapp_alert_numbers.split(",") if n.strip()]


config = Config()
