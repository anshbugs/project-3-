from __future__ import annotations

import argparse
import json
import logging
import os
from datetime import datetime, date
from glob import glob
from typing import Any, Dict, List, Tuple

from .config import ScrapeConfig
from .llm_gemini import generate_pulse_markdown


logger = logging.getLogger(__name__)


def _latest_grouped_file(cfg: ScrapeConfig) -> str:
    grouped_dir = os.path.join(cfg.data_dir, "grouped")
    pattern = os.path.join(grouped_dir, "grouped_reviews-*.json")
    files = glob(pattern)
    if not files:
        raise FileNotFoundError(f"No grouped_reviews-*.json found in {grouped_dir}")
    return sorted(files)[-1]


def _load_grouped(cfg: ScrapeConfig) -> Dict[str, Any]:
    path = _latest_grouped_file(cfg)
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data


def _compute_theme_stats(grouped: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], Dict[str, List[Dict[str, Any]]]]:
    themes: List[Dict[str, Any]] = grouped.get("themes", [])
    by_theme: Dict[str, List[Dict[str, Any]]] = grouped.get("byTheme", {})

    for t in themes:
        tid = t["id"]
        reviews = by_theme.get(tid, [])
        t["count"] = len(reviews)
        if reviews:
            t["avg_rating"] = sum(int(r.get("rating", 0)) for r in reviews) / len(reviews)
        else:
            t["avg_rating"] = 0.0

    themes.sort(key=lambda t: t.get("count", 0), reverse=True)
    return themes, by_theme


def _pick_top_themes_and_quotes(
    themes: List[Dict[str, Any]],
    by_theme: Dict[str, List[Dict[str, Any]]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    top_themes = themes[:3]

    # Flatten all reviews for quote selection.
    all_reviews: List[Dict[str, Any]] = []
    for tid in by_theme:
        all_reviews.extend(by_theme[tid])

    # Deduplicate by reviewId.
    seen = set()
    unique_reviews: List[Dict[str, Any]] = []
    for r in all_reviews:
        rid = r.get("reviewId")
        if rid in seen:
            continue
        seen.add(rid)
        unique_reviews.append(r)

    low_rating = [r for r in unique_reviews if int(r.get("rating", 0)) <= 2]
    others = [r for r in unique_reviews if int(r.get("rating", 0)) >= 3]

    quotes: List[Dict[str, Any]] = []
    if low_rating:
        quotes.append(low_rating[0])
    quotes.extend(others[: 3 - len(quotes)])

    # Fallback if we still have fewer than 3.
    if len(quotes) < 3:
        remaining = [r for r in unique_reviews if r not in quotes]
        quotes.extend(remaining[: 3 - len(quotes)])

    return top_themes, quotes[:3]


def _generate_markdown_pulse(
    grouped: Dict[str, Any],
    top_themes: List[Dict[str, Any]],
    quotes: List[Dict[str, Any]],
    report_date: date,
) -> str:
    week_of = report_date.isoformat()
    logger.info("Phase 3: calling Gemini to generate weekly pulse note")
    return generate_pulse_markdown(grouped, top_themes, quotes, week_of)


def run_phase3(report_date_str: str | None = None) -> Dict[str, str]:
    """
    Phase 3: Weekly note generation using Gemini.

    - Loads latest grouped_reviews-*.json (output of Phase 2).
    - Computes top 3 themes and selects 3 quotes.
    - Calls Gemini to generate a Markdown weekly pulse note (<=250 words).
    - Writes Markdown and plain-text files to data/notes/.
    """
    cfg = ScrapeConfig()
    grouped = _load_grouped(cfg)
    themes, by_theme = _compute_theme_stats(grouped)

    if not themes:
        raise RuntimeError("Phase 3: no themes found in grouped data")

    top_themes, quotes = _pick_top_themes_and_quotes(themes, by_theme)
    logger.info(
        "Phase 3: using top themes %s and %s quotes",
        [t["id"] for t in top_themes],
        len(quotes),
    )

    if report_date_str:
        report_date = datetime.fromisoformat(report_date_str).date()
    else:
        report_date = datetime.utcnow().date()

    markdown = _generate_markdown_pulse(grouped, top_themes, quotes, report_date)

    notes_dir = os.path.join(cfg.data_dir, "notes")
    os.makedirs(notes_dir, exist_ok=True)
    date_str = report_date.isoformat()
    md_path = os.path.join(notes_dir, f"pulse-{date_str}.md")
    txt_path = os.path.join(notes_dir, f"pulse-{date_str}.txt")

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(markdown)

    # For now, use the same content for plain text; Phase 4 can convert as needed.
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(markdown)

    logger.info("Phase 3: wrote weekly pulse note to %s and %s", md_path, txt_path)
    return {"markdown": md_path, "text": txt_path}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Phase 3: weekly pulse note generation using Gemini."
    )
    parser.add_argument(
        "--date",
        type=str,
        default=None,
        help="Optional report date YYYY-MM-DD (defaults to today).",
    )
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    args = _parse_args()
    run_phase3(report_date_str=args.date)


if __name__ == "__main__":
    main()

