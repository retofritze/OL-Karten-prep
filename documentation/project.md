# OL-Karten-prep

## Projektidee

Ein Programm, das das Zeichnen von Orientierungslauf-(OL-)Karten vereinfacht.
Nachdem auf einer "normalen" Karte ein Bereich ausgewählt wurde, führt das
Programm alle Vorbereitungsschritte automatisch durch und gibt eine
Open-Orienteering-Mapper-Datei (`*.omap`) aus:

1. Luftbild (Orthofoto) importieren
2. Höhenschichtenmodell / Höhenlinien importieren
3. OpenStreetMap-Daten importieren
4. Karte von geografisch Nord nach magnetisch Nord drehen (Deklination)

Ergebnis: eine `.omap`, in der der Kartenzeichner direkt mit dem eigentlichen
Zeichnen bzw. der Feldbegehung anfangen kann.

---

## Analyse des Referenzvideos

**Quelle:** "Online Fortbildung: Kartenerstellung", ÖFOL Orienteering, ca. 1:47 h
<https://www.youtube.com/watch?v=igycyNkwa_w>
(Analyse auf Basis des automatisch erzeugten deutschen YouTube-Transkripts;
Bildschirminhalte waren nicht verfügbar.)

Kontext: Fortbildung für Lehrer/Trainer, die eine kleine **Schulkarte**
(Sprint, 1:4000) erstellen wollen. Der Fokus liegt auf Österreich.

### Gezeigter manueller Workflow (mit Zeitmarken)

| Zeit | Schritt | Relevanz fürs Projekt |
|---|---|---|
| 02:19 | Im ÖFOL-Kartenarchiv prüfen, ob es schon eine Karte gibt (Schulkarten pink) | optional: Hinweis/Check |
| 06:11 | **Orthofoto beschaffen**: Landes-GIS (z. B. Steiermark-Atlas) → Download → Flugjahr (neuestes) → Rasterkachel anklicken → Download. Kachelgröße bzw. Kachelung (Raster vs. Gemeinde) je Bundesland unterschiedlich | **Kern – automatisieren** |
| 08:00–21:50 | Purple Pen: Bahnlegung direkt auf dem Luftbild | außerhalb des Scopes |
| 21:54 | OpenOrienteeringMap (Web, OSM-basiert, 5-m-Höhenlinien) als Schnell-Alternative; Qualität abhängig von OSM | Vergleich/Inspiration |
| 24:39 | OOM: neue Karte, **Maßstab 1:4000**, **Symbolsatz ISSprOM** | **Kern** – Vorlage für die .omap |
| 25:40–49:00 | OOM-Zeichenwerkzeuge (Punkt/Linie/Fläche, Kurven, Füllen, Farbreihenfolge …) | nicht automatisierbar, Handarbeit |
| 49:30 | **Luftbild als Vorlage laden**: GeoTIFF ist georeferenziert; JPG braucht Worldfile (`.jgw`) | **Kern** |
| 50:57 | Georeferenzierung wichtig für GPS-Apps (Navita, Livelox) | Anforderung |
| 51:33 | **Deklination**: Referenzpunkt prüfen, Deklination "abrufen" (Graz: ~5,05°), Vorzeichen-Fehler im Video → Luftbild wird nach magn. Nord gedreht | **Kern – automatisieren** (Vorzeichen sauber lösen!) |
| 1:00:58 | **OSM-Export** (openstreetmap.org → Export → Bereich) → OOM "Datei importieren" → Zuordnungstabelle OSM → OL-Symbol (Standard passt gut) | **Kern – automatisieren** |
| 1:04:19 | Nicht zuordenbare Objekte (violette Punkte, unbekannte Flächen/Linien) per "Alle Objekte mit diesem Symbol auswählen" löschen | **automatisieren** (Aufräumen) |
| 1:05:12 | JPG ohne Georeferenz: manuell über Passpunkte einpassen – mühsam | zeigt Nutzen georef. Daten |
| 1:08:00 | OSM-Qualität: Gebäude gut, Bäume teils verschoben; Stadt gut, Land schlecht | Hinweis an Nutzer |
| 1:11:05 | **Höhenlinien**: basemap.at (Böschungen), Landes-GIS (Wien: 1-m-Schichtenlinien als Download) → als Vorlage/Import in OOM | **Kern – automatisieren** |
| 1:19:50 | Zählkurven fehlen → manuell jede 5. Linie umsymbolisieren; Äquidistanz nur durch Löschen änderbar | **automatisieren**: Zählkurven + frei wählbare Äquidistanz |
| 1:25:07 | Export für Purple Pen: `.omap` direkt öffnen (Maßstab bleibt erhalten) | Ausgabe muss PP-kompatibel sein |
| 1:28:20 | Alte, nicht georeferenzierte Karte nachträglich einpassen | spätere Erweiterung |
| 1:31:00 | **Koordinatensystem**: Wien = MGI/GK M34, Steiermark/Kärnten oft M31 → wurde nicht automatisch erkannt, musste manuell nachgeschaut werden | **Kern** – CRS automatisch korrekt setzen |
| 1:42:02 | Tipp: Höhenlinien selbst aus Laserscan-DGM rechnen (freie Äquidistanz) | **Kern – bevorzugter Weg** |

### Erkenntnisse / Schmerzpunkte, die das Programm lösen soll

- Datenquellen sind je Bundesland verschieden (Portal, Kachelung, Format, CRS).
- Georeferenzierung/CRS geht leicht verloren oder wird falsch erkannt.
- Deklinations-Vorzeichen ist fehleranfällig (selbst im Video passiert).
- Fertige Höhenlinien gibt es nicht überall, oft ohne Zählkurven und mit fester Äquidistanz.
- OSM-Import erzeugt "Müll"-Objekte, die manuell gelöscht werden.
- Alles zusammen kostet Einsteiger viel Zeit, bevor überhaupt gezeichnet wird.

---

## Ziel-Pipeline (Entwurf)

