"""HTTP API for map jobs (FastAPI).

Start locally (from the project folder):
    .\\.venv\\Scripts\\python.exe -m uvicorn api.main:app --reload
Then: http://127.0.0.1:8000/docs (interactive documentation, generated from this file).

A map takes 30 s to minutes, so the API works with jobs:
    POST /api/v1/auftraege  ->  GET /api/v1/auftraege/{id}  ...until "fertig"  ->  GET .../ergebnis
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Literal

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from fastapi import FastAPI, Request  # noqa: E402
from fastapi.exceptions import RequestValidationError  # noqa: E402
from fastapi.responses import FileResponse, JSONResponse  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from olprep.auftrag import Auftrag, Eingabefehler  # noqa: E402
from olprep.ressourcen import SYMBOL_SETS  # noqa: E402

from .auftraege import FERTIG, Auftragsverwaltung, Eintrag  # noqa: E402

PREFIX = "/api/v1"
ARBEITSORDNER = Path(os.environ.get("OLPREP_API_ORDNER", ROOT / "output" / "api"))
ART = {"ISSprOM 2019": "Sprint", "ISOM 2017-2": "Wald", "ISMTBOM": "Mountainbike", "ISSkiOM 2019": "Ski-OL"}


# --- data models (also the OpenAPI documentation) ------------------------------

class AuftragEingabe(BaseModel):
    name: str = Field(description="Kartenname, wird Datei- und Ordnername (Buchstaben, Ziffern, _ und -)",
                      examples=["stadion"])
    bbox: list[float] = Field(min_length=4, max_length=4,
                              description="Kartenbereich: West, Süd, Ost, Nord in Grad (WGS84)",
                              examples=[[16.415, 48.203, 16.427, 48.211]])
    massstab: int = Field(description="Maßstabszahl, z. B. 4000 für 1:4000; muss zum Symbolsatz passen",
                          examples=[4000])
    symbolsatz: str | None = Field(None, description="Standard: ISSprOM 2019 bei 1:4000, sonst ISOM 2017-2")
    aequidistanz: float | None = Field(None, description="Abstand der Höhenlinien in m; Standard 2,5 (Sprint) bzw. 5")
    zaehlkurve: float | None = Field(None, description="Abstand der Zählkurven in m, Vielfaches der Äquidistanz; "
                                                       "Standard 5 × Äquidistanz")
    osm: bool = Field(True, description="OpenStreetMap-Objekte (Gebäude, Wege, Zäune …) übernehmen")


class AuftragStatus(BaseModel):
    id: str
    name: str
    status: Literal["wartend", "laeuft", "fertig", "fehler"]
    fortschritt: int = Field(description="0 bis 100 (Prozent)")
    schritt: str = Field(description="Was gerade läuft, z. B. „Höhenlinien berechnen“")
    fehler: str | None = Field(None, description="Nur bei status „fehler“: was schiefgegangen ist")


class Symbolsatz(BaseModel):
    name: str
    art: str
    massstaebe: list[int]


class Fehler(BaseModel):
    fehler: str


class UTF8JSONResponse(JSONResponse):
    """JSON with explicit charset: Windows PowerShell 5.1 otherwise decodes umlauts as Latin-1."""
    media_type = "application/json; charset=utf-8"


def _status(e: Eintrag) -> AuftragStatus:
    return AuftragStatus(id=e.id, name=e.auftrag.name, status=e.status, fortschritt=e.fortschritt,
                         schritt=e.schritt, fehler=e.fehler)


def _fehler(code: int, text: str) -> JSONResponse:
    return UTF8JSONResponse(status_code=code, content={"fehler": text})


# --- app -----------------------------------------------------------------------

def create_app(verwaltung: Auftragsverwaltung | None = None) -> FastAPI:
    verwaltung = verwaltung or Auftragsverwaltung(ARBEITSORDNER)
    app = FastAPI(
        title="OL-Karten-prep",
        default_response_class=UTF8JSONResponse,
        version="0.1.0",
        description="Bereitet Orientierungslauf-Karten für OpenOrienteering Mapper vor: "
                    "Orthofoto, Höhenlinien, Schummerung und OpenStreetMap-Objekte, georeferenziert "
                    "und nach magnetisch Nord gedreht. Ein Auftrag liefert den Kartenordner als ZIP.",
    )
    app.state.verwaltung = verwaltung

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, exc: RequestValidationError) -> JSONResponse:
        first = exc.errors()[0]
        where = ".".join(str(p) for p in first.get("loc", ()) if p != "body")
        return _fehler(422, f"{where}: {first.get('msg', 'ungültig')}" if where else first.get("msg", "ungültig"))

    @app.get(f"{PREFIX}/symbolsaetze", response_model=list[Symbolsatz], tags=["Einstellungen"],
             summary="Symbolsätze und erlaubte Maßstäbe")
    def symbolsaetze() -> list[Symbolsatz]:
        return [Symbolsatz(name=n, art=ART[n], massstaebe=list(s)) for n, s in SYMBOL_SETS.items()]

    @app.post(f"{PREFIX}/auftraege", status_code=202, response_model=AuftragStatus, tags=["Aufträge"],
              summary="Neuen Kartenauftrag anlegen",
              responses={422: {"model": Fehler, "description": "Eingabe ungültig"}})
    def auftrag_anlegen(eingabe: AuftragEingabe):
        try:
            eintrag = verwaltung.anlegen(Auftrag(eingabe.name, tuple(eingabe.bbox), eingabe.massstab,
                                                 eingabe.symbolsatz, eingabe.aequidistanz,
                                                 eingabe.zaehlkurve, eingabe.osm))
        except Eingabefehler as e:
            return _fehler(422, str(e))
        return _status(eintrag)

    @app.get(f"{PREFIX}/auftraege/{{auftrag_id}}", response_model=AuftragStatus, tags=["Aufträge"],
             summary="Status und Fortschritt abfragen",
             responses={404: {"model": Fehler, "description": "Auftrag nicht gefunden"}})
    def auftrag_status(auftrag_id: str):
        eintrag = verwaltung.holen(auftrag_id)
        if eintrag is None:
            return _fehler(404, f"Auftrag {auftrag_id} nicht gefunden")
        return _status(eintrag)

    @app.get(f"{PREFIX}/auftraege/{{auftrag_id}}/ergebnis", tags=["Aufträge"],
             summary="Fertigen Kartenordner als ZIP herunterladen",
             response_class=FileResponse,
             responses={200: {"content": {"application/zip": {}}, "description": "Kartenordner als ZIP"},
                        404: {"model": Fehler, "description": "Auftrag nicht gefunden"},
                        409: {"model": Fehler, "description": "Auftrag noch nicht fertig"}})
    def auftrag_ergebnis(auftrag_id: str):
        eintrag = verwaltung.holen(auftrag_id)
        if eintrag is None:
            return _fehler(404, f"Auftrag {auftrag_id} nicht gefunden")
        if eintrag.status != FERTIG or eintrag.zip is None:
            text = (f"Auftrag fehlgeschlagen: {eintrag.fehler}" if eintrag.fehler
                    else f"Auftrag läuft noch ({eintrag.fortschritt} %)")
            return _fehler(409, text)
        return FileResponse(eintrag.zip, media_type="application/zip", filename=f"{eintrag.auftrag.name}.zip")

    return app


app = create_app()
