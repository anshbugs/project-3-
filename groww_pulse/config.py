from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class ScrapeConfig:
    app_id: str = os.getenv("GROWW_APP_ID", "com.nextbillion.groww")
    lang: str = os.getenv("GROWW_LANG", "en")
    country: str = os.getenv("GROWW_COUNTRY", "in")

    min_weeks: int = int(os.getenv("GROWW_MIN_WEEKS", "8"))
    max_weeks: int = int(os.getenv("GROWW_MAX_WEEKS", "12"))
    default_weeks: int = int(os.getenv("GROWW_DEFAULT_WEEKS", "10"))

    max_reviews: int = int(os.getenv("GROWW_MAX_REVIEWS", "400"))
    min_text_chars: int = int(os.getenv("GROWW_MIN_TEXT_CHARS", "100"))

    data_dir: str = os.getenv("GROWW_DATA_DIR", "data")

    @property
    def raw_dir(self) -> str:
        return os.path.join(self.data_dir, "raw")

    @property
    def normalized_dir(self) -> str:
        return os.path.join(self.data_dir, "normalized")


@dataclass(frozen=True)
class GeminiConfig:
    api_key: str = os.getenv("GEMINI_API_KEY", "")
    model: str = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

    def ensure_present(self) -> None:
        if not self.api_key:
            raise RuntimeError(
                "GEMINI_API_KEY is not set. Please add it to your environment or .env file."
            )


@dataclass(frozen=True)
class EmailConfig:
    sender: str = os.getenv("EMAIL_SENDER", "")
    password: str = os.getenv("EMAIL_PASSWORD", "")
    smtp_host: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port: int = int(os.getenv("SMTP_PORT", "587"))
    default_recipient: str = os.getenv("EMAIL_RECIPIENT", "")


@dataclass(frozen=True)
class SchedulerConfig:
    interval_minutes: int = int(os.getenv("GROWW_SCHEDULER_INTERVAL_MINUTES", "5"))
    weeks: int = int(os.getenv("GROWW_SCHEDULER_WEEKS", "8"))
    max_reviews: int = int(os.getenv("GROWW_SCHEDULER_MAX_REVIEWS", "400"))
    recipient: str = os.getenv("GROWW_SCHEDULER_RECIPIENT", "anshbhalla421@gmail.com")
    # Weekly run: day 0=Monday, 1=Tuesday, ... 6=Sunday; hour 0-23 (24h).
    day_of_week: int = int(os.getenv("GROWW_SCHEDULER_DAY", "0"))  # Monday
    hour: int = int(os.getenv("GROWW_SCHEDULER_HOUR", "23"))  # 11pm
    minute: int = int(os.getenv("GROWW_SCHEDULER_MINUTE", "0"))


def ensure_data_dirs(cfg: ScrapeConfig) -> None:
    os.makedirs(cfg.raw_dir, exist_ok=True)
    os.makedirs(cfg.normalized_dir, exist_ok=True)

