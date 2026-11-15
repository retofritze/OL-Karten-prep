"""Common settings for all downloads."""

import os
from pathlib import Path

# Overpass, OSM and the other services ask for an identifying User-Agent with a contact
USER_AGENT = "OL-Karten-prep/0.1 (+https://github.com/retofritze/OL-Karten-prep)"

# Downloaded tiles; in the cloud a folder under /tmp (OLPREP_CACHE), locally project folder / cache
CACHE_DIR = Path(os.environ.get("OLPREP_CACHE", Path(__file__).resolve().parents[3] / "cache"))