```
[1] Bereich wählen (Rechteck/Polygon auf Webkarte)  + Maßstab + Symbolsatz
        │
[2] Projektion bestimmen (z. B. UTM 33N / MGI GK M28|M31|M34 / Lambert)
        │
        ├─[3a] Orthofoto laden (WMTS/WMS, z. B. basemap.at) → zuschneiden → GeoTIFF
        ├─[3b] DGM laden (ALS 1 m Land / 10 m AT) → Höhenlinien rechnen
        │        (Äquidistanz wählbar, Zählkurven, Glättung, Mindestlänge)
        ├─[3c] OSM via Overpass laden → OL-Symbole zuordnen → Unbekanntes verwerfen
        └─[3d] Deklination berechnen (WMM, Datum) → Grivation
        │
[4] .omap (XML) schreiben:
      - Georeferenzierung (CRS, Referenzpunkt, Deklination/Grivation, Maßstab)
      - Symbolsatz (ISSprOM 2019-2 / ISOM 2017-2)
      - Objekte: Höhenlinien, Zählkurven, OSM-Objekte
      - Vorlagen: Orthofoto (+ ggf. Schummerung/Hangneigung aus DGM)
        │
[5] Ausgabeordner: karte.omap + QUELLEN.txt + daten/  (in OOM und Purple Pen öffnbar)
```

*(Entwurf vom 2026-10-28. Umgesetzt sind [1]–[5] ohne Webkarte. Das Orthofoto wird als
JPG + `.jgw` gespeichert, als Koordinatensystem dient der GK-Streifen der Kartenmitte.)*

### Technische Notizen (vorläufig)

- **.omap** ist XML und wird von uns erfolgreich geschrieben (verifiziert
  per Round-Trip-Test, siehe [omap-format.md](omap-format.md)). Drehung nach
  magnetisch Nord geschieht über die Georeferenzierung, nicht durch Drehen der
  Daten selbst.
- **Symbolsätze** aus der OOM-Installation übernehmen (GPL) statt selbst definieren.
- **Stack**: Python 3.12 (`.venv`, je Rechner neu anlegen, siehe Wiedereinstieg), im Einsatz:
  lxml (XML), pyproj (Koordinaten), pygeomag (Deklination, WMM offline), rasterio (Raster
  lesen/umprojizieren, auch Teil-Downloads aus Cloud Optimized GeoTIFF), requests (Downloads),
  shapely (Geometrie), contourpy (Höhenlinien), scipy (Glättung), FastAPI + uvicorn (API),
  siehe `requirements.txt`; zum Entwickeln pytest, httpx, pyflakes (`requirements-dev.txt`).
  Geplant: Bereichsauswahl über eine kleine Leaflet-Weboberfläche; Betrieb auf Firebase/Cloud Run.
- **Datenquellen** (recherchiert und geprüft 2026-11-02, siehe [datenquellen.md](datenquellen.md)):
  Orthofoto Stadt Wien (WMTS) bzw. basemap.at (WMTS) für den Rest Österreichs, Höhenlinien
  Stadt Wien (WFS), BEV ALS-DGM 1 m für ganz Österreich, OpenStreetMap (Overpass / OSM-API).
- Lizenzen/Attribution der Datenquellen beachten (OSM: ODbL, basemap.at: CC BY).

---

## Planung (Phasen)

*Dateinamen in den Phasen 1–4 beziehen sich auf den Stand vor dem Umbau vom 2026-11-15
(z. B. `osm.py` liegt heute unter `verarbeitung/`), siehe „Projektstruktur“.*

1. **Recherche & Spike**
   - ✅ `.omap`-Format analysiert und Schreiben verifiziert (2026-10-29):
     Georeferenzierung, Deklination, Objekte, Orthofoto-Vorlage mit relativem Pfad.
   - ✅ Datenquellen Wien/NÖ recherchiert und am Server geprüft (2026-11-02):
     [datenquellen.md](datenquellen.md).
2. **MVP (CLI)**: Bounding-Box + Maßstab rein → `.omap` mit Georeferenzierung,
   Deklination und Orthofoto als Vorlage raus.
   - ✅ Erste Version läuft (2026-11-02): `scripts/make_map.py`. Lage des Orthofotos
     gegen das Original der Stadt Wien geprüft (kein messbarer Versatz).
   - ✅ Test in OOM bestanden (2026-11-02): Stadion (Wien, M34) und Waidhofen/Ybbs
     (NÖ, M31) ohne Warnung, Orthofoto scharf und richtig gedreht, OOM läuft flüssig.
3. **Höhenlinien**: DGM laden, Konturen rechnen, Zählkurven, Glättung → als
   OL-Objekte in die `.omap`.
   - ✅ Erste Version läuft (2026-11-02): `src/olprep/hoehenlinien.py`. Fertige Wiener
     Linien (WFS), wenn der Bereich ganz in Wien liegt und Äquidistanz und Zählkurve ganze
     Meter sind, sonst selbst gerechnet aus dem BEV-DGM. Symbole 101 (Höhenlinie) und 102
     (Zählkurve), in allen vier Symbolsätzen gleich codiert.
   - Generalisierung (in mm auf dem Papier, wächst mit dem Maßstab): Glättung des DGM
     σ = 0,3 mm, Vereinfachung 0,05 mm, Linien unter 2,5 mm Länge fallen weg.
     Bei 1:4000 also 1,2 m / 0,2 m / 10 m, bei 1:10000 3 m / 0,5 m / 25 m.
   - ✅ Test in OOM bestanden (2026-11-02): Linien braun, Zählkurven dicker, passen zum
     Gelände (Waidhofen), Glättung „genau richtig“, OOM flüssig. Im flachen Prater weichen
     Wiener Linien (2 m, Wiener Null) und selbst gerechnete (2,5 m, Adria) stark voneinander
     ab. Das ist erwartet: Im flachen Gelände verschiebt schon ein kleiner Höhenunterschied
     eine Linie um viele Meter.
