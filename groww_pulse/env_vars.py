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

    # Optional Streamlit Cloud integration.
    # Streamlit's `st.secrets` behaves like a mapping but may not support `key in st.secrets`,
    # depending on version/runtime. Use indexing + KeyError to be safe.
    try:
        import streamlit as st  # type: ignore

        if hasattr(st, "secrets"):
            try:
                sval: Any = st.secrets[key]  # type: ignore[index]
                if sval is None:
                    return default
                return str(sval)
            except KeyError:
                return default
    except Exception:
        # If Streamlit isn't available (e.g. local CLI runs), ignore and fall back.
        pass

    return default

