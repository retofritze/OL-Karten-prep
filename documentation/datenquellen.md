# Datenquellen Wien und Niederösterreich

Stand 2026-11-02. Alle Angaben unten mit **(geprüft)** wurden direkt am Server getestet
(Abruf von Dateien, Kacheln bzw. Capabilities). Die übrigen stammen von den Webseiten der Anbieter.

Recherchiert wurde für Wien und NÖ. basemap.at, das BEV-DGM und OpenStreetMap decken aber
**ganz Österreich** ab, deshalb gilt die Spalte „Niederösterreich“ für alle Bundesländer außer Wien
(getestet in Tirol, Innsbruck-Hungerburg).

## Übersicht und Empfehlung

| Daten | Wien | Niederösterreich |
|---|---|---|
| **Orthofoto** | Stadt Wien WMTS `lb` (Orthofoto 2025, bis 15 cm) | basemap.at WMTS `bmaporthofoto30cm` (29 cm, stellenweise 15 cm) |
| **Höhenlinien** | Stadt Wien WFS `HOEHENLINIEOGD` (fertig, 1 m Abstand) | selbst rechnen aus BEV ALS-DGM 1 m |
| **Geländemodell (DGM)** | BEV ALS-DGM 1 m (für Schummerung, 2,5-m-Linien) | BEV ALS-DGM 1 m |
| **Koordinatensystem der Karte** | EPSG:31256 (GK M34) | EPSG:31256 östlich, EPSG:31255 (GK M31) westlich von 14°50′ Ost |

Alle Quellen sind kostenlos und unter CC BY 4.0 nutzbar. Die Namensnennung gehört in die Karte bzw. ins Impressum (siehe unten).

---

## Orthofoto

### Wien: Stadt Wien, Orthofoto 2025

- **WMTS (geprüft):** Capabilities `https://mapsneu.wien.gv.at/wmtsneu/1.0.0/WMTSCapabilities.xml`
  - Kachel-URL: `https://mapsneu.wien.gv.at/wmts/lb/farbe/google3857/{z}/{row}/{col}.jpeg`
  - Layer `lb` = aktuelles Orthofoto (2025), ältere Jahrgänge als `lb2024` … `lb2014`, historische Luftbildpläne `lb1938` … `lb1992`.
  - Zoomstufen bis 21 (am Stadion geprüft). Kachelsystem Web-Mercator EPSG:3857, daher muss das Bild auf das Koordinatensystem der Karte umprojiziert werden.
  - Pixelgröße in Wien (48,2° N): Zoom 19 ≈ 0,20 m, Zoom 20 ≈ 0,10 m, Zoom 21 ≈ 0,05 m.
  - **Zoom 21 bringt kaum echte Details (geprüft):** Gegenüber der hochskalierten Zoom-20-Kachel
    weicht Zoom 21 im Mittel nur um 4,0 Grauwerte ab, Zoom 20 gegenüber Zoom 19 um 9,7.
    Zoom 21 ist also großteils hochgerechnet, bei vierfacher Datenmenge. **Wir nehmen höchstens Zoom 20 (10 cm).**
    Seit 2026-11-15 richtet sich die Zoomstufe nach dem Maßstab (0,025 mm pro Pixel auf dem Papier,
    project.md Entscheidung 20): Zoom 20 bei 1:4 000, Zoom 19 auf 25 cm verkleinert bei 1:10 000 usw.
  - **Abdeckung (geprüft):** Das Orthofoto reicht etwa 1–2 km über die Stadtgrenze hinaus
    (echte Bilder in Klosterneuburg, Schwechat und Perchtoldsdorf, nicht mehr in Mödling).
    Außerhalb antwortet der Server mit 404. Halbleere Randkacheln gab es im Test nicht.
    Das Programm nimmt deshalb das Wiener Orthofoto, wenn alle Kacheln vorhanden sind, sonst basemap.at.
  - Mit einer wiederverwendeten Verbindung (keep-alive) kommen ca. 30–60 Kacheln/s. Mit einer
    neuen Verbindung je Kachel waren es nur ca. 4/s, und der Server brach nach einigen hundert Kacheln ab.
- **Alternative: Kacheln als JPG-Download** aus dem Geodatenviewer der Stadtvermessung
  (`https://www.wien.gv.at/ma41datenviewer/public/start.aspx`): 2,5 × 2,5 km, 15 cm, EPSG:31256, ca. 40 MB je Kachel,
  so wie das Test-Orthofoto `36_3_op_2025.jpg`. Die Download-Links erscheinen nur im Viewer, deshalb ist die Automatisierung schwieriger als beim WMTS.
- Befliegung 2025: 20. März und 30. April 2025 (also vor dem Laubaustrieb), jährliche Aktualisierung, True-Orthofoto.
  Quelle: <https://www.wien.gv.at/stadtplanung/orthofoto-produktinformation>
