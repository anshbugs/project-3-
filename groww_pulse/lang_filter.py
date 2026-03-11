from __future__ import annotations

from langdetect import DetectorFactory, detect


# Make language detection deterministic.
DetectorFactory.seed = 0


def is_english(text: str) -> bool:
    """
    Return True if the given text is likely English.

    For very short or noisy texts, detection can be unreliable, but in this
    pipeline we already require >=100 characters, which improves accuracy.
    """
    if not text or len(text) < 20:
        # Too short to reliably detect; treat as non-English here.
        return False
    try:
        lang = detect(text)
    except Exception:
        return False
    return lang == "en"

