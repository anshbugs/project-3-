from __future__ import annotations

import json
import os
from datetime import datetime
from glob import glob
from typing import Any, Dict, List

from .lang_filter import is_english


def _latest_reviews_only_file(base_dir: str) -> str:
    pattern = os.path.join(base_dir, "data", "normalized", "reviews-only-*.json")
    candidates = glob(pattern)
    if not candidates:
        raise FileNotFoundError(f"No reviews-only JSON files found matching {pattern}")
    return sorted(candidates)[-1]


def filter_and_sort_english_reviews(base_dir: str | None = None) -> str:
    """
    Load the latest reviews-only JSON, keep only English reviews, sort them,
    and write an `*-en.json` file with the filtered array.

    Returns:
        Path to the filtered JSON file.
    """
    if base_dir is None:
        base_dir = os.getcwd()

    src_path = _latest_reviews_only_file(base_dir)
    with open(src_path, "r", encoding="utf-8") as f:
        reviews: List[Dict[str, Any]] = json.load(f)

    english_reviews: List[Dict[str, Any]] = [
        r for r in reviews if is_english(r.get("text", ""))
    ]

    def _parse_date(d: str) -> datetime:
        try:
            return datetime.fromisoformat(d)
        except Exception:
            return datetime.min

    # Sort by date (newest first), then rating (highest first).
    english_reviews.sort(
        key=lambda r: (_parse_date(r.get("date", "")), r.get("rating", 0)),
        reverse=True,
    )

    out_path = src_path.replace(".json", "-en.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(english_reviews, f, ensure_ascii=False, indent=2)

    return out_path


if __name__ == "__main__":
    out = filter_and_sort_english_reviews()
    print(out)