4. **OSM-Import**: Overpass, Zuordnungstabelle OSM-Tags → OL-Symbole
   (Sprint & Wald), Aufräumen nicht zuordenbarer Objekte.
   - ✅ Erste Version läuft (2026-11-02): `src/olprep/osm.py`. Regeln aus den
     OOM-Tabellen (`OSM-ISSprOM 2019.crt`, `OSM-ISOM 2017-2.crt`, `OSM-ISSkiOM 2019.crt`),
     bei mehreren Treffern gilt die letzte Regel. Nicht Zuordenbares wird gar nicht erst
     übernommen. Für ISMTBOM gibt es keine Tabelle, dort kein OSM-Import.
   - Download über Overpass, bei Störung über die OSM-API (`/map` + `/relation/<id>/full`
     für angeschnittene Flächen). Beide Wege liefern fürs Stadion dieselben 1960 Objekte.
   - Jedes Objekt bekommt seine OSM-Tags und `osm_id` als OOM-Tags mit (in OOM über
     „Objekte nach Tags auswählen“ nutzbar). Flächen mit Löchern (Lichtungen, Innenhöfe)
     werden als ein Objekt mit Löchern geschrieben.
   - Lage geprüft: Gebäude und Straßen liegen auf dem Orthofoto (Stadion, Waidhofen).
   - ✅ Test in OOM (2026-11-02): keine Warnung, alles passt zusammen. Die OSM-Einzelbäume
     bleiben (lassen sich in OOM bei Bedarf gesammelt löschen).
   - **Entscheidung 12:** Wald (`natural=wood`, `landuse=forest`) wird weiß „405 Forest“
     statt hellgrün „406 langsam belaufbar“ wie in der OOM-Tabelle. Ausdrücklich als dicht,
     jung oder licht eingetragener Wald behält 408 bzw. 404 (`RULE_CHANGES` in `osm.py`).
   - Gebäude: Die Sprint-Tabelle (ISSprOM, 1:4000) ergibt graue Gebäude, die Wald-Tabelle
     (ISOM, 1:10000/15000) schwarze. So ist es in den IOF-Normen vorgesehen.
   - ✅ Tags in OOM bestätigt (2026-11-02): im deutschen OOM im „Anmerkungseditor“,
     z. B. `landuse = meadow`, `osm_id = way/807912677`.
   - ✅ **Schummerung** (`schummerung.py`, 2026-11-02) aus dem BEV-DGM, 1 m, Licht aus
     Nordwesten (315°, 45° hoch), als zweite Vorlage, anfangs ausgeblendet, weil sie das
     Orthofoto verdecken würde. Lichtrichtung an einem künstlichen Hügel geprüft (NW hell,
     SO dunkel), in OOM bestätigt (passt zu den Höhenlinien). Das DGM wird nur einmal geladen
     und für Höhenlinien und Schummerung gemeinsam genutzt.
   - Nordlinien wurden kurz eingebaut und auf Wunsch wieder entfernt (Entscheidung 14).
5. ✅ **Umbau und API** (2026-11-15): Tests, Schichten, Auftrag mit Prüfung und Fortschritt,
   lokale API (FastAPI), A3-Grenze und Orthofoto-Auflösung nach Maßstab. Details unter
   „Stand und nächste Schritte“.
6. ✅ **Betrieb in der Cloud (Firebase / Cloud Run)** (2026-11-15): online unter
   <https://ol-karten-prep.web.app>, siehe „Betrieb in der Cloud“ unter Wiedereinstieg.
   **Nächster Schritt: Weboberfläche.**
7. **Weboberfläche**: Bereich auf einer Webkarte aufziehen, Einstellungen wählen
   (siehe „Ablauf auf der Website“), fertigen Kartenordner als ZIP herunterladen.
8. **Erweiterungen**: Hangneigung als zusätzliche Vorlage, bessere Landesdaten weiterer
   Bundesländer, Vegetation aus LiDAR (vgl. Karttapullautin), weitere Länder, Einpassen
   alter Karten.

### Außerhalb des Scopes (im Video gezeigt)

- Bahnlegung (Purple Pen), Navita-Events
- Manuelles Zeichnen/Bearbeiten in OOM
- Feldbegehung

---

## Entscheidungen (2026-10-28)

1. **Region**: Österreich, vorerst nur **Ost-Österreich (Wien, Niederösterreich)**,
   weil jedes Bundesland eigene Datenportale hat. *(Stand 2026-11-02: Da die gewählten
   Quellen österreichweit sind, läuft das Programm bereits in ganz Österreich, getestet in Tirol.)*
2. **Kartentyp**: Maßstab wird in der Oberfläche gewählt; der Workflow ist für
   alle Maßstäbe gleich (Sprint/ISSprOM und Wald/ISOM nur unterschiedlicher Symbolsatz).
3. **Bedienung**: Ziel ist eine Weboberfläche; begonnen wird als
   Python-Bibliothek/Kommandozeilentool, die Weboberfläche folgt später.
4. **Technik**: Python + Geodaten-Bibliotheken, wird im Laufe der Planung überprüft.
5. **Ergebnis ist ein Ordner**, nicht nur eine `.omap`: alle erzeugten und
   heruntergeladenen Dateien (Orthofoto, DGM-Ableitungen, OSM-Rohdaten …)
   liegen darin und werden von der `.omap` so referenziert, dass OOM sie
   direkt öffnet (relative Pfade, Ordner verschiebbar).

## Entscheidungen (2026-11-02)

6. **Deklination**: Stichtag ist immer das Datum, an dem die Karte erzeugt wird
   (so bereits umgesetzt: `date.today()` in `Georeferencing.create`).
7. **Koordinatensystem**: Gauß-Krüger-Streifen nach der Kartenmitte, östlich von
   14°50′ EPSG:31256 (M34), westlich EPSG:31255 (M31), westlich von 11°50′ EPSG:31254
   (M28). Nach Recherche bestätigt, Begründung in [datenquellen.md](datenquellen.md).
8. **Höhenlinien**: fertige Downloads verwenden, wo sie gut sind (Wien: 1-m-Linien der
   Stadt). Wo es keine oder nur schlechte gibt (NÖ: nur BEV 5 m, veraltet), selbst aus dem
   BEV ALS-DGM 1 m rechnen. Auch in Wien selbst rechnen, wenn 2,5 m Abstand gewünscht ist.

## Entscheidungen (2026-11-02, Fortsetzung)

9. **Orthofoto-Auflösung**: immer die beste verfügbare mit echten Details. Wien: Zoom 20
   (10 cm), Zoom 21 ist nur hochgerechnet. basemap.at: Zoom 20, wo vorhanden, sonst 19 (20 cm).
   *Seit 2026-11-15 ersetzt durch Entscheidung 20 (Auflösung nach Maßstab); 10 cm bleibt die
   feinste Stufe und gilt weiterhin für Sprint (1:4 000).*
10. **Quelle Wien/NÖ**: Stadt-Wien-Orthofoto, wenn alle Kacheln des Bereichs vorhanden
    sind (Abdeckung reicht ca. 1–2 km über die Stadtgrenze), sonst basemap.at.
11. **Datumstransformation MGI ↔ WGS84**: überall die Standardtransformation von PROJ,
    „MGI to WGS 84 (3)“ (angegebene Genauigkeit 1,5 m). pyproj und GDAL wählen sie gleich
    (0,000 m Unterschied). Die Wiener Orthofoto-Kacheln passen damit ohne Versatz auf das
    Original in EPSG:31256, viele OSM-Daten sind von diesen Luftbildern abgezeichnet. Die
    genauere Variante (8) würde OSM und Orthofoto gegeneinander verschieben.
