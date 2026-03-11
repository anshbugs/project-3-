"""
Weekly pulse scheduler: runs the full pipeline once per week at a fixed time (default Monday 11pm)
using the CLI. Recipient is fixed to anshbhalla421@gmail.com (overridable via GROWW_SCHEDULER_RECIPIENT).
"""
from __future__ import annotations

import logging
import os
import subprocess
import sys
import time
from datetime import datetime, time, timedelta

from groww_pulse.config import SchedulerConfig, ScrapeConfig


def configure_logging(log_path: str) -> None:
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_path, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


def next_run_at(day_of_week: int, hour: int, minute: int) -> datetime:
    """Next occurrence of weekday at hour:minute (local time)."""
    now = datetime.now()
    days_ahead = (day_of_week - now.weekday()) % 7
    next_date = now.date() + timedelta(days=days_ahead)
    next_dt = datetime.combine(next_date, time(hour, minute, 0))
    if next_dt <= now:
        next_dt += timedelta(days=7)
    return next_dt


def run_weekly_pulse_cli(scfg: SchedulerConfig) -> int:
    """Invoke the pipeline via CLI. Returns process return code."""
    cmd = [
        sys.executable,
        "-m",
        "groww_pulse.main",
        "--phase",
        "all",
        "--weeks",
        str(scfg.weeks),
        "--max-reviews",
        str(scfg.max_reviews),
        "--recipient",
        scfg.recipient,
        "--send",
    ]
    logging.info("Scheduler: running CLI: %s", " ".join(cmd))
    # Capture the full pipeline output so it is also stored in the scheduler log.
    result = subprocess.run(
        cmd,
        cwd=os.getcwd(),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    if result.stdout:
        logging.info("Pipeline output (via CLI):\n%s", result.stdout)
    return result.returncode


def main() -> None:
    scfg = SchedulerConfig()
    data_cfg = ScrapeConfig()

    log_path = os.path.join(data_cfg.data_dir, "logs", "scheduler.log")
    configure_logging(log_path)

    weekdays = "Mon Tue Wed Thu Fri Sat Sun".split()
    day_name = weekdays[scfg.day_of_week] if 0 <= scfg.day_of_week <= 6 else "?"

    logging.info(
        "Starting weekly scheduler: every %s at %02d:%02d, weeks=%s, max_reviews=%s, recipient=%s",
        day_name,
        scfg.hour,
        scfg.minute,
        scfg.weeks,
        scfg.max_reviews,
        scfg.recipient,
    )

    while True:
        next_run = next_run_at(scfg.day_of_week, scfg.hour, scfg.minute)
        wait_seconds = (next_run - datetime.now()).total_seconds()
        wait_seconds = max(1, int(wait_seconds))
        logging.info("Next run at %s (in %s seconds)", next_run.isoformat(), wait_seconds)
        time.sleep(wait_seconds)

        try:
            code = run_weekly_pulse_cli(scfg)
            if code == 0:
                logging.info("Scheduler cycle completed successfully.")
            else:
                logging.warning("Scheduler cycle exited with code %s", code)
        except Exception as exc:
            logging.exception("Scheduler cycle failed: %s", exc)


if __name__ == "__main__":
    main()
