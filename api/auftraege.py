"""Job management for the API, local variant: queue, status and result of each map job.

Jobs run one after another in a background thread (the data sources and the memory of
one machine are the limit, and waiting jobs show the status "wartend"). The status is
kept in memory. In the cloud, api/cloud.py does the same with Firestore, Cloud Run Jobs
and Cloud Storage (project.md, decision 18). Both offer anlegen(), holen(), download().
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


class Ausgelastet(RuntimeError):
    """Too many jobs at the same time; the user should try again later."""


def fehlertext(e: Exception) -> str:
    """Message for the user: our own RuntimeErrors are written for users (German, no
    internals); a failed download gets a general hint; anything else only its type."""
    import requests                                     # imported here: only needed on errors
    if isinstance(e, RuntimeError):
        return str(e)
    if isinstance(e, requests.RequestException):
        return "Ein Datendienst war nicht erreichbar. Bitte später noch einmal versuchen."
    return f"Interner Fehler ({type(e).__name__}). Bitte später noch einmal versuchen."


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
    zip: Path | str | None = None        # local file, or object name in Cloud Storage
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
            self._setzen(eintrag, status=FEHLER, fehler=fehlertext(e))
        else:
            self._setzen(eintrag, status=FERTIG, fortschritt=100, schritt="fertig", zip=ergebnis.zip)

    def download(self, eintrag: Eintrag) -> Path:
        """Local ZIP file of a finished job (the cloud variant returns a URL)."""
        return Path(eintrag.zip)

    def beenden(self) -> None:
        self._pool.shutdown(wait=False, cancel_futures=True)
