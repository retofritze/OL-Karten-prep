"""Layer rule (project.md, decision 17): dependencies point in one direction only.

    auftrag -> verarbeitung, ausgabe -> quellen -> (nothing)
    ressourcen may be used by every layer; ausgabe must not import verarbeitung
    (a TYPE_CHECKING import for type hints is allowed).
"""

import ast
from pathlib import Path

import pytest

PACKAGE = Path(__file__).resolve().parents[1] / "src" / "olprep"
FORBIDDEN = {
    "quellen": {"verarbeitung", "ausgabe", "auftrag"},
    "verarbeitung": {"ausgabe", "auftrag"},
    "ausgabe": {"verarbeitung", "quellen", "auftrag"},
}


def runtime_imports(path: Path) -> set[str]:
    """First package part below olprep of every import, except inside `if TYPE_CHECKING:`."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    type_only = {id(n) for node in ast.walk(tree)
                 if isinstance(node, ast.If) and getattr(node.test, "id", None) == "TYPE_CHECKING"
                 for n in ast.walk(node)}
    found = set()
    for node in ast.walk(tree):
        if id(node) in type_only:
            continue
        if isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module and node.module.startswith("olprep."):
                found.add(node.module.split(".")[1])
            elif node.level == 2 and node.module:       # from ..x import y
                found.add(node.module.split(".")[0])
            elif node.level == 2:                       # from .. import x
                found.update(a.name for a in node.names)
        elif isinstance(node, ast.Import):
            found.update(a.name.split(".")[1] for a in node.names if a.name.startswith("olprep."))
    return found


@pytest.mark.parametrize("layer", sorted(FORBIDDEN))
def test_layer_dependencies(layer):
    for path in sorted((PACKAGE / layer).glob("*.py")):
        bad = runtime_imports(path) & FORBIDDEN[layer]
        assert not bad, f"{layer}/{path.name} importiert {sorted(bad)}"


def test_rule_detects_violation(tmp_path):
    bad = tmp_path / "quellen" / "x.py"
    bad.parent.mkdir()
    bad.write_text("from ..verarbeitung.georef import Georeferencing\n", encoding="utf-8")
    assert "verarbeitung" in runtime_imports(bad)
