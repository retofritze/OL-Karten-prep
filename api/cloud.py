"""Job management in the cloud: Firestore (status), Cloud Run Jobs (work), Cloud Storage (ZIPs).

Why not a background thread as locally: Cloud Run throttles the CPU of a service as soon as
no request is open, and Firebase Hosting cuts requests after 60 s. So the API service only
records the job in Firestore and starts one execution of a Cloud Run Job with AUFTRAG_ID;
the job (api/job.py) builds the map, reports progress to Firestore and stores the ZIP in
Cloud Storage. The download is a time-limited signed URL of the ZIP (Cloud Run responses
are limited to 32 MiB, Hosting to 60 s).

The Google services are wrapped in three small classes (Speicher, Starter, Ablage) so that
the logic can be tested with fakes (tests/test_cloud.py). Google libraries are imported
inside them only, so local use and tests do not need them.
"""

from __future__ import annotations

import logging
import os
import tempfile
import uuid
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Protocol

from olprep.auftrag import Auftrag, Ergebnis, Melde, ausfuehren

from .auftraege import FEHLER, FERTIG, LAEUFT, WARTEND, Ausgelastet, Eintrag, fehlertext

log = logging.getLogger(__name__)

MAX_GLEICHZEITIG = 3                    # jobs waiting or running at the same time
VERGESSEN_NACH = timedelta(hours=1)     # older unfinished jobs no longer count (e.g. crashed)
LINK_GUELTIG = timedelta(hours=1)       # validity of the signed download URL


# --- the three Google services, behind small interfaces ----------------------------

class Speicher(Protocol):
    def anlegen(self, auftrag_id: str, daten: dict) -> None: ...
    def lesen(self, auftrag_id: str) -> dict | None: ...
    def aendern(self, auftrag_id: str, werte: dict) -> None: ...
    def aktive(self) -> list[dict]: ...          # jobs with status wartend or laeuft


class Starter(Protocol):
    def starten(self, auftrag_id: str) -> None: ...


class Ablage(Protocol):
    def hochladen(self, datei: Path, name: str) -> None: ...
    def link(self, name: str, dateiname: str) -> str: ...


class FirestoreSpeicher:
    def __init__(self, sammlung: str = "auftraege"):
        from google.cloud import firestore
        self._col = firestore.Client().collection(sammlung)

    def anlegen(self, auftrag_id, daten):
        self._col.document(auftrag_id).set(daten)

    def lesen(self, auftrag_id):
        doc = self._col.document(auftrag_id).get()
        return doc.to_dict() if doc.exists else None

    def aendern(self, auftrag_id, werte):
        self._col.document(auftrag_id).update(werte)

    def aktive(self):
        # single-field "in" query: needs no composite index
        return [d.to_dict() for d in self._col.where("status", "in", [WARTEND, LAEUFT]).stream()]


class CloudRunStarter:
    """Starts one execution of the Cloud Run Job with the environment variable AUFTRAG_ID."""

    def __init__(self, projekt: str, region: str, job: str):
        from google.cloud import run_v2
        self._run_v2 = run_v2
        self._client = run_v2.JobsClient()
        self._name = f"projects/{projekt}/locations/{region}/jobs/{job}"

    def starten(self, auftrag_id):
        run_v2 = self._run_v2
        # The job has one unnamed container: an override without a name applies to it (as with
        # "gcloud run jobs execute --update-env-vars"). Reading the job to look up a name would
        # need the extra permission run.jobs.get, which roles/run.jobsExecutorWithOverrides lacks.
        override = run_v2.RunJobRequest.Overrides.ContainerOverride(
            env=[run_v2.EnvVar(name="AUFTRAG_ID", value=auftrag_id)])
        # returns a long-running operation at once; the job runs on without us
        self._client.run_job(request=run_v2.RunJobRequest(
            name=self._name, overrides=run_v2.RunJobRequest.Overrides(container_overrides=[override])))


class StorageAblage:
    def __init__(self, bucket: str):
        import google.auth
        from google.cloud import storage
        self._google_auth = google.auth
        self._bucket = storage.Client().bucket(bucket)

    def hochladen(self, datei, name):
        self._bucket.blob(name).upload_from_filename(str(datei), content_type="application/zip")

    def link(self, name, dateiname):
        # On Cloud Run there is no key file: sign through the IAM API with the service
        # account itself (needs roles/iam.serviceAccountTokenCreator on itself).
        from google.auth.transport.requests import Request
        credentials, _ = self._google_auth.default()
        credentials.refresh(Request())
        return self._bucket.blob(name).generate_signed_url(
            version="v4", expiration=LINK_GUELTIG, method="GET",
            service_account_email=credentials.service_account_email, access_token=credentials.token,
            response_disposition=f'attachment; filename="{dateiname}"')


