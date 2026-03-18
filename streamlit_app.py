from __future__ import annotations

import glob
import logging
import os
from datetime import datetime
from typing import Optional

import streamlit as st

from groww_pulse.config import ScrapeConfig
from groww_pulse.main import run_pipeline
from groww_pulse.env_vars import get_secret


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


def _latest_pulse_paths(data_cfg: ScrapeConfig) -> tuple[str, Optional[str]]:
    notes_dir = os.path.join(data_cfg.data_dir, "notes")
    pattern = os.path.join(notes_dir, "pulse-*.md")
    md_files = glob.glob(pattern)
    if not md_files:
        raise FileNotFoundError(f"No pulse-*.md found under {notes_dir}")
    latest_md = sorted(md_files)[-1]

    eml_dir = os.path.join(data_cfg.data_dir, "email")
    base = os.path.basename(latest_md).replace(".md", "")
    eml_path = os.path.join(eml_dir, f"{base}.eml")
    if os.path.exists(eml_path):
        return latest_md, eml_path
    return latest_md, None


def main() -> None:
    st.set_page_config(page_title="GROWW Weekly Pulse", layout="centered")
    st.title("GROWW Weekly Pulse")
    st.caption("Run the weekly pipeline and optionally send the email.")

    _setup_logging()
    data_cfg = ScrapeConfig()

    with st.sidebar:
        st.subheader("Config check")
        st.write("OPENROUTER_API_KEY present:", bool(get_secret("OPENROUTER_API_KEY", "")))
        st.write("OPENROUTER_MODEL:", get_secret("OPENROUTER_MODEL", "" ) or "(not set)")
        st.write("EMAIL_SENDER present:", bool(get_secret("EMAIL_SENDER", "")))
        st.write("EMAIL_PASSWORD present:", bool(get_secret("EMAIL_PASSWORD", "")))
        st.write("SMTP_HOST:", get_secret("SMTP_HOST", "") or "(not set)")
        st.write("SMTP_PORT:", get_secret("SMTP_PORT", "") or "(not set)")
        st.caption("Keys are not displayed—only whether they are present.")

    with st.form("run_form"):
        weeks = st.number_input("Weeks window (8–12)", min_value=8, max_value=12, value=10)
        max_reviews = st.number_input("Max reviews", min_value=50, max_value=1000, value=400)

        recipient = st.text_input("Recipient email", value="")
        recipient_name = st.text_input("Recipient name (optional)", value="")
        send_email = st.checkbox("Actually send email (SMTP). Otherwise writes .eml draft.", value=False)

        run_clicked = st.form_submit_button("Run pipeline")

    if not run_clicked:
        return

    if not recipient.strip():
        st.error("Recipient email is required.")
        return

    st.info(f"Starting pipeline at {datetime.utcnow().isoformat()}Z (UTC). This can take a few minutes.")

    try:
        with st.spinner("Running pipeline..."):
            run_pipeline(
                phase="all",
                weeks=int(weeks),
                max_reviews=int(max_reviews),
                report_date_str=None,
                recipient=recipient.strip(),
                recipient_name=recipient_name.strip() or None,
                send=bool(send_email),
            )

        latest_md, latest_eml = _latest_pulse_paths(data_cfg)
        st.success("Pipeline finished successfully.")
        st.markdown(f"Latest note: `{latest_md}`")
        if latest_eml:
            st.markdown(f"Latest email draft/sent: `{latest_eml}`")
        else:
            st.info("Email draft not found yet. If you did not enable 'send email', you should still get a .eml in `data/email/`.")
    except Exception as exc:
        logging.exception("Streamlit run failed")
        st.error(f"Pipeline failed: {exc}")


if __name__ == "__main__":
    main()

