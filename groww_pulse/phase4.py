from __future__ import annotations

import argparse
import logging
import os
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from glob import glob
from typing import Optional

import markdown

from .config import EmailConfig, ScrapeConfig


logger = logging.getLogger(__name__)


def _latest_pulse_md(cfg: ScrapeConfig) -> str:
    notes_dir = os.path.join(cfg.data_dir, "notes")
    pattern = os.path.join(notes_dir, "pulse-*.md")
    files = glob(pattern)
    if not files:
        raise FileNotFoundError(f"No pulse-*.md files found in {notes_dir}")
    return sorted(files)[-1]


def _build_email(
    cfg: EmailConfig,
    markdown_path: str,
    report_date_str: Optional[str],
    recipient: Optional[str],
    recipient_name: Optional[str],
) -> EmailMessage:
    with open(markdown_path, "r", encoding="utf-8") as f:
        md_body = f.read()

    # Derive date from filename if not provided.
    filename = os.path.basename(markdown_path)
    if report_date_str:
        week_of = report_date_str
    else:
        # pulse-YYYY-MM-DD.md
        parts = filename.replace("pulse-", "").split(".", 1)[0]
        week_of = parts

    subject = f"GROWW Weekly Review Pulse -- Week of {week_of}"
    # Recipient is expected to come from the caller (e.g. frontend), with an
    # optional default from EMAIL_RECIPIENT in config. We no longer fall back
    # to the sender address implicitly.
    to_addr = recipient or cfg.default_recipient
    if not to_addr:
        raise RuntimeError(
            "No recipient email provided. Pass a recipient from the frontend/CLI "
            "or set EMAIL_RECIPIENT in the environment."
        )

    # Plain text: optionally prepend greeting.
    greeting = ""
    if recipient_name:
        greeting = f"Hi {recipient_name},\n\n"
    text_body = greeting + md_body

    # HTML: convert Markdown to HTML and add greeting.
    html_content = markdown.markdown(md_body)
    if recipient_name:
        html_greeting = f"<p>Hi {recipient_name},</p>\n"
    else:
        html_greeting = ""
    html_body = f"<!doctype html><html><body>{html_greeting}{html_content}</body></html>"

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = cfg.sender or to_addr
    msg["To"] = to_addr

    msg.set_content(text_body)
    msg.add_alternative(html_body, subtype="html")

    return msg


def _send_email(cfg: EmailConfig, msg: EmailMessage) -> None:
    if not (cfg.sender and cfg.password):
        raise RuntimeError(
            "EMAIL_SENDER or EMAIL_PASSWORD not set; cannot send. Use dry-run without --send."
        )

    with smtplib.SMTP(cfg.smtp_host, cfg.smtp_port) as server:
        server.starttls()
        server.login(cfg.sender, cfg.password)
        server.send_message(msg)


@dataclass
class Phase4Result:
    eml_path: str
    sent: bool


def run_phase4(
    report_date_str: Optional[str] = None,
    recipient: Optional[str] = None,
    recipient_name: Optional[str] = None,
    send: bool = False,
) -> Phase4Result:
    """
    Phase 4: Email delivery / draft.

    - Loads latest pulse-*.md (output of Phase 3).
    - Builds an email with plain text + HTML parts.
    - In dry-run mode (default), writes .eml file under data/email/.
    - If --send is passed and SMTP credentials exist, sends via SMTP.
    """
    scfg = ScrapeConfig()
    ecfg = EmailConfig()

    notes_md = _latest_pulse_md(scfg)
    msg = _build_email(ecfg, notes_md, report_date_str, recipient, recipient_name)

    email_dir = os.path.join(scfg.data_dir, "email")
    os.makedirs(email_dir, exist_ok=True)

    # Use week-of date part for filename.
    basename = os.path.basename(notes_md).replace(".md", "")
    eml_path = os.path.join(email_dir, f"{basename}.eml")
    with open(eml_path, "wb") as f:
        f.write(bytes(msg))

    logger.info("Phase 4: wrote email draft to %s", eml_path)

    did_send = False
    if send:
        _send_email(ecfg, msg)
        did_send = True
        logger.info("Phase 4: sent email to %s", msg["To"])

    return Phase4Result(eml_path=eml_path, sent=did_send)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Phase 4: email draft generation and optional send."
    )
    parser.add_argument(
        "--date",
        type=str,
        default=None,
        help="Optional report date YYYY-MM-DD (defaults from latest pulse filename).",
    )
    parser.add_argument(
        "--recipient",
        type=str,
        default=None,
        help="Recipient email address (overrides EMAIL_RECIPIENT).",
    )
    parser.add_argument(
        "--recipient-name",
        type=str,
        default=None,
        help='Recipient name for greeting ("Hi {name},").',
    )
    parser.add_argument(
        "--send",
        action="store_true",
        help="If set, actually send the email via SMTP instead of just writing .eml.",
    )
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    args = _parse_args()
    run_phase4(
        report_date_str=args.date,
        recipient=args.recipient,
        recipient_name=args.recipient_name,
        send=args.send,
    )


if __name__ == "__main__":
    main()