12. **Wald aus OSM weiß** (405) statt hellgrün (406), siehe Phase 4.
13. **Ein Datenordner**: Alle Dateien einer Karte liegen in `daten/` (Orthofoto,
    Schummerung, OSM-Rohdaten), daneben nur `.omap` und `QUELLEN.txt`.
14. **Keine automatischen Nordlinien**: OOM hat dafür das Flächensymbol „Nordlinien-Raster“
    (ISOM 601.2 schwarz / 601.4 blau, ISSprOM 601.1 / 601.6). Damit zeichnet der Benutzer
    die Nordlinien schnell selbst und wählt dabei schwarz oder blau.
15. **Orthofoto immer der neueste Jahrgang**, keine Auswahl.

## Architektur (Entscheidungen 2026-11-10)

16. **Logik und Oberfläche getrennt über eine API.** Website, Kommandozeile und spätere
    Oberflächen nutzen dieselbe Logik. Die API arbeitet mit Aufträgen (Auftrag abschicken →
    Nummer, Fortschritt abfragen, ZIP herunterladen), weil eine Karte 30 s bis Minuten dauert.
17. **Ein Repository, ein Python-Paket mit getrennten Schichten** (keine getrennten
    Projekte: gleicher Stack, eng verzahnt, kleines Team; später trennbar). GitHub:
    <https://github.com/retofritze/OL-Karten-prep> (**öffentlich seit 2026-11-15**, Branch
    `main`). Vor dem Veröffentlichen geprüft: keine Passwörter oder Schlüssel; lokale Pfade mit
    Benutzernamen entfernt; die Versionsgeschichte (7 Commits ab 2026-11-14) durch einen
    einzigen bereinigten Commit ersetzt (alte Commits bleiben über ihre Kennung abrufbar, bis
    GitHub aufräumt; endgültig entfernen nur über den GitHub-Support). In Doku und Lab Notebook künftig keine lokalen Pfade
    mit Benutzernamen (`C:\Users\<Benutzer>\…` schreiben). Lizenz **GPL-3.0** (`LICENSE`). Commits mit der anonymen GitHub-Adresse
    `355008406+retofritze@users.noreply.github.com` (nur im Repository eingestellt, nicht global).
    Zeilenenden: LF (`.gitattributes`). Nicht im Repository: `.venv`, `cache/`, `output/`,
    `data/spec/` (IOF-PDFs, 18 MB), das Test-Orthofoto `36_3_op_2025.jpg` (40 MB, Bezug
    siehe datenquellen.md; ohne Orthofoto erzeugt `make_testfile.py` die Karte ohne Vorlage)
    und Office-Dateien wie die Vorlage der Infografik (`*.pptx`, `*.docx`: Metadaten enthalten
    den Namen des Autors).
    Struktur (umgesetzt 2026-11-15, nur `web/` fehlt noch; Details unter „Projektstruktur“):
    ```
    src/olprep/
      quellen/        Daten beschaffen: Orthofoto, Geländemodell, OSM, Wien-Daten (+ Zwischenspeicher)
      verarbeitung/   Georeferenz, Höhenlinien, Schummerung, Symbolzuordnung
      ausgabe/        .omap, Kartenordner, ZIP; Speicher austauschbar (lokal / Cloud Storage)
      auftrag.py      Steuerung: Auftrag rein, Ergebnis raus, meldet Fortschritt
    api/              FastAPI
    web/              Website (HTML/JS, Leaflet)
    scripts/          Kommandozeile
    tests/
    documentation/
    ```
    Abhängigkeiten nur in eine Richtung: web → api → auftrag → verarbeitung/ausgabe → quellen.
18. **Ziel-Plattform Firebase (öffentlich):** Firebase Hosting (Website), Cloud Run
    (Python-Container mit API und Logik; empfohlen statt Cloud Functions wegen GDAL,
    Speicher und Laufzeit), Firestore (Auftragsstatus), Cloud Storage (ZIPs), optional
    Firebase Authentication. Erfordert den Tarif „Blaze“, Budget-Warnung einrichten.
    Grenzen von Cloud Run / Functions vor der Festlegung in der aktuellen Doku prüfen.
    Folgen für den Code:
    - **OOM-Symbolsätze und `.crt`-Tabellen mitliefern** (in der Cloud gibt es keine
      OOM-Installation). Sie stehen unter der GPL, deshalb Projektlizenz voraussichtlich GPL-3.0.
    - **OSM für eine öffentliche Website:** Die OSM-API ist als Ersatz nicht erlaubt. Overpass
      oder ein eigener Datenauszug, dazu eine Begrenzung der Kartengröße.

## Entscheidungen (2026-11-15): Kartengröße, Orthofoto, Betrieb

19. **Höchstens A3:** Der Bereich muss beim gewählten Maßstab auf ein A3-Blatt passen
    (420 × 297 mm, hoch oder quer; `PAPIER_MM` in `auftrag.py`). Ersetzt die vorläufige
    Grenze von 4 km². In der Natur: 1:4 000 → 1,68 × 1,19 km, 1:10 000 → 4,2 × 2,97 km,
    1:15 000 → 6,3 × 4,46 km, 1:20 000 → 8,4 × 5,94 km.
20. **Auflösung des Orthofotos nach Maßstab:** 1 Pixel = 0,025 mm auf dem Papier
    (`PIXEL_MM`), nie gröber als 0,5 m. 10 cm bei 1:4 000 (wie bisher), 25 cm bei 1:10 000,
    50 cm bei 1:20 000. Volles A3 = 16 800 × 11 880 Pixel bei jedem Maßstab. Kacheln werden auf
    der gröbsten Zoomstufe geladen, die (bis 10 % Toleranz) fein genug ist, und mit
    Mittelwertbildung verkleinert (`Resampling.average`), damit schmale Merkmale (Wege, Zäune,
    Kulturgrenzen) als blassere Linie erhalten bleiben. Gebäude, Wege, Zäune kommen zusätzlich
    als OSM-Vektoren. Außerhalb Wiens liefert basemap.at meist höchstens 20 cm.
21. **Gemessen (2026-11-15, volles A3):** 1:10 000 bei Waidhofen/Ybbs (4,1 × 2,8 km): 5040
    Kacheln, 151–175 s, Spitze 1,7 GB Arbeitsspeicher, ZIP 44 MB. 1:20 000 (8,1 × 5,7 km,
    ohne OSM): 4920 Kacheln, 164 s, Spitze 1,7 GB, ZIP 49 MB. Ein Aufteilen des Orthofotos ist
    nicht nötig. **Cloud Run: 4 GB** (Dateien liegen dort ebenfalls im Arbeitsspeicher).
