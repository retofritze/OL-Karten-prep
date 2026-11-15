"""Entry point of the Cloud Run Job: build the map of the job in AUFTRAG_ID.

    python -m api.job        (environment: AUFTRAG_ID, OLPREP_BUCKET)

Exit code 1 marks a failed execution in Cloud Run; the job itself sets the status in
Firestore either way. The job is deployed with max retries 0: a retry would only repeat
the same failure and cost time.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from .cloud import FirestoreSpeicher, StorageAblage, auftrag_bearbeiten  # noqa: E402


def main() -> int:
    logging.basicConfig(level=logging.INFO)
    ok = auftrag_bearbeiten(os.environ["AUFTRAG_ID"], FirestoreSpeicher(),
                            StorageAblage(os.environ["OLPREP_BUCKET"]))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
