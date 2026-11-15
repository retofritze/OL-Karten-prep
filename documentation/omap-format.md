# Das .omap-Dateiformat (OpenOrienteering Mapper 0.9.6)

Stand 2026-11-02 (Grundlagen 2026-10-29, ergänzt um Tags, mehrteilige Pfade und Vorlagen-Sichtbarkeit). Grundlagen:

- `data/Leeres Course_Design_10000.omap` (leere Karte aus OOM)
- `data/referenz_georef.omap` (in OOM georeferenziert, mit Orthofoto-Vorlage und 3 Objekten)
- `data/test_stadion_roundtrip.omap` (unsere erzeugte Testdatei, in OOM geöffnet und gespeichert)
- Symbolsätze und Beispiele der OOM-Installation
- OOM-Quellcode v0.9.6 (GitHub `OpenOrienteering/mapper`: `src/core/georeferencing.cpp`,
  `src/fileformats/xml_file_format.cpp`)

**Status: Schreiben funktioniert.** Die erzeugte Testdatei öffnet sich in OOM ohne
Warnung, Orthofoto und Objekte liegen deckungsgleich.

## Grundlagen

- Reines **XML**, UTF-8, Namespace `http://openorienteering.org/apps/mapper/xml/v2`, `version="9"`.
- Eine "leere" Karte ist trotzdem ~260–380 kB groß, weil der **komplette Symbolsatz**
  (Farben + Symboldefinitionen) in der Datei steckt.

## Aufbau

```xml
<map xmlns="..." version="9">
  <notes/>
  <georeferencing .../>          <!-- Maßstab, CRS, Deklination, Grivation -->
  <colors count="N">...</colors>  <!-- Farben inkl. Druckreihenfolge (priority) -->
  <barrier version="6" required="0.6.0">
    <symbols count="N" id="ISOM 2017-2">...</symbols>
    <parts><part name="..."><objects count="N">...</objects></part></parts>
    <templates ...>...</templates>   <!-- Vorlagen: Orthofoto, DGM-Ableitungen ... -->
    <view>...</view>                  <!-- Zoom, Raster, Sichtbarkeit -->
  </barrier>
  <barrier version="6" required="0.6.0">  <!-- optional: Undo/Redo-Historie -->
    <undo>...</undo><redo/>
  </barrier>
</map>
```

## Georeferenzierung

So schreiben wir sie (EPSG:31256, Wien):

```xml
<georeferencing scale="10000" grid_scale_factor="1.000005" auxiliary_scale_factor="1"
                declination="5.38" grivation="5.32">
  <projected_crs id="EPSG">
    <spec language="PROJ.4">+init=epsg:31256</spec>
    <parameter>31256</parameter>
    <ref_point x="6601.4" y="340984.2"/>        <!-- Projektionskoordinate (m) -->
  </projected_crs>
  <geographic_crs id="Geographic coordinates">
    <spec language="PROJ.4">+proj=latlong +datum=WGS84</spec>
    <ref_point_deg lat="..." lon="..."/>
  </geographic_crs>
</georeferencing>
```

- Ein `<ref_point x y>` direkt unter `<georeferencing>` wäre der Referenzpunkt auf
  dem Papier (mm). Fehlt er, liegt der Referenzpunkt bei Papier (0, 0). Wir lassen ihn weg.
- Leere Karte ohne Georeferenz: `<projected_crs id="Local"/>`.
- `declination` = magnetische Deklination (Ost positiv), `grivation` = Deklination −
  Meridiankonvergenz. OOM lässt Attribute weg, die 0 bzw. 1 sind.
- Die Drehung nach magnetisch Nord steckt **nur hier**. Objekte liegen in
  Papierkoordinaten, deren "oben" bereits magnetisch Nord ist. Umrechnung
  Projektion → Papier: siehe `Georeferencing.to_paper` in `src/olprep/verarbeitung/georef.py`.

### Konsistenzprüfung beim Laden (Warnung "Inkonsistente Deklination/Nadelabweichung")