22. **Öffentlicher Zugang** zur Website, ohne Anmeldung (erwartet: eine Handvoll Nutzer).
    Schutz über die A3-Grenze und die Warteschlange (Aufträge nacheinander).
23. **Rechenzentrum `europe-west1`** (Belgien), obwohl die Nutzer in Österreich sind:
    Laufzeit eines Auftrags (Minuten) überwiegt die Netzlaufzeit bei Weitem, günstigere
    Preisstufe als Frankfurt/Zürich, Weiterleitung von Firebase Hosting möglich (beim
    Einrichten in der aktuellen Doku prüfen).

## Ablauf auf der Website (Vorgabe 2026-11-02)

Der Benutzer stellt möglichst viel selbst ein, damit das Programm für viele
verschiedene Karten taugt. Aus den Einstellungen entscheidet das Programm selbst,
welche Daten es verwendet (z. B. fertige Höhenlinien oder selbst gerechnete).

| Schritt | Eingabe | Kommandozeile (heute / geplant) |
|---|---|---|
| 1 | Bereich auswählen | `--bbox W S O N` ✅ |
| 2 | Symbolsatz (wie beim Anlegen einer neuen Karte in OOM) | `--symbolsatz` ✅ |
| 3 | Maßstab | `--scale` ✅ |
| 4 | Äquidistanz (Abstand der Höhenlinien) | `--aequidistanz` ✅ |
| 5 | Zählkurvenabstand | `--zaehlkurve` ✅ |
| 6 | weitere Einstellungen, die sich später ergeben: OSM ja/nein | `--kein-osm` ✅ |
| – | Download des fertigen Kartenordners (ZIP) | `output/<name>.zip` ✅, API `…/ergebnis` ✅ |

**Größe des Bereichs (seit 2026-11-15, Entscheidung 19):** höchstens A3 beim gewählten
Maßstab. Die Website soll deshalb beim Aufziehen des Bereichs einen A3-Rahmen für den
gewählten Maßstab anzeigen (hoch oder quer).

**Symbolsatz und Maßstab hängen zusammen:** OOM liefert jeden Symbolsatz nur für
bestimmte Maßstäbe mit (Stand OOM 0.9.6):

| Symbolsatz | Maßstäbe |
|---|---|
| ISSprOM 2019 (Sprint) | 4000 |
| ISOM 2017-2 (Wald) | 10000, 15000 |
| ISMTBOM (Mountainbike-OL) | 5000, 7500, 10000, 15000, 20000 |
| ISSkiOM 2019 (Ski-OL) | 5000, 7500, 10000, 12500, 15000 |

`Course_Design` (Bahnlegung) wird nicht angeboten. Die Website zeigt nach der Wahl des
Symbolsatzes nur die passenden Maßstäbe an.

**Für Schritt 6 entschieden (2026-11-02):** Die Schummerung kommt immer mit, ohne
Einstellung. Nordlinien gibt es nicht (Entscheidung 14). Kein Orthofoto-Jahrgang zum
Auswählen, es wird immer der neueste genommen. OSM-Einzelbäume bleiben drin (lassen sich
in OOM gesammelt löschen).

Details zum Dateiformat: [omap-format.md](omap-format.md)
Details zu den Datenquellen: [datenquellen.md](datenquellen.md)

## Fachliche Vorgaben (IOF-Spezifikationen in `data/spec`)

Die PDFs (ISSprOM 2019-2, Best Practices Sprint 2025, Ankündigung ISSprOM 2031)
beschreiben den Karteninhalt, nicht das Dateiformat. Für die Automatisierung relevant:

- Sprint: Maßstab 1:4000 (Vergrößerung 1:3000), **Äquidistanz 2 m oder 2,5 m**
  (5 m nur in steilem Gelände). Wald (ISOM): üblicherweise 5 m.
- Karte nach **magnetisch Nord** ausgerichtet; Nordlinien (Symbol 601) im
  Abstand von 30 mm auf Papier (Sprint = 120 m). Zeichnet der Benutzer selbst mit dem
  Nordlinien-Raster von OOM (Entscheidung 14).
- Mindestgrößen und Generalisierungsregeln (Best Practices) → später für das
  Aufbereiten der OSM-Daten nützlich.
- ISOM wird gerade überarbeitet (Entwurf Herbst 2026), ISSprOM 2031 folgt. Die
  Symbolsätze sollten deshalb austauschbar bleiben.

## Projektstruktur (Stand 2026-11-15)

```
CLAUDE.md           Arbeitsregeln für Claude (Sprache, Lab Notebook, OOM-Dateien)
LICENSE             GPL-3.0
.gitignore, .gitattributes   was nicht ins Repository kommt; Zeilenenden LF
documentation/      project.md (diese Datei), omap-format.md, datenquellen.md,
                    unterhaltung.md (Lab Notebook), projektuebersicht.html (Projektseite:
                    Infografik, API, Links, Checkliste; eigenständig ohne externe
                    Dateien, lokal per Doppelklick, später auf Firebase Hosting; nicht auf
                    claude.ai veröffentlichen)
data/               Eingangs- und Referenzdaten (nicht vom Programm erzeugt)
  spec/             IOF-Spezifikationen (PDF)
  Orthofoto_Wien_Stadion/   Test-Orthofoto Stadt Wien (JPG + .jgw, EPSG:31256)
  referenz_georef.omap      in OOM erstellte Referenz
  test_stadion_roundtrip.omap  unsere Testdatei, in OOM gespeichert
src/olprep/         Python-Paket in Schichten (seit 2026-11-15, Entscheidung 17):
  ressourcen.py     OOM-Symbolsätze und .crt-Tabellen (Ort, Maßstäbe), von allen Schichten genutzt
  oom_symbolsaetze/ mitgelieferte Kopien aus OOM 0.9.6 (GPL-3.0): Symbolsätze je Maßstab, OSM-*.crt
  quellen/          Daten beschaffen: orthofoto.py (Kacheldienste), gelaende.py (BEV-DGM),
                    wien.py (WFS: Stadtgrenze, Höhenlinien), osm.py (Overpass / OSM-API),
                    netz.py (User-Agent, Zwischenspeicher)
  verarbeitung/     georef.py (Georeferenzierung, GK-Streifen), hoehenlinien.py (Wien oder
                    selbst berechnet), schummerung.py, osm.py (Regeln, OSM → OL-Symbole)
  ausgabe/          omap.py (.omap schreiben), bilder.py (JPG + .jgw),
                    kartenordner.py (Text für QUELLEN.txt, ZIP)
  auftrag.py        Auftrag (Einstellungen + Prüfung) und ausfuehren() mit Fortschritt
                    Abhängigkeiten nur auftrag → verarbeitung/ausgabe → quellen;
                    tests/test_schichten.py prüft das.
api/                HTTP-API (FastAPI): main.py (Adressen, Datenmodelle = OpenAPI-Doku),
                    auftraege.py (lokal: Warteschlange, Status, Ergebnis), cloud.py (Cloud:
                    Firestore, Cloud Run Jobs, Cloud Storage), job.py (Einstieg des Cloud Run Jobs);
                    nutzt olprep.auftrag
deploy/             einstellungen.ps1, einrichten.ps1 (einmalig), hochladen.ps1 (je Version)
Dockerfile, requirements-cloud.txt, .gcloudignore   Container für Cloud Run (feste Versionen)
firebase.json, .firebaserc, firestore.rules          Firebase Hosting und Firestore-Regeln
scripts/            make_map.py (Kommandozeilenprogramm), make_testfile.py (Formattest)
tests/              pytest-Tests; referenz/stadion.json = Zusammenfassung der Referenzkarte,
                    referenz/stadion_osm.json.gz = gespeicherter OSM-Download dafür
pytest.ini, requirements-dev.txt   Testeinstellungen; Pakete zum Entwickeln (pytest, pyflakes)
output/             erzeugte Ergebnisordner, je Karte: <name>.omap, QUELLEN.txt und
                    daten/ mit orthofoto.jpg + .jgw, schummerung.jpg + .jgw, osm.json;
                    daneben <name>.zip mit dem ganzen Ordner (seit 2026-11-15)
                    (nur output/test_stadion/ hat noch die alte Form mit templates/)
cache/              heruntergeladene Kacheln (wird wiederverwendet, darf gelöscht werden)
```

