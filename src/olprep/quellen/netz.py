"""Common settings for all downloads."""

from pathlib import Path

USER_AGENT = "OL-Karten-prep/0.1 (Orienteering map preparation)"
CACHE_DIR = Path(__file__).resolve().parents[3] / "cache"     # project folder / cache
