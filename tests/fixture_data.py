"""Zugriff auf die aufgezeichneten Fixtures unter ``tests/fixtures/``.

Herkunft, Datum, Auswahlregel und SHA-256 stehen je Datei in
``tests/fixtures/PROVENANCE.md``, geschrieben von ``scripts/record_fixtures.py``.

Ein fehlender Name ist ein Fehler und keine leere Zeichenkette: Der
Rueckfallwert eines Lookups waere sonst die ganze Ursache — ein Test gegen eine
leere Fixture prueft nichts und meldet Erfolg.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def fixture_text(name: str) -> str:
    path = FIXTURES / name
    if not path.is_file():
        available = sorted(p.name for p in FIXTURES.iterdir() if p.is_file())
        raise FileNotFoundError(
            f"Keine Fixture {name!r} unter {FIXTURES}. Vorhanden: {available}. "
            "Neu aufzeichnen mit `python scripts/record_fixtures.py`."
        )
    return path.read_text(encoding="utf-8")


def fixture_json(name: str) -> Any:
    return json.loads(fixture_text(name))
