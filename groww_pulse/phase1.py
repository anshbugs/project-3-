from __future__ import annotations

import argparse
import json
import logging
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from google_play_scraper import Sort, reviews

from .config import ScrapeConfig, ensure_data_dirs
from .pii import sanitize_review_text
from .lang_filter import is_english


logger = logging.getLogger(__name__)


@dataclass
class NormalizedReview:
    reviewId: str
    rating: int
    title: Optional[str]
    text: str
    date: str  # ISO8601


def _clamp_weeks(cfg: ScrapeConfig, weeks: Optional[int]) -> int:
    if weeks is None:
        weeks = cfg.default_weeks
    return max(cfg.min_weeks, min(cfg.max_weeks, weeks))


def scrape_and_normalize(
    weeks: Optional[int] = None,
    max_reviews: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Phase 1: Scrape Play Store reviews for GROWW and write normalized JSON.

    - Scrapes around `max_reviews` newest reviews (default 400).
    - Restricts to the last 8–12 weeks.
    - Keeps only reviews whose sanitised text has >= min_text_chars characters.
    - Keeps only reviews detected as English.
    """
    cfg = ScrapeConfig()
    ensure_data_dirs(cfg)

    weeks = _clamp_weeks(cfg, weeks)
    if max_reviews is None:
        max_reviews = cfg.max_reviews

    now = datetime.now(timezone.utc)
    min_date = now - timedelta(weeks=weeks)

    logger.info(
        "Phase 1: scraping Play Store reviews for %s (weeks=%s, max_reviews=%s, lang=%s, country=%s)",
        cfg.app_id,
        weeks,
        max_reviews,
        cfg.lang,
        cfg.country,
    )

    all_raw: List[Dict[str, Any]] = []
    normalized: List[NormalizedReview] = []

    continuation_token = None
    remaining = max_reviews

    while remaining > 0:
        batch_size = min(200, remaining)
        batch, continuation_token = reviews(
            cfg.app_id,
            lang=cfg.lang,
            country=cfg.country,
            sort=Sort.NEWEST,
            count=batch_size,
            continuation_token=continuation_token,
        )
        if not batch:
            break

        all_raw.extend(batch)

        for r in batch:
            at: datetime = r["at"]
            # google_play_scraper may return naive datetimes; normalise to UTC-aware.
            if at.tzinfo is None:
                at = at.replace(tzinfo=timezone.utc)

            if at < min_date:
                # Reviews are newest-first; once outside the window we can stop.
                continuation_token = None
                break

            raw_text = (r.get("content") or "").strip()
            sanitised = sanitize_review_text(raw_text)
            if not sanitised:
                continue

            if len(sanitised) < cfg.min_text_chars:
                continue

            if not is_english(sanitised):
                continue

            review = NormalizedReview(
                reviewId=str(r.get("reviewId", "")),
                rating=int(r.get("score", 0)),
                title=(r.get("title") or None),
                text=sanitised,
                date=at.astimezone(timezone.utc).isoformat(),
            )
            normalized.append(review)
            remaining -= 1

            if remaining <= 0:
                break

        if continuation_token is None:
            break

    date_str = now.date().isoformat()

    # Optional: store raw snapshot for debugging (not to be shared/committed).
    raw_path = os.path.join(cfg.raw_dir, f"playstore-raw-{date_str}.json")
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(all_raw, f, ensure_ascii=False, default=str, indent=2)

    payload: Dict[str, Any] = {
        "generatedAt": now.isoformat(),
        "sourceFile": raw_path,
        "appId": cfg.app_id,
        "platform": "play_store",
        "weeksWindow": weeks,
        "reviews": [asdict(r) for r in normalized],
    }

    out_path = os.path.join(cfg.normalized_dir, f"reviews-{date_str}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    # Separate file with just the normalized reviews array for convenience.
    reviews_only_path = os.path.join(
        cfg.normalized_dir, f"reviews-only-{date_str}.json"
    )
    with open(reviews_only_path, "w", encoding="utf-8") as f:
        json.dump([asdict(r) for r in normalized], f, ensure_ascii=False, indent=2)

    logger.info(
        "Phase 1: wrote %s normalized reviews (>= %s chars) to %s and %s (raw=%s)",
        len(normalized),
        cfg.min_text_chars,
        out_path,
        reviews_only_path,
        raw_path,
    )

    return payload


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Phase 1: scrape and normalize GROWW Play Store reviews."
    )
    parser.add_argument(
        "--weeks",
        type=int,
        default=None,
        help="Review window in weeks (will be clamped to 8–12; default from config).",
    )
    parser.add_argument(
        "--max-reviews",
        type=int,
        default=None,
        help="Maximum number of reviews to keep after filtering (default 400).",
    )
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    args = _parse_args()
    scrape_and_normalize(weeks=args.weeks, max_reviews=args.max_reviews)


if __name__ == "__main__":
    main()

