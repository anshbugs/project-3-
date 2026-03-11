from __future__ import annotations

import argparse
import logging
from typing import Optional

from . import phase1, phase2, phase3, phase4


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="GROWW weekly pulse pipeline CLI (scrape → analyze → classify → report → email)."
    )
    parser.add_argument(
        "--phase",
        choices=["scrape", "analyze", "classify", "report", "email", "all"],
        default="all",
        help="Which phase to run (default: all).",
    )
    parser.add_argument(
        "--weeks",
        type=int,
        default=None,
        help="Review window in weeks for scrape (8–12; default from config).",
    )
    parser.add_argument(
        "--max-reviews",
        type=int,
        default=None,
        help="Maximum reviews to keep in Phase 1 (default from config).",
    )
    parser.add_argument(
        "--date",
        type=str,
        default=None,
        help="Optional report date YYYY-MM-DD for Phase 3/4 (defaults to today / filenames).",
    )
    parser.add_argument(
        "--recipient",
        type=str,
        default=None,
        help="Recipient email for Phase 4 (can also be provided by frontend).",
    )
    parser.add_argument(
        "--recipient-name",
        type=str,
        default=None,
        help='Recipient name for greeting in Phase 4 ("Hi {name},").',
    )
    parser.add_argument(
        "--send",
        action="store_true",
        help="In Phase 4, actually send email via SMTP instead of just writing .eml.",
    )
    return parser.parse_args()


def run_pipeline(
    phase: str,
    weeks: Optional[int],
    max_reviews: Optional[int],
    report_date_str: Optional[str],
    recipient: Optional[str],
    recipient_name: Optional[str],
    send: bool,
) -> None:
    """
    Orchestrate the pipeline phases based on CLI or API parameters.
    """
    if phase in ("scrape", "all"):
        logging.info("Running Phase 1: scrape & normalize")
        phase1.scrape_and_normalize(weeks=weeks, max_reviews=max_reviews)

    if phase in ("analyze", "classify", "all"):
        # Our Phase 2 combines theme discovery + classification.
        logging.info("Running Phase 2: themes & classification")
        phase2.run_phase2()

    if phase in ("report", "all"):
        logging.info("Running Phase 3: weekly pulse note")
        phase3.run_phase3(report_date_str=report_date_str)

    if phase in ("email", "all"):
        logging.info("Running Phase 4: email draft/send")
        phase4.run_phase4(
            report_date_str=report_date_str,
            recipient=recipient,
            recipient_name=recipient_name,
            send=send,
        )


def cli() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    args = _parse_args()
    run_pipeline(
        phase=args.phase,
        weeks=args.weeks,
        max_reviews=args.max_reviews,
        report_date_str=args.date,
        recipient=args.recipient,
        recipient_name=args.recipient_name,
        send=args.send,
    )


if __name__ == "__main__":
    cli()