OOM berechnet beim Laden die Meridiankonvergenz neu und prüft
`declination == round(grivation + Konvergenz, 2)`. Bei Abweichung korrigiert es die
Deklination und warnt. OOM rechnet die Konvergenz **nicht analytisch**, sondern
mit einem Näherungsverfahren (`Georeferencing::updateGridCompensation`): lokale
stereografische WGS84-Projektion um den Referenzpunkt, je 1 km Basislinie Ost-West
und Süd-Nord, in die Ziel-Projektion abgebildet. Am Stadion ergibt das 0,0629°
statt analytisch 0,0650°. Bei 2 Nachkommastellen reicht das für einen Unterschied von 0,01°.

→ `olprep.georef.oom_grid_compensation` bildet das Verfahren 1:1 nach. Grivation und
Deklination werden in derselben Reihenfolge gerundet wie in OOM. Der Grid-Faktor
stimmt damit ebenfalls mit OOM überein (1,000005).

### Koordinatensysteme Österreich

| EPSG | Name | Einsatz |
|---|---|---|
| 31256 | MGI / Austria GK East (M34) | Wien (Orthofotos der Stadt Wien), östliches Österreich |
| 31255 | MGI / Austria GK Central (M31) | Mitte, z. B. westliches NÖ (Grenze M31/M34 bei 14°50' Ost) |
| 31254 | MGI / Austria GK West (M28) | Westen, z. B. Tirol (Grenze M28/M31 bei 11°50' Ost) |
| 31259 | MGI / Austria M34 (BMN) | Landesdaten NÖ (wie 31256, Rechtswert + 750 km) |
| 31287 | MGI / Austria Lambert | österreichweite Datensätze |
| 25833 | ETRS89 / UTM 33N | österreichweite/neuere Datensätze |
| 3035 | ETRS89 / LAEA Europe | BEV ALS-DGM 1 m |
| 3857 | Web-Mercator | Kacheldienste (basemap.at, Stadt Wien WMTS) |

Welches System die Karte bekommt, regelt Entscheidung 7 in [project.md](project.md)
(GK-Streifen nach Kartenmitte), Begründung in [datenquellen.md](datenquellen.md).

## Objekte

```xml
<object type="1" symbol="0">
  <coords count="5">-18059 21768;21768 18059;18059 -21768;-21768 -18059;-18059 21768 18;</coords>
  <pattern rotation="0"><coord x="0" y="0"/></pattern>
</object>
<object type="0" symbol="102"><coords count="1">39043 47263;</coords></object>
```

- `type`: 0 = Punkt, 1 = Pfad (Linie oder Fläche, je nach Symbol), 4 = Text (noch nicht verwendet).
- `symbol`: Index (`id`) des Symbols im `<symbols>`-Block, **nicht** der ISOM-Code.
  Die IDs sind **dateispezifisch** und müssen immer über das Attribut `code`
  nachgeschlagen werden. Beispiel ISOM 2017-2, Code → id:

  | Code | Symbol | OOM-Symbolsatz (191 Symbole) | `referenz_georef.omap` (169 Symbole) |
  |---|---|---|---|
  | 101 | Höhenlinie | 0 | 0 |
  | 102 | Zählkurve | 2 | 2 |
  | 401 | Offenes Land | 79 | 74 |
  | 418 | Markanter Busch/Baum | 109 | 103 |
  | 521 | Gebäude | 146 | 139 |
- Koordinaten in **1/1000 mm auf dem Papier**, x nach rechts, y nach unten.
  Bei 1:10000 entspricht 1 m im Gelände 100 Einheiten.
- Drittes Zahlenfeld = Punkt-Flags (Bitmaske), bestätigt:
  `1` = Kurvenstart (Bézier, die nächsten 2 Punkte sind Kontrollpunkte),
  `2` = Pfad geschlossen, `16` = Ende eines Teilpfads, `32` = Strichelpunkt.
  Geschlossener Pfad: letzter Punkt = erster Punkt mit Flag `18` (= 16 + 2).
- Die Symbolsatz-Dateien von OOM enthalten ~35 **Beispielobjekte**, die wir beim Erzeugen entfernen.
- **Auch Symbole enthalten `<object>`-Elemente**: Punktsymbole (und ein Logo-Symbol mit dem
  Schriftzug „OpenOrienteering“) bestehen intern aus kleinen Objekten um (0, 0). Wer
  Kartenobjekte auslesen will, darf nur `parts/part/objects/object` lesen, nicht alle `object`.
- **Symboltypen** (`<symbol type>`): 1 Punkt, 2 Linie, 4 Fläche, 8 Text, 16 kombiniert
  (z. B. Gebäude in ISSprOM = Fläche + Umrandung, kann Linie oder Fläche tragen).
- **Mehrteilige Pfade** (Fläche mit Löchern): Teile hintereinander in einem `<coords>`, jeder
  Teil endet mit Flag `16`, geschlossene Teile wiederholen ihren ersten Punkt mit Flag `18`.
  Der erste Teil ist der Außenrand.
- **Objekt-Tags** (von uns für OSM-Tags genutzt, in OOM bestätigt 2026-11-02, deutsch „Anmerkungseditor“):
  `<object …><tags><t k="building">yes</t><t k="osm_id">way/123</t></tags><coords …>`.

## Vorlagen (Templates)

So schreiben wir ein georeferenziertes Bild (JPG + `.jgw` oder GeoTIFF):

```xml
<templates count="1" first_front_template="1">
  <template type="TemplateImage" open="true" name="36_3_op_2025.jpg"
            path="C:/.../output/test_stadion/templates/36_3_op_2025.jpg"
            relpath="templates/36_3_op_2025.jpg" georef="true">
    <crs_spec>+init=epsg:31256</crs_spec>
  </template>
  <defaults use_meters_per_pixel="true" meters_per_pixel="0" dpi="0" scale="0"/>
</templates>
```

- `relpath` ist relativ zum Ordner der `.omap`. OOM findet die Datei auch nach
  Verschieben des ganzen Ordners (getestet). → Der Ergebnisordner ist portabel.
- `georef="true"` + `<crs_spec>` (ohne `language`-Attribut, so speichert es OOM):
  OOM liest die Lage selbst aus dem World-File bzw. GeoTIFF. Eine
  Transformationsmatrix ist nicht nötig.
- Alternativ (so in `referenz_georef.omap`): `georef` fehlt, stattdessen
  `<transformations>` mit expliziten Matrizen Pixel ↔ Papier. Das brauchen wir nicht.
- `first_front_template="1"` bedeutet: Vorlage 0 liegt *unter* der Karte.
- Die Sichtbarkeit pro Vorlage steht in `<view><map_view><templates><ref template="0" visible="true" opacity="1"/>`.
  Wir schreiben die Schummerung mit `visible="false"`, damit sie das Orthofoto nicht verdeckt.
  In OOM schaltet man sie in der Vorlagenliste ein.
- Unsere Kartenordner legen alle Vorlagen in `daten/` ab (`relpath="daten/orthofoto.jpg"`).

## Mit OOM ausgelieferte, wiederverwendbare Dateien

Unter `C:\Program Files\OpenOrienteering Mapper 0.9.6\symbol sets\`:

| Datei | Nutzen |
|---|---|
| `4000\ISSprOM 2019_4000.omap` | Vorlage Sprintkarte |
| `10000\ISOM 2017-2_10000.omap`, `15000\ISOM 2017-2_15000.omap` | Vorlage Waldkarte |
| `OSM-ISOM 2017-2.crt`, `OSM-ISSprOM 2019.crt`, `OSM-ISSkiOM 2019.crt` | **Zuordnung OSM-Tags → OL-Symbolcode** (Textformat, GPL), von `verarbeitung/osm.py` gelesen. Je Zeile `<Code> <Abfrage>` mit `=`, `!=`, `~=` (enthält), `AND`, `OR`, Klammern. Bei mehreren Treffern gilt die letzte Zeile. Eigene Änderung: Wald 406 → 405 (`RULE_CHANGES`). |
| `ISOM 2017-2-ISSprOM 2019.crt` | Zuordnung zwischen den Symbolsätzen |

`Course_Design_*` ist der Symbolsatz für **Bahnlegung** (nur 6 Farben, Posten,
Startdreieck …), nicht fürs Kartenzeichnen. Für unsere Karten nehmen wir ISSprOM/ISOM.

## Umsetzung im Code

Seit 2026-11-15 in Schichten (project.md, Entscheidung 17), alle Pfade unter `src/olprep/`:

- `ressourcen.py`: Ort der OOM-Symbolsätze und `.crt`-Tabellen, Symbolsätze mit ihren Maßstäben.
- `verarbeitung/georef.py`: Deklination (WMM über `pygeomag`), OOM-kompatible
  Konvergenz und Grid-Faktor, Umrechnung Projektion/WGS84 → Papier.
- `ausgabe/omap.py`: `OmapDocument` lädt einen OOM-Symbolsatz, entfernt die
  Beispielobjekte, setzt Georeferenzierung, Objekte (über ISOM-Code) und
  georeferenzierte Bild-Vorlagen und speichert.
- `quellen/orthofoto.py`: Orthofoto aus Kacheldiensten, ins Karten-Koordinatensystem umgerechnet,
  Auflösung nach Maßstab (0,025 mm pro Pixel, beim Verkleinern gemittelt; project.md Entscheidung 20).
- `ausgabe/bilder.py`: Bild als JPG + `.jgw`. GDAL nennt die Lagedatei eines JPG `.wld`, wir
  benennen sie in `.jgw` um (in OOM bestätigte Form) und schreiben keine `.aux.xml`.
- `quellen/gelaende.py` (BEV-DGM), `quellen/wien.py` (Wiener WFS) und
  `verarbeitung/hoehenlinien.py`: Höhenlinien (101) und Zählkurven (102).
- `quellen/osm.py` (Download) und `verarbeitung/osm.py`: OSM-Daten über die `.crt`-Tabellen
  zuordnen, als Punkte, Linien oder Flächen (mit Löchern und Tags) schreiben.
- `verarbeitung/schummerung.py`: Schummerung als graues Bild (zweite Vorlage, ausgeblendet).
- `auftrag.py` + `scripts/make_map.py`: kompletter Kartenordner aus Bereich und Maßstab
  (Einstellungen prüfen, Fortschritt melden); `ausgabe/kartenordner.py`: `QUELLEN.txt`-Text und ZIP.
- `scripts/make_testfile.py`: erzeugt `output/test_stadion/` (Testkarte am Stadion).
- Kartennotizen: `<notes>` direkt unter `<map>`. Darin schreiben wir die Quellenangaben
  (in OOM unter *Karte → Kartennotizen* sichtbar).

Vorgehen bei Formatfragen: **Round-Trip-Test**. Datei erzeugen → in OOM öffnen →
unverändert speichern → vergleichen. Was OOM ändert, zeigt, wo die Datei vom erwarteten Format abweicht.

## Offen / zu beachten

- ~~Datumstransformation MGI ↔ WGS84~~ geklärt 2026-11-02: Standard „MGI to WGS 84 (3)“
  für Orthofoto und OSM gleichermaßen, siehe Entscheidung 11 in [project.md](project.md).
  OOM selbst rechnet unsere Objekte nicht um, sie liegen schon in Papierkoordinaten vor.
- Textobjekte (`type="4"`) und mehrere Kartenteile (`<part>`) sind noch nicht untersucht.
- Warum die Referenzdatei weniger Symbole hat (169 statt 191) ist ungeklärt.
  Vermutlich hat OOM beim Anlegen bzw. Speichern einen anderen Stand des Symbolsatzes
  verwendet. Für uns egal, solange wir über `code` nachschlagen.
