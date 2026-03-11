from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Sequence

from openai import OpenAI

from .retry_network import with_network_retry


class OpenRouterConfig:
    """
    Configuration for using OpenRouter's OpenAI-compatible API.
    """

    def __init__(self) -> None:
        self.api_key = os.getenv("OPENROUTER_API_KEY", "")
        self.model = os.getenv(
            "OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct"
        )
        if not self.api_key:
            raise RuntimeError(
                "OPENROUTER_API_KEY is not set. Please add it to your environment or .env file."
            )


def _client() -> OpenAI:
    cfg = OpenRouterConfig()
    # OpenRouter is OpenAI-compatible with its own base URL.
    return OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=cfg.api_key,
    )


def generate_themes_from_reviews(
    sample_reviews: Sequence[Dict[str, Any]]
) -> List[Dict[str, str]]:
    """
    Call OpenRouter to generate 3–5 themes from a sample of reviews.

    Returns a list of {id, label, description} dicts.
    """
    cfg = OpenRouterConfig()

    texts = [f"- ({r.get('rating', '?')}★) {r.get('text', '')}" for r in sample_reviews]
    joined = "\n".join(texts)

    system_prompt = (
        "You are a product/growth analyst for the GROWW investing app. "
        "You analyse app store reviews and summarise them into clear product themes."
    )
    user_prompt = (
        "Given the following GROWW app reviews, identify exactly 3 to 5 recurring themes.\n\n"
        "Reviews:\n"
        f"{joined}\n\n"
        "Return ONLY a JSON array of theme objects, no extra text. "
        'Each theme object must have: \"id\" (a machine-friendly slug), '
        '\"label\" (a short human-readable name), and '
        '"description" (a one-line description).\n'
        'Example: [{\"id\": \"app_performance\", \"label\": \"App performance\", '
        '\"description\": \"Speed, crashes, and general reliability\"}]'
    )

    client = _client()
    resp = with_network_retry(
        lambda: client.chat.completions.create(
            model=cfg.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
        )
    )
    content = resp.choices[0].message.content or "[]"
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        try:
            data = json.loads(content.strip().split("\n", 1)[-1])
        except Exception:
            data = []

    if not isinstance(data, list):
        data = []

    themes: List[Dict[str, str]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        tid = str(item.get("id", "")).strip()
        label = str(item.get("label", "")).strip()
        desc = str(item.get("description", "")).strip()
        if not (tid and label and desc):
            continue
        themes.append({"id": tid, "label": label, "description": desc})

    if len(themes) > 5:
        themes = themes[:5]

    return themes


def classify_reviews_into_themes(
    themes: Sequence[Dict[str, str]],
    batch: Sequence[Dict[str, Any]],
) -> List[Dict[str, str]]:
    """
    Call OpenRouter to classify a batch of reviews into the provided themes.

    Returns a list of {reviewId, theme_id} mappings.
    """
    cfg = OpenRouterConfig()

    themes_json = json.dumps(themes, ensure_ascii=False)
    reviews_json = json.dumps(
        [
            {
                "reviewId": r.get("reviewId", ""),
                "rating": r.get("rating", 0),
                "text": r.get("text", ""),
            }
            for r in batch
        ],
        ensure_ascii=False,
    )

    system_prompt = (
        "You are a precise classifier that assigns each app review to one product theme. "
        "You must always pick exactly one theme per review."
    )
    user_prompt = (
        f"Here are the themes as JSON:\n{themes_json}\n\n"
        f"Here is a JSON array of reviews to classify:\n{reviews_json}\n\n"
        "For each review, choose the single best-matching theme by its `id`.\n"
        "Return ONLY a JSON array of objects with this shape:\n"
        '[{\"reviewId\": \"string\", \"theme_id\": \"theme_slug\"}]\n'
        "Return no extra commentary or keys."
    )

    client = _client()
    resp = with_network_retry(
        lambda: client.chat.completions.create(
            model=cfg.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.0,
        )
    )
    content = resp.choices[0].message.content or "[]"
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        data = []

    if not isinstance(data, list):
        data = []

    result: List[Dict[str, str]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        rid = str(item.get("reviewId", "")).strip()
        theme_id = str(item.get("theme_id", "")).strip()
        if not (rid and theme_id):
            continue
        result.append({"reviewId": rid, "theme_id": theme_id})
    return result

