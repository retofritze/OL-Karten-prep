"""API: endpoints, job status and errors. The map building is replaced by a fake runner
(no downloads); the real run is covered by test_referenzkarte.py."""

import threading
import time
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.auftraege import Auftragsverwaltung
from api.main import PREFIX, create_app
from olprep.auftrag import Ergebnis

STADION = {"name": "stadion", "bbox": [16.415, 48.203, 16.427, 48.211], "massstab": 4000}


def fake_runner(auftrag, ziel: Path, melde, gate: threading.Event | None = None, fail: bool = False):
    melde("Orthofoto laden", 5)
    if gate is not None:
        assert gate.wait(5), "test gate not opened"
    if fail:
        raise RuntimeError("Kachelserver nicht erreichbar")
    melde("Karte speichern", 90)
    folder = ziel / auftrag.name
    folder.mkdir(parents=True)
    (folder / f"{auftrag.name}.omap").write_text("<map/>", encoding="utf-8")
    zip_path = ziel / f"{auftrag.name}.zip"
    with zipfile.ZipFile(zip_path, "w") as z:
        z.write(folder / f"{auftrag.name}.omap", f"{auftrag.name}/{auftrag.name}.omap")
    melde("fertig", 100)
    return Ergebnis(folder, folder / f"{auftrag.name}.omap", zip_path, 0)


@pytest.fixture
def make_client(tmp_path):
    managers = []

    def make(**runner_options):
        manager = Auftragsverwaltung(tmp_path, runner=lambda a, z, m: fake_runner(a, z, m, **runner_options))
        managers.append(manager)
        return TestClient(create_app(manager)), manager

    yield make
    for manager in managers:
        manager.beenden()


def wait_until(client, job_id, states=("fertig", "fehler"), timeout=5.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        body = client.get(f"{PREFIX}/auftraege/{job_id}").json()
        if body["status"] in states:
            return body
        time.sleep(0.02)
    raise AssertionError(f"Auftrag {job_id} hängt: {body}")


def test_symbol_sets(make_client):
    client, _ = make_client()
    r = client.get(f"{PREFIX}/symbolsaetze")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/json; charset=utf-8"     # umlauts in PowerShell
    assert {"name": "ISSprOM 2019", "art": "Sprint", "massstaebe": [4000]} in r.json()


def test_job_runs_and_zip_downloads(make_client):
    client, manager = make_client()
    r = client.post(f"{PREFIX}/auftraege", json=STADION)
    assert r.status_code == 202
    job = r.json()
    assert job["name"] == "stadion" and job["status"] in ("wartend", "laeuft")
    # defaults are filled in before the job runs
    assert manager.holen(job["id"]).auftrag.symbolsatz == "ISSprOM 2019"

    done = wait_until(client, job["id"])
    assert (done["status"], done["fortschritt"], done["schritt"]) == ("fertig", 100, "fertig")

    r = client.get(f"{PREFIX}/auftraege/{job['id']}/ergebnis")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/zip"
    assert 'filename="stadion.zip"' in r.headers["content-disposition"]
    assert r.content[:2] == b"PK"


def test_progress_and_409_while_running(make_client):
    gate = threading.Event()
    client, _ = make_client(gate=gate)
    job = client.post(f"{PREFIX}/auftraege", json=STADION).json()
    running = wait_until(client, job["id"], states=("laeuft",))
    end = time.monotonic() + 5
    while running["fortschritt"] != 5 and time.monotonic() < end:
        running = client.get(f"{PREFIX}/auftraege/{job['id']}").json()
    assert (running["fortschritt"], running["schritt"]) == (5, "Orthofoto laden")

    r = client.get(f"{PREFIX}/auftraege/{job['id']}/ergebnis")
    assert r.status_code == 409 and r.json() == {"fehler": "Auftrag läuft noch (5 %)"}
    gate.set()
    assert wait_until(client, job["id"])["status"] == "fertig"


def test_jobs_wait_in_queue(make_client):
    gate = threading.Event()
    client, _ = make_client(gate=gate)
    first = client.post(f"{PREFIX}/auftraege", json=STADION).json()
    second = client.post(f"{PREFIX}/auftraege", json=STADION | {"name": "zweite"}).json()
    wait_until(client, first["id"], states=("laeuft",))
    assert client.get(f"{PREFIX}/auftraege/{second['id']}").json()["status"] == "wartend"
    gate.set()
    assert wait_until(client, second["id"])["status"] == "fertig"


def test_failed_job(make_client):
    client, _ = make_client(fail=True)
    job = client.post(f"{PREFIX}/auftraege", json=STADION).json()
    done = wait_until(client, job["id"])
    assert done["status"] == "fehler"
    assert done["fehler"] == "Kachelserver nicht erreichbar"       # own RuntimeErrors are for users
    r = client.get(f"{PREFIX}/auftraege/{job['id']}/ergebnis")
    assert r.status_code == 409 and "fehlgeschlagen" in r.json()["fehler"]


@pytest.mark.parametrize("body, message", [
    (STADION | {"massstab": 10000, "symbolsatz": "ISSprOM 2019"}, "ISSprOM 2019 gibt es nur für 1:4000"),
    (STADION | {"name": "../x"}, "Name"),
    (STADION | {"bbox": [13.0, 52.4, 13.1, 52.5]}, "nicht in Österreich"),
    (STADION | {"bbox": [16.4, 48.2, 16.5]}, "bbox"),               # checked by FastAPI/pydantic
    ({"name": "x", "bbox": [16.415, 48.203, 16.427, 48.211]}, "massstab"),
    (STADION | {"massstab": "gross"}, "massstab"),
])
def test_invalid_input(make_client, body, message):
    client, _ = make_client()
    r = client.post(f"{PREFIX}/auftraege", json=body)
    assert r.status_code == 422
    assert r.headers["content-type"] == "application/json; charset=utf-8"
    assert list(r.json()) == ["fehler"] and message in r.json()["fehler"]


def test_unknown_job(make_client):
    client, _ = make_client()
    for path in ("/auftraege/gibtsnicht", "/auftraege/gibtsnicht/ergebnis"):
        r = client.get(PREFIX + path)
        assert r.status_code == 404 and r.json() == {"fehler": "Auftrag gibtsnicht nicht gefunden"}


def test_openapi_documentation(make_client):
    client, _ = make_client()
    spec = client.get("/api/openapi.json").json()
    assert set(spec["paths"]) == {f"{PREFIX}/symbolsaetze", f"{PREFIX}/auftraege",
                                  f"{PREFIX}/auftraege/{{auftrag_id}}", f"{PREFIX}/auftraege/{{auftrag_id}}/ergebnis"}
    assert client.get("/api/docs").status_code == 200
