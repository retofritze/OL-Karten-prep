"""Job management for the API: queue, status and result of each map job.

Jobs run one after another in a background thread (the data sources and the memory of
one machine are the limit, and waiting jobs show the status "wartend"). The status is
kept in memory; with Firebase it moves to Firestore and the ZIPs to Cloud Storage
(project.md, decision 18).
"""

from __future__ import annotations

import logging
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from olprep.auftrag import Auftrag, Ergebnis, Melde, ausfuehren

log = logging.getLogger(__name__)

WARTEND, LAEUFT, FERTIG, FEHLER = "wartend", "laeuft", "fertig", "fehler"

Runner = Callable[[Auftrag, Path, Melde], Ergebnis]


def _run_job(auftrag: Auftrag, ziel: Path, melde: Melde) -> Ergebnis:
    return ausfuehren(auftrag, ziel, melde=melde)


@dataclass
class Eintrag:
    id: str
    auftrag: Auftrag                    # already checked
    status: str = WARTEND
    fortschritt: int = 0
    schritt: str = "wartet auf Start"
    fehler: str | None = None
    zip: Path | None = None
    erstellt: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class Auftragsverwaltung:
    def __init__(self, arbeitsordner: Path, runner: Runner = _run_job, parallel: int = 1):
        self.arbeitsordner = arbeitsordner
        self._runner = runner
        self._pool = ThreadPoolExecutor(parallel, thread_name_prefix="auftrag")
        self._lock = threading.Lock()
        self._eintraege: dict[str, Eintrag] = {}

    def anlegen(self, auftrag: Auftrag) -> Eintrag:
        """Queue a checked job. Raises Eingabefehler for unusable settings."""
        eintrag = Eintrag(uuid.uuid4().hex[:12], auftrag.geprueft())
        with self._lock:
            self._eintraege[eintrag.id] = eintrag
        self._pool.submit(self._ausfuehren, eintrag)
        return eintrag

    def holen(self, auftrag_id: str) -> Eintrag | None:
        with self._lock:
            return self._eintraege.get(auftrag_id)

    def _setzen(self, eintrag: Eintrag, **werte) -> None:
        with self._lock:
            for key, value in werte.items():
                setattr(eintrag, key, value)

    def _ausfuehren(self, eintrag: Eintrag) -> None:
        self._setzen(eintrag, status=LAEUFT, schritt="startet")

        def melde(schritt: str, prozent: int) -> None:
            self._setzen(eintrag, schritt=schritt, fortschritt=prozent)

        try:
            ergebnis = self._runner(eintrag.auftrag, self.arbeitsordner / eintrag.id, melde)
        except Exception as e:      # any failure ends this job, not the server
            log.exception("Auftrag %s fehlgeschlagen", eintrag.id)
            self._setzen(eintrag, status=FEHLER, fehler=f"{type(e).__name__}: {e}")
        else:
            self._setzen(eintrag, status=FERTIG, fortschritt=100, schritt="fertig", zip=ergebnis.zip)

    def beenden(self) -> None:
        self._pool.shutdown(wait=False, cancel_futures=True)
