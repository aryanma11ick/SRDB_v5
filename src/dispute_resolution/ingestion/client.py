"""
Backward-compatible wrapper that re-exports the Gmail client helpers.

Prefer importing from ``src.dispute_resolution.ingestion.gmail_client`` directly.
"""

from .gmail_client import fetch_and_print_one_email, get_gmail_service

__all__ = ["fetch_and_print_one_email", "get_gmail_service"]
