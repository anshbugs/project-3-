from __future__ import annotations

import argparse
import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from glob import glob
from typing import Any, Dict, List, Sequence

from .config import ScrapeConfig
from .llm_openrouter import classify_reviews_into_themes, generate_themes_from_reviews


logger = logging.getLogger(__name__)


@dataclass
class Theme:
    id: str
    label: str
    description: str


def _latest_normalized_file(cfg: ScrapeConfig) -> str:
    # Match only the full normalized payload files like reviews-YYYY-MM-DD.json,
    # not the reviews-only-*.json helper files.
    pattern = os.path.join(cfg.normalized_dir, "reviews-[0-9]*.json")
    candidates = glob(pattern)
    if not candidates:
        raise FileNotFoundError(f"No normalized reviews files found matching {pattern}")
    return sorted(candidates)[-1]


def _load_reviews(cfg: ScrapeConfig) -> Dict[str, Any]:
    path = _latest_normalized_file(cfg)
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data


def _sample_for_themes(reviews: Sequence[Dict[str, Any]], sample_size: int = 120) -> List[Dict[str, Any]]:
    # Stratify by rating 1–5 to keep balance.
    buckets: Dict[int, List[Dict[str, Any]]] = {i: [] for i in range(1, 6)}
    for r in reviews:
        rating = int(r.get("rating", 0))
        if rating in buckets:
            buckets[rating].append(r)

    per_bucket = max(1, sample_size // 5)
    sample: List[Dict[str, Any]] = []
    for rating in range(1, 6):
        bucket = buckets[rating]
        sample.extend(bucket[:per_bucket])
    return sample[:sample_size]


def run_phase2() -> str:
    """
    Phase 2: Theme discovery and classification using a model on OpenRouter.

    - Loads latest normalized reviews JSON (output of Phase 1).
    - Uses a sample to generate 3–5 themes via OpenRouter.
    - Classifies every review into exactly one theme via OpenRouter, in batches.
    - Writes grouped output JSON for downstream phases.
    """
    cfg = ScrapeConfig()
    data = _load_reviews(cfg)
    all_reviews: List[Dict[str, Any]] = data.get("reviews", [])

    logger.info("Phase 2: loaded %s normalized reviews for theming/classification", len(all_reviews))

    # 2a: theme discovery
    sample = _sample_for_themes(all_reviews)
    logger.info("Phase 2a: sending %s sampled reviews to OpenRouter for theme discovery", len(sample))
    raw_themes = generate_themes_from_reviews(sample)

    themes: List[Theme] = [
        Theme(id=t["id"], label=t["label"], description=t["description"])
        for t in raw_themes
    ]

    logger.info(
        "Phase 2a: discovered %s themes: %s",
        len(themes),
        [t.id for t in themes],
    )

    # 2b: classification
    id_to_review: Dict[str, Dict[str, Any]] = {
        str(r.get("reviewId", "")): r for r in all_reviews if r.get("reviewId")
    }

    def _batches(seq: Sequence[Dict[str, Any]], size: int) -> Sequence[Sequence[Dict[str, Any]]]:
        for i in range(0, len(seq), size):
            yield seq[i : i + size]

    theme_dicts = [vars(t) for t in themes]
    assignments: Dict[str, str] = {}
    batch_size = 50

    for batch in _batches(all_reviews, batch_size):
        classified = classify_reviews_into_themes(theme_dicts, batch)
        logger.info("Phase 2b: classified batch of %s reviews; got %s mappings", len(batch), len(classified))
        for item in classified:
            rid = item["reviewId"]
            theme_id = item["theme_id"]
            if rid in id_to_review:
                assignments[rid] = theme_id

    # Group by theme; unassigned can go into largest theme or an "unclassified" bucket.
    by_theme: Dict[str, List[Dict[str, Any]]] = {t.id: [] for t in themes}
    unclassified: List[Dict[str, Any]] = []

    for rid, review in id_to_review.items():
        theme_id = assignments.get(rid)
        if theme_id in by_theme:
            by_theme[theme_id].append(review)
        else:
            unclassified.append(review)

    # If we have many unclassified, optionally assign them to the largest theme.
    if unclassified and by_theme:
        largest_theme_id = max(by_theme.items(), key=lambda kv: len(kv[1]))[0]
        by_theme[largest_theme_id].extend(unclassified)
        logger.info(
            "Phase 2b: assigned %s previously unclassified reviews to largest theme '%s'",
            len(unclassified),
            largest_theme_id,
        )
        unclassified = []

    grouped = {
        "generatedAt": datetime.utcnow().isoformat() + "Z",
        "sourceReviewsFile": _latest_normalized_file(cfg),
        "themes": [vars(t) for t in themes],
        "byTheme": by_theme,
        "unclassified": unclassified,
    }

    grouped_dir = os.path.join(cfg.data_dir, "grouped")
    os.makedirs(grouped_dir, exist_ok=True)
    today = datetime.utcnow().date().isoformat()
    out_path = os.path.join(grouped_dir, f"grouped_reviews-{today}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(grouped, f, ensure_ascii=False, indent=2)

    logger.info("Phase 2: wrote grouped reviews to %s", out_path)
    return out_path


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Phase 2: theme discovery and review classification using OpenAI."
    )
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    _parse_args()
    run_phase2()


if __name__ == "__main__":
    main()

