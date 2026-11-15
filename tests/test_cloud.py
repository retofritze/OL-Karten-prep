"""Cloud job management (api/cloud.py) with fakes for Firestore, Cloud Run Jobs and Cloud Storage.

The real Google services are only exercised after deployment (smoke test, project.md)."""

import zipfile
from datetime import timedelta
from pathlib import Path

import pytest
import requests
from fastapi.testclient import TestClient

from api import cloud
from api.auftraege import Ausgelastet, fehlertext
from api.main import PREFIX, create_app
from olprep.auftrag import Auftrag, Eingabefehler, Ergebnis
from olprep.quellen.osm import OsmNichtErreichbar

STADION = Auftrag("stadion", (16.415, 48.203, 16.427, 48.211), 4000)


class FakeSpeicher:
    def __init__(self):
        self.docs = {}

    def anlegen(self, auftrag_id, daten):
        self.docs[auftrag_id] = dict(daten)

    def lesen(self, auftrag_id):
        return dict(self.docs[auftrag_id]) if auftrag_id in self.docs else None

    def aendern(self, auftrag_id, werte):
        self.docs[auftrag_id].update(werte)

    def aktive(self):
        return [d for d in self.docs.values() if d["status"] in ("wartend", "laeuft")]


class FakeStarter:
    def __init__(self, fail=False):
        self.started, self.fail = [], fail

    def starten(self, auftrag_id):
        if self.fail:
            raise RuntimeError("permission denied")
        self.started.append(auftrag_id)


class FakeAblage:
    def __init__(self):
        self.uploaded = {}

    def hochladen(self, datei, name):
        self.uploaded[name] = Path(datei).read_bytes()

    def link(self, name, dateiname):
        return f"https://storage.example/{name}?signed&filename={dateiname}"


@pytest.fixture
def parts():
    return FakeSpeicher(), FakeStarter(), FakeAblage()


def test_create_records_and_starts_job(parts):
    speicher, starter, ablage = parts
    e = cloud.CloudAuftragsverwaltung(speicher, starter, ablage).anlegen(STADION)
    assert starter.started == [e.id]
    doc = speicher.docs[e.id]
    assert doc["status"] == "wartend" and doc["auftrag"]["bbox"] == [16.415, 48.203, 16.427, 48.211]
    assert doc["auftrag"]["symbolsatz"] == "ISSprOM 2019"          # checked, defaults filled in
    assert cloud.CloudAuftragsverwaltung(speicher, starter, ablage).holen(e.id).auftrag == STADION.geprueft()


def test_invalid_job_is_not_recorded(parts):
    speicher, starter, ablage = parts
    with pytest.raises(Eingabefehler):
        cloud.CloudAuftragsverwaltung(speicher, starter, ablage).anlegen(
            Auftrag("x", STADION.bbox, 10000, symbolsatz="ISSprOM 2019"))
    assert speicher.docs == {} and starter.started == []


def test_limit_of_simultaneous_jobs(parts):
    speicher, starter, ablage = parts
    manager = cloud.CloudAuftragsverwaltung(speicher, starter, ablage, max_gleichzeitig=2)
    first = manager.anlegen(STADION)
    manager.anlegen(STADION)
    with pytest.raises(Ausgelastet, match="schon 2 Karten"):
        manager.anlegen(STADION)
    speicher.docs[first.id]["status"] = "fertig"                    # one finished: room again
    manager.anlegen(STADION)
    # stale jobs (e.g. a crashed container) stop counting after VERGESSEN_NACH
    for d in speicher.docs.values():
        d["erstellt"] -= cloud.VERGESSEN_NACH + timedelta(minutes=1)
    manager.anlegen(STADION)


def test_job_start_failure_is_reported(parts):
    speicher, _, ablage = parts
    e = cloud.CloudAuftragsverwaltung(speicher, FakeStarter(fail=True), ablage).anlegen(STADION)
    assert e.status == "fehler" and "nicht gestartet" in e.fehler
    assert speicher.docs[e.id]["status"] == "fehler"


