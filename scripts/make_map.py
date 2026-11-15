"""Erzeugt einen Kartenordner (output/<name>/) mit .omap, Orthofoto und Höhenlinien,
dazu output/<name>.zip zum Weitergeben.

Beispiel (Ernst-Happel-Stadion, Sprint):
    .\\.venv\\Scripts\\python.exe scripts\\make_map.py stadion --bbox 16.415 48.203 16.427 48.211 --scale 4000

--bbox:          West Süd Ost Nord in Grad (WGS84), z. B. aus einer Webkarte abgelesen.
--symbolsatz:    Standard ISSprOM 2019 bei 1:4000, sonst ISOM 2017-2.
--aequidistanz:  Abstand der Höhenlinien in m, Standard 2,5 (Sprint) bzw. 5.
--zaehlkurve:    Abstand der Zählkurven in m, Standard 5 × Äquidistanz.
--kein-osm:      ohne OpenStreetMap-Objekte (Gebäude, Wege, Zäune …).
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from olprep.auftrag import Auftrag, Eingabefehler, ausfuehren  # noqa: E402
from olprep.ressourcen import SCALES, SYMBOL_SETS  # noqa: E402


def show_progress(schritt: str, prozent: int) -> None:
    print(f"[{prozent:3d} %] {schritt}")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("name", help="Kartenname = Ordner- und Dateiname")
    p.add_argument("--bbox", nargs=4, type=float, required=True, metavar=("W", "S", "O", "N"))
    p.add_argument("--scale", type=int, default=4000, choices=SCALES)
    p.add_argument("--symbolsatz", choices=list(SYMBOL_SETS))
    p.add_argument("--aequidistanz", type=float)
    p.add_argument("--zaehlkurve", type=float)
    p.add_argument("--kein-osm", action="store_true", help="keine OpenStreetMap-Objekte importieren")
    p.add_argument("--out", type=Path, default=ROOT / "output")
    a = p.parse_args()
    auftrag = Auftrag(a.name, tuple(a.bbox), a.scale, a.symbolsatz, a.aequidistanz, a.zaehlkurve,
                      osm=not a.kein_osm)
    try:
        auftrag = auftrag.geprueft()
    except Eingabefehler as e:
        p.error(str(e))
    ergebnis = ausfuehren(auftrag, a.out, melde=show_progress)
    print(f"ZIP: {ergebnis.zip}")


if __name__ == "__main__":
    main()