Die Ordner sind normal verschachtelt (z. B. `output` → `test_stadion` → `templates`).
VS Code zeigt Ordner mit nur einem Unterordner zusammengefasst als
`output\test_stadion` an (Einstellung `explorer.compactFolders`).

## Wiedereinstieg

**Speicherorte:**
- bis 2026-10-31: auf dem alten Laptop
- 2026-11-01 bis 2026-11-10: im OneDrive-Ordner der Schule
- ab 2026-11-10: `C:\Users\<Benutzer>\Documents\OL-Karten-prep` (**außerhalb von OneDrive**, weil
  sich Git und OneDrive schlecht vertragen; der Ordner „Dokumente“ wird auf diesem Laptop
  nicht von OneDrive synchronisiert, geprüft 2026-11-10).

**Nach dem Umzug:**
1. `.venv` neu anlegen (siehe „Neu aufsetzen“ unten). Eine verschobene `.venv` funktioniert
   oft nur halb, weil manche Startdateien den alten Pfad enthalten.
2. Claude Code im neuen Ordner starten. Die Arbeitsregeln für Claude stehen in `CLAUDE.md`
   im Projektordner und ziehen deshalb mit um. Claudes automatisches Gedächtnis ist dagegen
   an den alten Pfad gebunden.
3. Testlauf: `.\.venv\Scripts\python.exe scripts\make_testfile.py`.

```powershell
# Karte erzeugen: Name, Bereich West Süd Ost Nord (Grad, WGS84), Maßstab,
# optional --symbolsatz, --aequidistanz, --zaehlkurve, --kein-osm (Hilfe: --help)
# Vorher prüfen, dass die Karte nicht in OOM offen ist (der Ordner wird überschrieben).
.\.venv\Scripts\python.exe scripts\make_map.py stadion --bbox 16.415 48.203 16.427 48.211 --scale 4000
.\.venv\Scripts\python.exe scripts\make_map.py stadion_2m --bbox 16.415 48.203 16.427 48.211 --scale 4000 --aequidistanz 2 --zaehlkurve 10
.\.venv\Scripts\python.exe scripts\make_map.py waidhofen_ybbs --bbox 14.765 47.955 14.781 47.965 --scale 10000
.\.venv\Scripts\python.exe scripts\make_map.py innsbruck_hungerburg --bbox 11.385 47.284 11.405 47.296 --scale 10000

.\.venv\Scripts\python.exe scripts\make_testfile.py   # Formattest: output\test_stadion\test_stadion.omap
```