- Lizenz CC BY 4.0, Namensnennung „Datenquelle: Stadt Wien – data.wien.gv.at“.

### Niederösterreich (und ganz Österreich): basemap.at

- **WMTS (geprüft):** Capabilities `https://mapsneu.wien.gv.at/basemapneu/1.0.0/WMTSCapabilities.xml`
  - Kachel-URL: `https://mapsneu.wien.gv.at/basemap/bmaporthofoto30cm/normal/google3857/{z}/{row}/{col}.jpeg`
  - Auflösung 29 cm flächendeckend, 15 cm in einzelnen Regionen. Zoom 19 gibt es überall,
    Zoom 20 nur in manchen Gebieten. Geprüft: Zoom 20 in Wien vorhanden, in Melk, Gmünd und Hollabrunn nicht,
    in Waidhofen/Ybbs auch nicht (2026-11-15). 10 cm gibt es damit verlässlich nur im Wiener Orthofoto,
    sonst meist 20 cm (Zoom 19).
  - Das Flugjahr ist je Region verschieden. Es steht als Wasserzeichen in den Kacheln ab Zoom 17 und im Datensatz
    „Erfassungsstände“: <https://www.data.gv.at/datasets/8795c23b-4db6-4a01-97a2-617adbe750a2?locale=de>
  - Lizenz CC BY 4.0, Namensnennung „Datenquelle: basemap.at“ mit Link auf <https://basemap.at/>.
  - Download-Limits nennt basemap.at nicht. Wir laden trotzdem nur den benötigten Bereich, speichern die Kacheln zwischen und laden sie nicht mehrfach.
- **Land NÖ selbst:** Der WMS `https://geo.noe.gv.at/geoserver/ows` enthält nur INSPIRE-Themen
  (Schutzgebiete, Flächenwidmung …), kein Orthofoto (geprüft). Auf
  <https://www.noe.gv.at/noe/Karten-Geoinformationen/DownloadGeodatenKarten.html> gibt es nur
  Blattschnitt-Übersichten (`bs_faof.zip`). Die Orthofotos selbst bietet der kostenpflichtige NÖ Geoshop an. Für uns ist deshalb basemap.at die Quelle.

---

## Höhenlinien

### Wien: Stadt Wien, Schichtenlinien 1 m

- **WFS (geprüft):** `https://data.wien.gv.at/daten/geo?service=WFS&version=1.1.0&request=GetFeature&typeName=ogdwien:HOEHENLINIEOGD&srsName=EPSG:31256&outputFormat=json&bbox=<xmin>,<ymin>,<xmax>,<ymax>,EPSG:31256`
  - Ausschnitt 1 × 1 km am Stadion: 238 Linien, 1 MB GeoJSON, in Sekunden geladen.
  - Attribute: `HOEHE_ADRIA` (Höhe über Adria), `HOEHE_WIEN` (über Wiener Null), `LAYER` = `ISO_1` / `ISO_5` / `ISO_100`
    (normale Linie / jede 5. / jede 100.).
  - **Die Linien liegen auf ganzen Metern über Wiener Null**, also auf …,68 m über Adria (Wiener Null = 156,68 m ü. A.).
    Für die Karte ist das unerheblich, die Zählkurven liegen dann eben auf „runden“ Wiener-Null-Höhen.
  - Die Linien sind an den Grenzen des 2,5-km-Kachelrasters geschnitten und müssen vor dem Import wieder zusammengefügt werden.
  - Mit 1 m Abstand lassen sich 1-, 2- und 5-m-Linien direkt auswählen. **2,5 m geht nicht**, dafür muss aus dem DGM gerechnet werden.
  - Kein Mengenlimit erkennbar: 10 × 10 km = 23 008 Linien (geprüft). Das Programm vergleicht
    trotzdem `totalFeatures` mit der Anzahl gelieferter Linien.
  - Stadtgrenze als Polygon: Layer `ogdwien:LANDESGRENZEOGD`. Damit prüft das Programm, ob der Bereich ganz in Wien liegt.
  - **Höhenvergleich mit dem BEV-DGM (geprüft, 3852 Punkte am Stadion):** Das BEV liegt im Median
    0,53 m tiefer als `HOEHE_ADRIA` (Höhensystem EVRF2000 statt Adria), die Streuung beträgt ±0,46 m.
    Die beiden Quellen passen also zusammen.
- Ganzer Datensatz auch als SHP/GeoPackage auf data.gv.at. Ebenfalls CC BY 4.0, „Datenquelle: Stadt Wien – data.wien.gv.at“.

### Niederösterreich: kein brauchbarer fertiger Datensatz