def fake_runner(auftrag, ziel, melde):
    melde("Orthofoto laden", 5)
    folder = ziel / auftrag.name
    folder.mkdir(parents=True)
    (folder / f"{auftrag.name}.omap").write_text("<map/>", encoding="utf-8")
    zip_path = ziel / f"{auftrag.name}.zip"
    with zipfile.ZipFile(zip_path, "w") as z:
        z.write(folder / f"{auftrag.name}.omap", f"{auftrag.name}/{auftrag.name}.omap")
    melde("fertig", 100)
    return Ergebnis(folder, folder / f"{auftrag.name}.omap", zip_path, 0)


def test_job_builds_uploads_and_finishes(parts):
    speicher, starter, ablage = parts
    e = cloud.CloudAuftragsverwaltung(speicher, starter, ablage).anlegen(STADION)
    seen = []
    original = speicher.aendern
    speicher.aendern = lambda i, w: (seen.append(dict(w)), original(i, w))
    assert cloud.auftrag_bearbeiten(e.id, speicher, ablage, runner=fake_runner) is True
    doc = speicher.docs[e.id]
    assert (doc["status"], doc["fortschritt"], doc["zip"]) == ("fertig", 100, f"{e.id}/stadion.zip")
    assert ablage.uploaded[f"{e.id}/stadion.zip"][:2] == b"PK"
    assert {"schritt": "Orthofoto laden", "fortschritt": 5} in seen
    assert seen[0] == {"status": "laeuft", "schritt": "startet"}


@pytest.mark.parametrize("error, message", [
    (OsmNichtErreichbar("OpenStreetMap (Overpass) ist gerade nicht erreichbar."), "Overpass) ist gerade"),
    (RuntimeError("Keine Orthofoto-Quelle deckt den Bereich ab."), "Keine Orthofoto-Quelle"),
    (requests.ConnectionError("host xyz.internal:443"), "Datendienst war nicht erreichbar"),
    (MemoryError(), "Interner Fehler (MemoryError)"),
])
def test_job_failure_message_for_users(parts, error, message):
    speicher, starter, ablage = parts
    e = cloud.CloudAuftragsverwaltung(speicher, starter, ablage).anlegen(STADION)

    def failing(auftrag, ziel, melde):
        raise error

    assert cloud.auftrag_bearbeiten(e.id, speicher, ablage, runner=failing) is False
    doc = speicher.docs[e.id]
    assert doc["status"] == "fehler" and message in doc["fehler"]
    assert "xyz.internal" not in doc["fehler"]                  # no internals for the public
    assert ablage.uploaded == {}


def test_fehlertext_hides_internals():
    assert fehlertext(ValueError("C:/secret/path")) == "Interner Fehler (ValueError). Bitte später noch einmal versuchen."


def test_api_with_cloud_manager(parts):
    speicher, starter, ablage = parts
    client = TestClient(create_app(cloud.CloudAuftragsverwaltung(speicher, starter, ablage, max_gleichzeitig=1)))
    job = client.post(f"{PREFIX}/auftraege", json={"name": "stadion", "bbox": list(STADION.bbox),
                                                   "massstab": 4000}).json()
    assert client.get(f"{PREFIX}/auftraege/{job['id']}").json()["status"] == "wartend"
    r = client.post(f"{PREFIX}/auftraege", json={"name": "zwei", "bbox": list(STADION.bbox), "massstab": 4000})
    assert r.status_code == 429 and "noch einmal versuchen" in r.json()["fehler"]

    assert client.get(f"{PREFIX}/auftraege/{job['id']}/ergebnis").status_code == 409
    cloud.auftrag_bearbeiten(job["id"], speicher, ablage, runner=fake_runner)
    r = client.get(f"{PREFIX}/auftraege/{job['id']}/ergebnis", follow_redirects=False)
    assert r.status_code == 307
    assert r.headers["location"] == f"https://storage.example/{job['id']}/stadion.zip?signed&filename=stadion.zip"
    assert client.get(f"{PREFIX}/auftraege/{job['id']}").headers["cache-control"] == "no-store"