**API lokal starten** (Ergebnisse unter `output\api\<Auftragsnummer>\`):

```powershell
.\.venv\Scripts\python.exe -m uvicorn api.main:app --reload
# Doku zum Ausprobieren: http://127.0.0.1:8000/api/docs   Beenden: Strg+C
$job = Invoke-RestMethod -Method Post http://127.0.0.1:8000/api/v1/auftraege -ContentType "application/json" `
  -Body '{"name":"stadion","bbox":[16.415,48.203,16.427,48.211],"massstab":4000}'
Invoke-RestMethod http://127.0.0.1:8000/api/v1/auftraege/$($job.id)          # Status, Fortschritt
Invoke-WebRequest http://127.0.0.1:8000/api/v1/auftraege/$($job.id)/ergebnis -OutFile stadion.zip
```

**Neu aufsetzen** (nötig auf jedem neuen Rechner, denn eine `.venv` ist an den Pfad
des Python-Interpreters gebunden und lässt sich nicht kopieren):

```powershell
winget install --id Python.Python.3.12 --scope user     # falls kein Python installiert ist
Remove-Item -Recurse -Force .venv
& "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe" -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt   # Programm + pytest
```

**Werkzeuge für Firebase** (installiert 2026-11-15: Node.js 26.13.1, Firebase-CLI 15.36.0,
Google Cloud SDK 593.0.0; Installation fragt nach Administrator-Bestätigung):

```powershell
winget install --id OpenJS.NodeJS.LTS -e
winget install --id Google.CloudSDK -e
npm install -g firebase-tools          # nach Neustart von VS Code, damit node/npm im Pfad sind
firebase login                         # Anmeldung im Browser
gcloud auth login
```

**Betrieb in der Cloud** (seit 2026-11-15, Projekt `ol-karten-prep`, Region `europe-west1`):

- Öffentliche Adresse: <https://ol-karten-prep.web.app> (Projektübersicht),
  API unter `/api/v1/…`, Doku zum Ausprobieren unter <https://ol-karten-prep.web.app/api/docs>.
- **Aufbau:**
  - *Firebase Hosting* liefert `documentation/projektuebersicht.html` als Startseite aus
    (`*.md` und Office-Dateien ausgeschlossen, `firebase.json`) und leitet `/api/**` an den
    Cloud-Run-Service `olprep-api` weiter.
  - *Service `olprep-api`* (1 GB, 0–2 Instanzen, öffentlich): nimmt Aufträge an, speichert sie
    in Firestore (Sammlung `auftraege`) und startet je Auftrag eine Ausführung des Jobs mit
    `AUFTRAG_ID`. Höchstens 3 Aufträge gleichzeitig (sonst 429). Download = Weiterleitung (307)
    auf einen 1 Stunde gültigen, signierten Link in Cloud Storage.
  - *Job `olprep-auftrag`* (4 GB, 2 CPU, höchstens 30 min, keine Wiederholung): baut die Karte
    in `/tmp`, meldet den Fortschritt an Firestore, lädt das ZIP nach
    `gs://ol-karten-prep-ergebnisse/<id>/<name>.zip`.
  - *Cloud Storage* `ol-karten-prep-ergebnisse`: privat, ZIPs werden nach 1 Tag gelöscht.
  - *Firestore* (Native, `europe-west1`): nur der Server greift zu, Zugriff aus dem Browser
    ist per Regeln gesperrt (`firestore.rules`).
  - Dienstkonto `olprep-runner` für Service und Job, mit nur den nötigen Rechten
    (Firestore-Benutzer, Objekt-Admin am Bucket, Job starten, eigene Signatur für die Links).
- **Unterschiede zu lokal:** OSM nur über Overpass (`OLPREP_OSM_API_ERSATZ=0`), Kachel-Cache in
  `/tmp`, Fehlermeldungen ohne interne Details. Container mit fest eingestellten Versionen
  (`requirements-cloud.txt`), OOM-Symbolsätze aus `src/olprep/oom_symbolsaetze/`.
- **Einmal eingerichtet** mit `deploy\einrichten.ps1` (Dienste, Firestore, Bucket, Image-Ablage,
  Dienstkonto). **Neue Version hochladen** (nach den Tests und einem Commit; das Image trägt die
  Commit-Kennung):

  ```powershell
  powershell -ExecutionPolicy Bypass -File deploy\hochladen.ps1
  ```

- **Getestet 2026-11-15** über die öffentliche Adresse: Stadion 1:4 000 in 72 s, ZIP mit
  derselben Orthofoto-Datei wie lokal; ungültige Eingabe → 422; `*.md` und `*.pptx` nicht
  abrufbar.
- **Logs:** Google Cloud Console → Cloud Run → `olprep-api` bzw. `olprep-auftrag` → Logs.

**Tests** (pytest, Einstellungen in `pytest.ini`, Stand 2026-11-15: pytest 9.2.0):

```powershell
.\.venv\Scripts\python.exe -m pytest            # 100 schnelle Tests ohne Internet, ca. 10 s
.\.venv\Scripts\python.exe -m pytest -m netz    # Referenzkarte, mit Internet, 15 s bis 1 min
.\.venv\Scripts\python.exe -m pyflakes src scripts tests   # ungenutzte Importe u. Ä.
```

- Schnelle Tests: GK-Streifen, Gitterkorrektur und Deklination gegen die von OOM gespeicherten
  Dateien in `data/`, `.omap` schreiben und zurücklesen, OSM-Regeln und Symbolzuordnung,
  Prüfung der Eingaben. Tests, die die OOM-Symbolsätze brauchen, werden ohne OOM übersprungen.
- Referenzkarte (`tests/test_referenzkarte.py`): erzeugt `stadion` (1:4000) in einem
  temporären Ordner mit festem Datum 2026-11-15 (die Deklination dreht sonst alle
  Papierkoordinaten) und vergleicht mit `tests/referenz/stadion.json` (Dateien,
  Georeferenz, Vorlagen, Bildgrößen, Objekte je Symbol und Prüfsummen der Koordinaten).
  OSM kommt dabei aus einem gespeicherten Overpass-Download (`tests/referenz/stadion_osm.json.gz`,
  2026-11-15), weil sich OSM laufend ändert und der Ersatzweg über die OSM-API dieselben
  Objekte in anderer Form liefert. Orthofoto, Geländemodell und Wiener Höhenlinien werden
  geladen (Kacheln aus `cache/`, dann ca. 15 s). Die Referenz stammt vom Code vor dem
  Umbau 5b; der umgebaute Code ergibt exakt dieselbe Karte.
  Nur nach größeren Umbauschritten laufen lassen. Neue Referenz nur bei gewollter Änderung:
  `$env:OLPREP_REFERENZ_NEU = "1"` setzen, Test laufen lassen, Variable wieder löschen.

Stand 2026-11-02: Python 3.12.10, lxml 6.1.3, pyproj 3.8.0 (PROJ 9.8.1), pygeomag 1.1.0,
rasterio 1.5.2 (GDAL 3.12.2), requests 2.34.2, shapely 2.2.0, contourpy 1.4.0, scipy 1.18.1
(für den OSM-Import kamen keine neuen Pakete dazu).
OOM 0.9.6 liegt unter `C:\Program Files\OpenOrienteering Mapper 0.9.6` (sonst
Umgebungsvariable `OOM_SYMBOL_SETS` setzen).

Erwartete Ausgabe: Grid-Faktor 1.000005; Deklination/Grivation hängen vom Tag ab
(Deklination wird für das aktuelle Datum berechnet, steigt in Wien um ca. 0,1°/Jahr):
am 2026-10-29 5.38°/5.32°, ab 2026-11-01 5.39°/5.33°. Die Datei öffnet in OOM 0.9.6
ohne Warnung, der Kreis liegt mittig ums Stadion (bestätigt 2026-10-29).

## Stand und nächste Schritte (2026-11-15)

**Fertig und in OOM bestätigt:** Phasen 1–4. Das Kommandozeilenprogramm erzeugt für einen
Bereich in ganz Österreich (höchstens A3 beim gewählten Maßstab) einen Kartenordner mit
Georeferenzierung und Deklination, Orthofoto (Auflösung nach Maßstab, Entscheidung 20),
Höhenlinien und Zählkurven (Wien fertig, sonst aus dem BEV-DGM), Schummerung, OSM-Objekten
mit Symbolzuordnung und Tags sowie Quellen- und Lizenzhinweisen (Kartennotizen und
`QUELLEN.txt`), dazu ein ZIP des Ordners.

**Fertig seit 2026-11-15 (Phase 5):** Code in Schichten mit 88 schnellen Tests und einem
Referenzkarten-Test, Auftrag mit Prüfung und Fortschritt, lokale API, öffentliches
GitHub-Repository. Orthofoto-Auflösung nach Maßstab vom Benutzer bestätigt („passt so“).

**Ganz Österreich (getestet 2026-11-02):** Orthofoto (basemap.at), Geländemodell (BEV) und
OSM decken ganz Österreich ab, die Wahl des GK-Streifens ebenso. Testkarte
`innsbruck_hungerburg` (Tirol, 1:10000): Streifen M28 (EPSG:31254) automatisch gewählt,
Höhenlinien 602–1362 m passen zur Nordkette, 970 OSM-Objekte. Wien-spezifisch sind nur die
Extras (10-cm-Orthofoto, fertige Höhenlinien).

**Testkarten** in `output/`: `stadion` (Wien, 1:4000), `stadion_2m` (Wien, fertige
Höhenlinien 2 m), `waidhofen_ybbs` (NÖ West, M31, 1:10000), `innsbruck_hungerburg` (Tirol,
M28, 1:10000), `test_stadion` (Formattest von Phase 1). Seit 2026-11-15 zusätzlich
`wald_a3_10000` (Waidhofen, volles A3 bei 1:10 000, 25 cm), `mtbo_a3_20000` (volles A3 bei
1:20 000, 50 cm, ohne OSM), `vergleich_wien_10cm` / `vergleich_wien_25cm` (Schwarzenbergpark,
1 × 1 km, Vergleich der Auflösungen) und `api/` (Ergebnisse der lokalen API). Die älteren
Testkarten stammen noch aus der Zeit vor der Auflösung nach Maßstab.

**Nächste Schritte (Stand 2026-11-15):**
1. ✅ Projektordner aus OneDrive verschoben, `.venv` neu angelegt, Testlauf ok (2026-11-10).
2. ✅ Git 2.56.0 und GitHub-CLI 2.103.3 installiert (`winget install --id Git.Git`,
   `winget install --id GitHub.cli`, 2026-11-10), Anmeldung als `retofritze` (2026-11-14).
3. ✅ Anonyme GitHub-Adresse für die Commits, Lizenz GPL-3.0 (2026-11-14).
4. ✅ `.gitignore` erweitert, `.gitattributes` (LF), erster Commit, Push nach GitHub (2026-11-14).
5. Code in die Schichten aus Entscheidung 17 umbauen (Verhalten unverändert, mit Tests absichern).
   ✅ 5a Tests (2026-11-15), siehe „Tests“ unter Wiedereinstieg. ✅ 5b Module in
   `quellen/`, `verarbeitung/`, `ausgabe/` aufgeteilt (2026-11-15, Ergebnis unverändert).
   ✅ 5c `auftrag.py` (2026-11-15): `Auftrag` mit den Feldern des API-Entwurfs und
   `geprueft()` (Name, Bereich in Österreich, Fläche, Symbolsatz/Maßstab, Äquidistanz,
   Zählkurve; Standardwerte werden eingesetzt), `ausfuehren()` meldet Schritt + Prozent und
   schreibt zusätzlich `<name>.zip`. Ersetzt `build.py`; Karte unverändert (Referenztest).
6. ✅ **API lokal** (2026-11-15, FastAPI 0.163, uvicorn 0.54), wie im Entwurf der
   Projektübersicht: `GET /api/v1/symbolsaetze`, `POST /api/v1/auftraege` (202),
   `GET /api/v1/auftraege/{id}`, `GET /api/v1/auftraege/{id}/ergebnis` (ZIP; 409 solange nicht
   fertig). Fehler immer als `{"fehler": "…"}` (404, 409, 422), JSON mit `charset=utf-8`
   (sonst falsche Umlaute in Windows PowerShell 5.1). Aufträge laufen **nacheinander** in
   einem Hintergrund-Thread (wartende zeigen „wartend“); Status im Arbeitsspeicher (geht beim
   Neustart verloren), Ergebnisse in `output/api/<id>/`. 13 API-Tests mit Ersatz-Ablauf ohne
   Download; ein echter Auftrag über den Server getestet (Stadion, 62 s, davon 48 s Overpass).
   Seit 2026-11-15 außerdem A3-Grenze und Orthofoto-Auflösung nach Maßstab (Entscheidungen 19–21).
7. ✅ **Firebase / Cloud Run** (2026-11-15; vom Benutzer vor die Website gezogen): online unter
   <https://ol-karten-prep.web.app>, Aufbau unter „Betrieb in der Cloud“. Geprüft in der
   aktuellen Doku: Firebase Hosting bricht weitergeleitete Anfragen nach 60 s ab (`europe-west1`
   ist eine empfohlene Region), Cloud Run Jobs laufen bis 168 h und lassen sich mit eigenen
   Umgebungsvariablen starten (Recht `run.jobs.runWithOverrides`). Zwei Fehler beim ersten
   Hochladen behoben: fehlende Systembibliothek `libexpat` für rasterio (der Build prüft jetzt
   die Importe) und das Lesen der Job-Beschreibung (`run.jobs.get`) ohne Berechtigung.
8. **Website** ← nächster Schritt (Leaflet: Bereich wählen mit A3-Rahmen, Einstellungen, Fortschritt, Download).
   Lizenzhinweis (CC BY 4.0 / ODbL, Quellen müssen auf die Karte) gut sichtbar anzeigen.

## Offene Fragen

- Höhenbezug: Fertige Wiener Linien liegen auf ganzen Metern über Wiener Null, selbst
  gerechnete auf Vielfachen der Äquidistanz über Adria (EVRF2000, im Mittel 0,5 m unter
  den Wiener Höhen). Für die Kartenform egal. Höhenzahlen an Zählkurven später ggf. angleichen.
- Lokale API: Alte Aufträge werden nicht gelöscht (`output/api/` wächst; bei Bedarf von Hand
  löschen). In der Cloud löscht Cloud Storage die ZIPs nach 1 Tag. Die Einträge in Firestore
  bleiben (wenige Bytes je Auftrag), bei Bedarf später eine Aufbewahrungsregel (TTL) einrichten.
- Budget-Warnung im Google-Cloud-Zahlungskonto: vom Benutzer einzurichten (z. B. 10 €/Monat),
  Stand 2026-11-15 nicht geprüft.
- Der Testclient von FastAPI meldet, dass `httpx` dort veraltet ist und `httpx2` erwartet
  wird (Hinweis, Tests laufen). Umstellen, sobald das Paket geprüft ist.
- Overpass war am 2026-11-02 meist gestört. Für eine öffentliche Website mit vielen
  Benutzern ist die OSM-API als Ersatz nicht gedacht (siehe [datenquellen.md](datenquellen.md)).