- **Land NÖ:** Kein freier Download von Höhenlinien oder DGM gefunden. Nur der NÖ Geoshop
  (<https://geoshop.noel.gv.at/>, Login nötig, Preise unbekannt) und die Anzeige im NÖ Atlas.
- **BEV Höhenschichtlinien** (<https://www.bev.gv.at/Services/Produkte/Digitales-Gelaendehoehenmodell/Hoehenschichtlinien.html>):
  5 m Abstand, aus dem alten photogrammetrischen Geländemodell abgeleitet, seit 2020 nicht mehr aktualisiert,
  mittlerer Fehler im Wald ±10 m. Nur als Gesamtdatei für Österreich (10 GB). **Für OL-Karten zu ungenau.**
- → Genau der Fall „schlechte fertige Höhenlinien“: **In NÖ rechnen wir die Linien selbst aus dem BEV ALS-DGM.**

---

## Geländemodell: BEV ALS-DGM 1 m (ganz Österreich)

- Produktseite: <https://www.bev.gv.at/Services/Produkte/Digitales-Gelaendehoehenmodell/ALS-Hoehenraster.html>
- **Download (geprüft):** `https://data.bev.gv.at/download/ALS/DTM/<Stichtag>/ALS_DTM_CRS3035RES50000mN<N>E<E>.tif`
  - Neuester Stichtag: `20250915`. Ältere: `20240915`, `20230915`, `20220915`.
  - `<N>`, `<E>` = linke untere Ecke der 50-km-Kachel in EPSG:3035, z. B. Stadion (E 4 797 783, N 2 808 865)
    → `N2800000E4750000`. Formel: Koordinate auf volle 50 000 m abrunden.
  - Kachelübersicht: <https://data.bev.gv.at/download/ALS/ALS_Kacheluebersicht.pdf>
  - Eine Kachel hat 5 bis 11 GB, aber sie ist ein **Cloud Optimized GeoTIFF** (512er-Blöcke, LZW, Übersichten).
    Mit GDAL/rasterio lässt sich ein Ausschnitt direkt per Teil-Download lesen: **1 km² in ca. 5 s** (geprüft), ohne die ganze Datei zu laden.
  - Rasterweite 1 m, float32, NoData −9999, Lage EPSG:3035 (ETRS89 LAEA), Höhe EVRF2000 (EPSG:9274).
  - Höhengenauigkeit ±0,5 m. Fortführung abschnittsweise, Daten bis zu 10 Jahre alt.
  - Verzeichnislisten sind gesperrt (403), die Dateinamen müssen also wie oben berechnet werden.
- Lizenz CC BY 4.0 (laut Metadaten), Namensnennung z. B. „Datenquelle: BEV – Bundesamt für Eich- und Vermessungswesen“.
- Wird an Kachelgrenzen gelegen, müssen zwei bis vier Kacheln gelesen und zusammengesetzt werden.

---

## Koordinatensystem der Karte

**Befund:** Die Quellen geben das Koordinatensystem nicht vor. BEV-DGM (EPSG:3035) und
basemap.at bzw. Stadt-Wien-WMTS (EPSG:3857) müssen ohnehin umprojiziert werden. Nur die Wiener
Höhenlinien liegen schon in EPSG:31256 vor. Das Land NÖ verwendet intern einheitlich BMN M34
(EPSG:31259). Das ist dieselbe Projektion wie GK M34 (EPSG:31256), nur mit 750 km verschobenem Rechtswert.

**Wie groß ist der Unterschied?** Die Verzerrung ist bei allen Varianten für eine OL-Karte vernachlässigbar:

| Variante | Maßstabsfehler in NÖ (max.) | Auf 1 km |
|---|---|---|
| GK, passender Streifen (≤ 1,5° vom Mittelmeridian) | 0,015 % | 15 cm |
| GK M34 auch im Westen von NÖ (bis 1,9°, Westgrenze ca. 14°27′) | 0,024 % | 24 cm |
| UTM 33N | −0,04 % | 40 cm |

Zum Vergleich: Bei 1:4000 entsprechen 0,1 mm auf dem Papier 40 cm im Gelände. Die Meridiankonvergenz
(bis ca. 1,1° im passenden Streifen, 1,4° mit M34 im Westen NÖ) verschwindet nicht durch die Streifenwahl, sondern wird über die Grivation in der `.omap` korrekt berücksichtigt.

**Empfehlung (deckt sich mit deinem Vorschlag):** Gauß-Krüger-Streifen **nach der Kartenmitte** wählen:

| Kartenmitte | EPSG | Streifen |
|---|---|---|
| östlich von 14°50′ (ganz Wien, größter Teil NÖ) | 31256 | MGI / Austria GK East (M34) |
| westlich von 14°50′ (westliches Wald- und Mostviertel) | 31255 | MGI / Austria GK Central (M31) |
| westlich von 11°50′ (Tirol, Vorarlberg) | 31254 | MGI / Austria GK West (M28) |

Begründung: Das ist das in Österreich übliche System, OOM kennt es, die Wiener Daten passen direkt ohne
Umrechnung, und es ist geometrisch die genaueste Variante. Eine Karte, die über die Streifengrenze reicht,
bekommt einfach den Streifen ihrer Mitte. Der kleine Zusatzfehler dabei ist laut Tabelle bedeutungslos.

---

## OpenStreetMap

- **Overpass** (`https://overpass-api.de/api/interpreter`): der vorgesehene Dienst für reine
  Lesezugriffe. Abfrage aller Knoten, Wege und Multipolygone mit einem der 15 Hauptschlüssel aus
  den OOM-Tabellen (`highway`, `building`, `landuse`, `natural` …), Ausgabe mit Geometrie (`out geom`).
- **Am 2026-11-02 war Overpass zeitweise gestört** (502/504, auch die Statusseite und andere
  öffentliche Overpass-Server). Deshalb gibt es einen Ersatzweg über die **OSM-API**
  (`https://api.openstreetmap.org/api/0.6/map.json?bbox=…`): 1 km² in 2 s, ca. 3 MB.
  Die API liefert vollständige Wege, aber angeschnittene Flächen-Relationen (z. B. ein großer Wald)
  ohne ihre äußeren Teile. Diese lädt das Programm mit `/relation/<id>/full.json` nach.
  Bei zu vielen Knoten (Limit 50 000) teilt das Programm den Bereich in Viertel.
  Die API ist eigentlich fürs Editieren gedacht, deshalb nur als Ersatz und nur für kleine Bereiche.
  **Auf der öffentlichen Website (Cloud) gibt es diesen Ersatzweg nicht** (`OLPREP_OSM_API_ERSATZ=0`):
  Ist Overpass gestört, endet der Auftrag mit einer verständlichen Meldung.
- **User-Agent** aller Downloads (seit 2026-11-15): `OL-Karten-prep/0.1 (+https://github.com/retofritze/OL-Karten-prep)`,
  wie es Overpass und OSM für automatische Zugriffe verlangen (Kontakt über das öffentliche Repository).
- Rohdaten bleiben im Ergebnisordner unter `daten/osm.json`.
- Lizenz ODbL, Namensnennung „© OpenStreetMap-Mitwirkende“.

## Namensnennung (für jede erzeugte Karte)

Das Programm schreibt die Quellen in `QUELLEN.txt` im Ergebnisordner und in die Kartennotizen
(`<notes>`) der `.omap`. Text seit 2026-11-16 nach Vorgabe des Benutzers (Code:
`ausgabe/kartenordner.py`, `QUELLEN`). Es erscheinen nur die tatsächlich verwendeten Quellen:

| Quelle | Eintrag unter „Datenquellen:“ | Zeile, die auf der Karte stehen muss |
|---|---|---|
| Orthofoto basemap.at | Orthofoto: basemap.at (CC BY 4.0; basemap.at; Lizenz-Link) | Datenquelle: basemap.at |
| Orthofoto Wien | Orthofoto: Stadt Wien (CC BY 4.0; data.wien.gv.at; Lizenz-Link) | Datenquelle: Stadt Wien - data.wien.gv.at |
| BEV-Geländemodell (immer, wegen der Schummerung) | Geländemodell (Höhenlinien und Schummerung bzw. nur Schummerung daraus gerechnet): Bundesamt für Eich- und Vermessungswesen (CC BY 4.0; https://www.bev.gv.at/public.html; Lizenz-Link) | Datenquelle: bev.gv.at/public.html |
| Höhenlinien Wien | Höhenlinien in Wien: Stadt Wien (CC BY 4.0; data.wien.gv.at; Lizenz-Link) | Datenquelle: Stadt Wien - data.wien.gv.at |
| OpenStreetMap | Schon vorplatzierte Symbole: OpenStreetMap (ODbL; openstreetmap.org; ODbL-Link) | Datenquelle: openstreetmap.org / OpenStreetMap-Mitwirkende |

Reihenfolge der Kartenzeilen: basemap.at, OpenStreetMap, BEV, Stadt Wien (die Wien-Zeile nur,
wenn Wiener Daten verwendet wurden, und nur einmal). Schlusszeile: „Keine Gewähr auf rechtliche
Angaben!“. Der erste Absatz (Angaben zur Karte) schreibt alle Abkürzungen aus.

## Offen

- Flugjahre von basemap.at je Region aus dem data.gv.at-Datensatz auslesen und in der Karte vermerken.
- ~~Passen Wiener Höhenlinien und BEV-DGM zusammen?~~ Ja, geprüft (siehe oben, 0,53 m Höhensystem-Unterschied).
- ~~Rechenaufwand für eigene Höhenlinien~~ Unkritisch: 1 km² DGM in ca. 5 s, Höhenlinien in Sekunden.