# --- job management for the API service --------------------------------------------

def _jetzt() -> datetime:
    return datetime.now(timezone.utc)


def _eintrag(auftrag_id: str, d: dict) -> Eintrag:
    a = dict(d["auftrag"])
    a["bbox"] = tuple(a["bbox"])
    return Eintrag(auftrag_id, Auftrag(**a), d["status"], d["fortschritt"], d["schritt"],
                   d.get("fehler"), d.get("zip"), d["erstellt"])


class CloudAuftragsverwaltung:
    def __init__(self, speicher: Speicher, starter: Starter, ablage: Ablage,
                 max_gleichzeitig: int = MAX_GLEICHZEITIG):
        self._speicher, self._starter, self._ablage = speicher, starter, ablage
        self._max = max_gleichzeitig

    @classmethod
    def aus_umgebung(cls) -> CloudAuftragsverwaltung:
        """Configured by environment variables of the Cloud Run service (see Dockerfile/deploy)."""
        projekt, region = os.environ["OLPREP_PROJEKT"], os.environ["OLPREP_REGION"]
        return cls(FirestoreSpeicher(), CloudRunStarter(projekt, region, os.environ["OLPREP_JOB"]),
                   StorageAblage(os.environ["OLPREP_BUCKET"]))

    def anlegen(self, auftrag: Auftrag) -> Eintrag:
        """Check, record and start a job. Raises Eingabefehler or Ausgelastet."""
        a = auftrag.geprueft()
        grenze = _jetzt() - VERGESSEN_NACH
        if sum(1 for d in self._speicher.aktive() if d["erstellt"] > grenze) >= self._max:
            raise Ausgelastet(f"Gerade werden schon {self._max} Karten erstellt. "
                              "Bitte in ein paar Minuten noch einmal versuchen.")
        auftrag_id = uuid.uuid4().hex[:12]
        daten = {"auftrag": asdict(a) | {"bbox": list(a.bbox)}, "status": WARTEND, "fortschritt": 0,
                 "schritt": "wartet auf Start", "fehler": None, "zip": None, "erstellt": _jetzt()}
        self._speicher.anlegen(auftrag_id, daten)
        try:
            self._starter.starten(auftrag_id)
        except Exception:
            log.exception("Job für Auftrag %s nicht gestartet", auftrag_id)
            daten |= {"status": FEHLER, "fehler": "Der Auftrag konnte nicht gestartet werden. "
                                                  "Bitte später noch einmal versuchen."}
            self._speicher.aendern(auftrag_id, {k: daten[k] for k in ("status", "fehler")})
        return _eintrag(auftrag_id, daten)

    def holen(self, auftrag_id: str) -> Eintrag | None:
        d = self._speicher.lesen(auftrag_id)
        return _eintrag(auftrag_id, d) if d else None

    def download(self, eintrag: Eintrag) -> str:
        """Signed URL of the ZIP in Cloud Storage, valid for LINK_GUELTIG."""
        return self._ablage.link(eintrag.zip, f"{eintrag.auftrag.name}.zip")


# --- the work, inside the Cloud Run Job ----------------------------------------------

def auftrag_bearbeiten(auftrag_id: str, speicher: Speicher, ablage: Ablage,
                       runner: Callable[[Auftrag, Path, Melde], Ergebnis] | None = None) -> bool:
    """Build the map of one job, report progress, upload the ZIP. Returns False on failure."""
    runner = runner or (lambda a, ziel, melde: ausfuehren(a, ziel, melde=melde))
    d = speicher.lesen(auftrag_id)
    if d is None:
        log.error("Auftrag %s nicht gefunden", auftrag_id)
        return False
    eintrag = _eintrag(auftrag_id, d)
    speicher.aendern(auftrag_id, {"status": LAEUFT, "schritt": "startet"})

    def melde(schritt: str, prozent: int) -> None:
        speicher.aendern(auftrag_id, {"schritt": schritt, "fortschritt": prozent})

    try:
        with tempfile.TemporaryDirectory(prefix="auftrag-") as tmp:      # /tmp is memory on Cloud Run
            ergebnis = runner(eintrag.auftrag, Path(tmp), melde)
            name = f"{auftrag_id}/{eintrag.auftrag.name}.zip"
            ablage.hochladen(ergebnis.zip, name)
    except Exception as e:
        log.exception("Auftrag %s fehlgeschlagen", auftrag_id)
        speicher.aendern(auftrag_id, {"status": FEHLER, "fehler": fehlertext(e)})
        return False
    speicher.aendern(auftrag_id, {"status": FERTIG, "fortschritt": 100, "schritt": "fertig", "zip": name})
    return True
