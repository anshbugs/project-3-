from __future__ import annotations

import glob
import logging
import os
from datetime import datetime
from typing import Optional

import streamlit as st

from groww_pulse.config import ScrapeConfig
from groww_pulse.main import run_pipeline


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
    _setup_logging()
    data_cfg = ScrapeConfig()

    st.set_page_config(page_title="GROWW Weekly Pulse", layout="centered")

    st.markdown(
        """
        <style>
          body { background: radial-gradient(circle at top, #0f172a, #020617 55%, #000 100%); color: #e5e7eb; }
          .glass {
            background: radial-gradient(circle at top left, #0f172a 0, #020617 45%, #000 100%);
            border: 1px solid rgba(148, 163, 184, 0.25);
            box-shadow: 0 0 0 1px rgba(15, 23, 42, 0.6), 0 18px 60px rgba(0,0,0,0.9);
            border-radius: 24px;
            padding: 22px 22px 26px;
          }
          .hero { display:flex; align-items:center; gap:12px; margin-bottom: 14px; }
          .logo-mark {
            width: 44px; height: 44px; border-radius: 18px;
            background: conic-gradient(from 160deg, #22c55e, #22c55e, #0ea5e9, #22c55e);
            display:flex; align-items:center; justify-content:center;
            box-shadow: 0 0 0 1px rgba(15, 23, 42, 0.9), 0 10px 30px rgba(34, 197, 94, 0.5);
          }
          .logo-g { font-weight: 900; color: #020617; letter-spacing: 0.03em; }
          .logo-name { font-size: 18px; font-weight: 800; letter-spacing: 0.18em; display:block; line-height: 1.2; }
          .logo-tagline { font-size: 12px; color: #9ca3af; display:block; margin-top: 4px; }
          .sub { font-size: 13px; color: #9ca3af; margin-bottom: 18px; }
          .stButton>button { border-radius: 999px; padding: 10px 18px; font-weight: 700; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="glass">', unsafe_allow_html=True)
    st.markdown(
        """
        <div class="hero">
          <div class="logo-mark"><span class="logo-g">G</span></div>
          <div>
            <span class="logo-name">GROWW</span>
            <span class="logo-tagline">Weekly Review Pulse</span>
          </div>
        </div>
        <div class="sub">
          Turn the latest Play Store reviews into a sharp, weekly email pulse for product, support, and leadership.
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.form("run_form"):
        weeks = st.number_input("Review window (weeks)", min_value=8, max_value=12, value=10, step=1)
        run_mode = st.selectbox("Run mode", options=["Quick (100 reviews)", "Full (400 reviews)"], index=0)
        max_reviews = 100 if run_mode.startswith("Quick") else 400

        recipient = st.text_input("Recipient email", value="Anshbhalla421@gmail.com")
        recipient_name = st.text_input("Recipient name (optional)", value="Ansh")
        send_email = st.checkbox(
            "Actually send email (SMTP). Otherwise writes .eml draft.",
            value=True,
        )

        run_clicked = st.form_submit_button("Run Weekly Pulse")

    if run_clicked:
        if not recipient.strip():
            st.error("Recipient email is required.")
            st.stop()

        st.info(
            f"Starting pipeline (UTC) at {datetime.utcnow().isoformat()}Z. "
            f"Mode: {run_mode}."
        )

        # Run phase-by-phase so Streamlit can update the user.
        progress = st.progress(0)

        try:
            with st.spinner("Phase 1/4: Scraping & normalization…"):
                run_pipeline(
                    phase="scrape",
                    weeks=int(weeks),
                    max_reviews=int(max_reviews),
                    report_date_str=None,
                    recipient=recipient.strip(),
                    recipient_name=recipient_name.strip() or None,
                    send=bool(send_email),
                )
            progress.progress(25)
            st.success("Phase 1 complete.")

            with st.spinner("Phase 2/4: Themes & classification…"):
                run_pipeline(
                    phase="classify",
                    weeks=int(weeks),
                    max_reviews=int(max_reviews),
                    report_date_str=None,
                    recipient=recipient.strip(),
                    recipient_name=recipient_name.strip() or None,
                    send=bool(send_email),
                )
            progress.progress(55)
            st.success("Phase 2 complete.")

            with st.spinner("Phase 3/4: Weekly pulse note…"):
                run_pipeline(
                    phase="report",
                    weeks=int(weeks),
                    max_reviews=int(max_reviews),
                    report_date_str=None,
                    recipient=recipient.strip(),
                    recipient_name=recipient_name.strip() or None,
                    send=bool(send_email),
                )
            progress.progress(80)
            st.success("Phase 3 complete.")

            with st.spinner("Phase 4/4: Email draft / send…"):
                run_pipeline(
                    phase="email",
                    weeks=int(weeks),
                    max_reviews=int(max_reviews),
                    report_date_str=None,
                    recipient=recipient.strip(),
                    recipient_name=recipient_name.strip() or None,
                    send=bool(send_email),
                )
            progress.progress(100)

            latest_md, latest_eml = _latest_pulse_paths(data_cfg)
            st.success("Pipeline finished successfully.")

            # Provide downloads without leaking secrets.
            st.markdown("### Output")
            st.caption("Generated artifacts are stored on the server container.")

            with open(latest_md, "r", encoding="utf-8") as f:
                md_text = f.read()
            st.download_button(
                label="Download latest pulse note (Markdown)",
                data=md_text,
                file_name=os.path.basename(latest_md),
                mime="text/markdown",
            )

            if latest_eml:
                with open(latest_eml, "rb") as f:
                    eml_bytes = f.read()
                st.download_button(
                    label="Download latest email (.eml)",
                    data=eml_bytes,
                    file_name=os.path.basename(latest_eml),
                    mime="message/rfc822",
                )
            else:
                st.info("Email draft not found yet. If you disabled sending, you should still get a .eml under `data/email/`.")

        except Exception as exc:
            logging.exception("Streamlit run failed")
            st.error(f"Pipeline failed: {exc}")

    st.markdown("</div>", unsafe_allow_html=True)


if __name__ == "__main__":
    main()

