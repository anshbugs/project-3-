"""
Core package for the GROWW weekly pulse pipeline.

Phase 1 (this implementation) handles:
- Scraping Play Store reviews for the GROWW app.
- PII-safe cleaning and length filtering.
- Writing normalized reviews JSON for downstream phases.
"""

__all__ = ["config", "pii", "phase1"]

