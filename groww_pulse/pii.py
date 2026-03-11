from __future__ import annotations

import re
from typing import Optional


_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
_URL_RE = re.compile(r"https?://\S+")
_PHONE_RE = re.compile(r"\b(?:\+?\d[\d\-\s]{7,}\d)\b")
_ID_RE = re.compile(r"\b\d{10,}\b")
_HANDLE_RE = re.compile(r"@\w+")


def sanitize_review_text(text: str) -> Optional[str]:
    """
    Basic PII scrubber for review text.

    - Trims whitespace.
    - Masks obvious emails, phones, URLs, numeric IDs, and @handles.
    - Normalises internal whitespace.

    Returns:
        Sanitised text, or None if it becomes empty.
    """
    if not text:
        return None

    cleaned = text.strip()
    if not cleaned:
        return None

    cleaned = _EMAIL_RE.sub("[EMAIL]", cleaned)
    cleaned = _URL_RE.sub("[URL]", cleaned)
    cleaned = _PHONE_RE.sub("[PHONE]", cleaned)
    cleaned = _ID_RE.sub("[ID]", cleaned)
    cleaned = _HANDLE_RE.sub("[USER]", cleaned)

    # Collapse excessive whitespace
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not cleaned:
        return None

    return cleaned

