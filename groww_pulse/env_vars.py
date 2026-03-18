from __future__ import annotations

import os
from typing import Any


def get_secret(key: str, default: str = "") -> str:
    """
    Read a secret from environment variables.

    If missing from env vars, also check Streamlit's `st.secrets` (Streamlit Cloud).
    Our pipeline code uses `os.getenv`, so this bridges both worlds.
    """
    val = os.getenv(key)
    if val is not None and str(val).strip() != "":
        return str(val)

    # Optional Streamlit Cloud integration
    try:
        import streamlit as st  # type: ignore

        if hasattr(st, "secrets") and key in st.secrets:  # pragma: no cover
            sval: Any = st.secrets[key]
            if sval is None:
                return default
            return str(sval)
    except Exception:
        pass

    return default

