# OL-Karten-prep – Arbeitsregeln für Claude

Projekt: Vorbereitung von Orientierungslauf-Karten für OpenOrienteering Mapper (OOM).
Stand, Entscheidungen und Planung: `documentation/project.md`.

## Sprache

Antworten und alle Dateien in `documentation/` auf Deutsch. Code-Kommentare und Docstrings bleiben Englisch.

## Lab Notebook

Nach **jeder** Antwortrunde ohne Nachfrage einen neuen Abschnitt an `documentation/unterhaltung.md` anhängen:

```
## N · JJJJ-MM-TT · Titel

### Prompt

> Prompt des Benutzers wörtlich als Zitat

### Ergebnis

Nur die Abschlussantwort, keine Zwischenschritte.
```

`project.md`, `datenquellen.md` und `omap-format.md` bei Änderungen mitpflegen.

## Öffentliches Repository

Das GitHub-Repository ist öffentlich (seit 2026-11-15). In Dateien, die ins Repository kommen,
also auch im Lab Notebook: keine lokalen Pfade mit Benutzernamen (`C:\Users\<Benutzer>\…`
schreiben), keine Namen, E-Mail-Adressen oder Zugangsdaten. Office-Dateien (`*.pptx`, `*.docx`)
sind in `.gitignore`, weil ihre Metadaten den Autor enthalten.

## Cloud (Firebase / Cloud Run)

- Online unter <https://ol-karten-prep.web.app> (Aufbau: `project.md` → „Betrieb in der Cloud“).
- **Firebase Hosting veröffentlicht den Ordner `documentation/`** (ohne `*.md` und Office-Dateien).
  Dort keine Dateien ablegen, die nicht öffentlich sein sollen.
- Neue Version: Tests, Commit, dann `powershell -ExecutionPolicy Bypass -File deploy\hochladen.ps1`.
  Nur die Projektübersicht geändert: `firebase deploy --only hosting`.

## Testkarten und OOM

Der Benutzer prüft die erzeugten Karten laufend in OOM. **Bevor ein Kartenordner unter `output/` gelöscht oder neu erzeugt wird**, prüfen, ob OOM die Karte geöffnet hat:

```powershell
Get-Process | Where-Object ProcessName -match "Mapper" | Select-Object MainWindowTitle
```

Steht der Dateiname im Fenstertitel (ein `*` bedeutet: ungespeicherte Änderungen), erst nachfragen.

## Tests

- Schnelle Tests (ohne Internet, ca. 10 s) nach jeder Codeänderung: `.\.venv\Scripts\python.exe -m pytest`
- Referenzkarten-Test mit Internet (ca. 1 min) **nur nach einem größeren Umbauschritt** (Vorgabe des
  Benutzers): `.\.venv\Scripts\python.exe -m pytest -m netz`

## Umgebung

- Windows, PowerShell, Python 3.12 in `.venv` (je Rechner bzw. Speicherort neu anlegen, siehe `project.md` → Wiedereinstieg).
- OOM 0.9.6 unter `C:\Program Files\OpenOrienteering Mapper 0.9.6` (Symbolsätze, `.crt`-Tabellen).
