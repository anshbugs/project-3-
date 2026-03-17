from __future__ import annotations

import json
from typing import Any, Dict, List, Sequence

import google.generativeai as genai

from .config import GeminiConfig


def _model() -> genai.GenerativeModel:
    cfg = GeminiConfig()
    cfg.ensure_present()
    genai.configure(api_key=cfg.api_key)
    return genai.GenerativeModel(cfg.model)


def _extract_text(resp: genai.types.GenerateContentResponse) -> str:
    # google-generativeai exposes .text on responses in recent versions.
    text = getattr(resp, "text", None)
    if text:
        return text
    # Fallback: concatenate parts.
    parts = []
    for cand in getattr(resp, "candidates", []) or []:
        for part in getattr(cand, "content", {}).parts or []:  # type: ignore[attr-defined]
            if getattr(part, "text", None):
                parts.append(part.text)
    return "\n".join(parts)


def generate_themes_from_reviews(
    sample_reviews: Sequence[Dict[str, Any]]
) -> List[Dict[str, str]]:
    """
    Use Gemini to generate 3–5 themes from a sample of reviews.
    Returns a list of {id, label, description} dicts.
    """
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
        "\"description\" (a one-line description).\n"
        "Example: "
        '[{\"id\": \"app_performance\", \"label\": \"App performance\", '
        '\"description\": \"Speed, crashes, and general reliability\"}]'
    )

    model = _model()
    resp = model.generate_content([system_prompt, user_prompt])
    content = _extract_text(resp) or "[]"

    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        # Sometimes models wrap JSON in markdown; try to salvage.
        try:
            start = content.find("[")
            end = content.rfind("]")
            if start != -1 and end != -1:
                data = json.loads(content[start : end + 1])
            else:
                data = []
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
    Use Gemini to classify a batch of reviews into the provided themes.
    Returns a list of {reviewId, theme_id} mappings.
    """
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

    model = _model()
    resp = model.generate_content([system_prompt, user_prompt])
    content = _extract_text(resp) or "[]"

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


def generate_pulse_markdown(
    grouped: Dict[str, Any],
    top_themes: Sequence[Dict[str, Any]],
    quotes: Sequence[Dict[str, Any]],
    week_of: str,
) -> str:
    """
    Use Gemini to generate the weekly pulse markdown note.
    """
    themes_for_prompt = [
        {
            "id": t["id"],
            "label": t["label"],
            "description": t["description"],
            "count": t.get("count", 0),
            "avg_rating": round(t.get("avg_rating", 0.0), 2),
        }
        for t in top_themes
    ]

    quotes_for_prompt = [
        {
            "reviewId": q.get("reviewId"),
            "rating": int(q.get("rating", 0)),
            "text": q.get("text", ""),
        }
        for q in quotes
    ]

    system_prompt = (
        "You are a product communications writer at GROWW. "
        "You write concise, scannable weekly updates for product, growth, support, and leadership."
    )

    user_prompt = (
        f"Using the themed review data below, write a concise Weekly Review Pulse note for GROWW.\n\n"
        f"Week of: {week_of}\n\n"
        f"Top themes (JSON):\n{json.dumps(themes_for_prompt, ensure_ascii=False, indent=2)}\n\n"
        f"Candidate quotes (JSON):\n{json.dumps(quotes_for_prompt, ensure_ascii=False, indent=2)}\n\n"
        "Requirements:\n"
        "- Structure the note in Markdown exactly as:\n"
        "  ## GROWW Weekly Review Pulse — Week of {date}\n"
        "  \n"
        "  ### Top Themes\n"
        "  1. ...\n"
        "  2. ...\n"
        "  3. ...\n"
        "  \n"
        "  ### Real User Quotes\n"
        "  - \"quote\" — {rating}★\n"
        "  - ... (total 3 quotes)\n"
        "  \n"
        "  ### Action Ideas\n"
        "  1. ...\n"
        "  2. ...\n"
        "  3. ...\n"
        "- Use exactly the 3 themes provided as Top Themes (no more than 3).\n"
        "- Use exactly 3 quotes, chosen from the provided candidate quotes only. Do not invent or modify quotes.\n"
        "- Each quote line must include the star rating.\n"
        "- Propose exactly 3 concrete, theme-linked action ideas.\n"
        "- Total length must be under 250 words.\n"
        "- Do not include any personally identifying information (names, emails, phone numbers). "
        "If a quote seems to contain a name, replace it with [User].\n"
        "- Keep language plain, concise, and scannable.\n"
        "Return ONLY the markdown for the note, no extra commentary.\n"
    )

    model = _model()
    resp = model.generate_content([system_prompt, user_prompt])
    text = _extract_text(resp) or ""
    return text.strip()

