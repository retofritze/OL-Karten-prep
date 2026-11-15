"""Erzeugt eine Test-.omap (ISOM 2017-2, 1:10000, EPSG:31256) rund ums Ernst-Happel-Stadion.

Prüfpunkte beim Öffnen in OOM:
- Orthofoto liegt als Vorlage unter der Karte (relativer Pfad templates/...).
- Kreis (Höhenlinie, r = 140 m) umschließt das Stadion, Baum-Symbol in der Mitte.
- Quadrat (Zählkurve, 400 m, nach Gitternord ausgerichtet) ist gegenüber dem
  Blattrand um die Grivation (~5,3°) gedreht, ebenso das Orthofoto.
"""

import math
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from olprep.ressourcen import symbol_set_file  # noqa: E402
from olprep.verarbeitung.georef import Georeferencing  # noqa: E402
from olprep.ausgabe.omap import OmapDocument  # noqa: E402

EPSG = 31256
SCALE = 10000
STADION_EN = (6601.4, 340984.2)   # Spielfeldmitte, im Orthofoto gemessen (EPSG:31256)
ORTHO = ROOT / "data" / "Orthofoto_Wien_Stadion" / "36_3_op_2025.jpg"
OUT_DIR = ROOT / "output" / "test_stadion"


def main() -> None:
    e0, n0 = STADION_EN
    g = Georeferencing.create(EPSG, SCALE, e0, n0)
    print(f"Referenzpunkt {e0:.1f} / {n0:.1f}, Deklination {g.declination}°, "
          f"Grivation {g.grivation}°, Grid-Faktor {g.grid_scale_factor}")

    doc = OmapDocument(symbol_set_file("ISOM 2017-2", SCALE))
    doc.set_georeferencing(g)

    doc.add_point("418", g.to_paper(e0, n0))
    circle = [g.to_paper(e0 + 140 * math.cos(a), n0 + 140 * math.sin(a))
              for a in (math.radians(d) for d in range(0, 360, 10))]
    doc.add_line("101", circle, closed=True)
    square = [g.to_paper(e0 + dx, n0 + dy) for dx, dy in
              ((-200, -200), (200, -200), (200, 200), (-200, 200))]
    doc.add_line("102", square, closed=True)
    doc.add_area("401", [g.to_paper(e0 + dx, n0 + dy) for dx, dy in
                         ((220, -60), (320, -60), (320, 60), (220, 60))])

    template_dir = OUT_DIR / "templates"
    template_dir.mkdir(parents=True, exist_ok=True)
    if ORTHO.exists():
        for src in (ORTHO, ORTHO.with_suffix(".jgw")):
            dst = template_dir / src.name
            if not dst.exists():
                shutil.copy2(src, dst)
        doc.add_georeferenced_image(template_dir / ORTHO.name, OUT_DIR)
    else:
        # The orthophoto is not in the repository (too large); see documentation/datenquellen.md.
        print(f"Hinweis: {ORTHO.relative_to(ROOT)} fehlt, Karte ohne Orthofoto-Vorlage.")

    out = OUT_DIR / "test_stadion.omap"
    doc.save(out)
    print(f"geschrieben: {out}")


if __name__ == "__main__":
    main()
