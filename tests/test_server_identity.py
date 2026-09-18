"""Spec 2026-07-28 #3002: die `serverInfo`-Identitaet, die jede Antwort traegt.

Die moderne Aera stempelt `serverInfo` nicht einmal beim Handshake, sondern in
das `_meta` *jedes* Resultats. Was dort steht, entscheidet allein der
`MCPServer`-Konstruktor — das SDK setzt nichts nach:

    An unversioned server reports an empty `version`; the SDK never
    substitutes its own.   (mcp/server/lowlevel/server.py)

Vor dieser Datei trug jede moderne Antwort dieses Servers

    {"name": "swiss_statistics_mcp", "version": ""}

waehrend `server.json` `description` und `websiteUrl` seit jeher fuehrt. Das
war keine Luecke zwischen Server und Spec, sondern eine Drift zwischen dem
Manifest und dem Draht — und genau die Sorte, die niemandem auffaellt, weil
beide Seiten fuer sich gruen aussehen.

Gemessen, nicht zurueckgelesen: die Zusicherungen haengen an dem, was eine
echte Verbindung zurueckbekommt, nicht an den Konstruktor-Argumenten. Ein Blick
auf `mcp.title` waere auch dann gruen, wenn das Argument auf dem Weg zum Draht
verlorenginge — das ist derselbe Fehler wie eine Fixture, die die Annahme des
Autors kodiert.
"""

from __future__ import annotations

import ast
import pathlib
from importlib.metadata import metadata as _dist_metadata
from importlib.metadata import version as _installed_version

from mcp import Client
from mcp.server.mcpserver import MCPServer

from swiss_statistics_mcp.server import CKAN_USER_AGENT, mcp

DIST = "swiss-statistics-mcp"


async def test_die_moderne_aera_traegt_die_version() -> None:
    """Der lasttragende Fall: leer war hier eine falsche Angabe, keine fehlende."""
    async with Client(mcp) as client:
        info = client.server_info

    assert info is not None, "kein serverInfo — die moderne Aera stempelt es immer"
    assert info.version, (
        "serverInfo.version ist leer. Das SDK setzt nichts nach; die Nummer muss "
        "als `version=` in den MCPServer-Konstruktor."
    )
    assert info.version == _installed_version("swiss-statistics-mcp")


async def test_die_identitaet_kommt_aus_den_paket_metadaten() -> None:
    """Nicht bloss «ist gesetzt», sondern «kommt aus der einen Quelle».

    Ohne den Vergleich waere der Test auch mit einem Literal in `server.py`
    gruen — und genau das Literal ist der Anfang der Drift: es steht dann als
    dritte Fassung neben `pyproject.toml` und `server.json`, und niemand
    fuehrt es nach, weil es nirgends sichtbar ist.
    """
    dist = _dist_metadata(DIST)
    homepage = next(
        url.strip()
        for label, _, url in (e.partition(", ") for e in dist.get_all("Project-URL") or [])
        if label.strip() == "Homepage"
    )

    async with Client(mcp) as client:
        info = client.server_info

    assert info is not None
    assert info.name == "swiss_statistics_mcp"
    assert info.description == dist["Summary"]
    assert info.website_url == homepage
    assert info.title == "Swiss Statistics (BFS STAT-TAB)", (
        "der Anzeigename ist bewusst ein Literal — er steht in keiner Paket-Metadate"
    )


async def test_kein_feld_der_identitaet_ist_leer() -> None:
    """Der Fehler, gegen den dieses Modul geschrieben ist, als Regel statt als
    Einzelfall.

    Nachgemessen: `Implementation.website_url` ist `str | None` ohne
    URL-Pruefung, und der Stempel wird mit `exclude_none` gedumpt. `None` laesst
    das Feld also weg, `""` schickt `"websiteUrl": ""` an jeden Aufrufer — die
    gleiche falsche Angabe, die die leere `version` war. Ein leeres Feld ist
    schlechter als ein fehlendes, weil es Anwesenheit behauptet.
    """
    async with Client(mcp) as client:
        info = client.server_info

    assert info is not None
    leer = sorted(
        name
        for name in ("name", "title", "version", "description", "website_url")
        if getattr(info, name) == ""
    )
    assert not leer, f"leer statt abwesend: {leer}"


async def test_auch_die_handshake_aera_nennt_die_identitaet() -> None:
    """Die Aera, die heutige Clients sprechen — hier kommt `serverInfo` aus dem
    `initialize`-Ergebnis statt aus dem Pro-Antwort-Stempel. Beide speisen sich
    aus demselben Konstruktor; dass sie es tun, steht hier gemessen."""
    async with Client(mcp, mode="legacy") as client:
        info = client.server_info

    assert info is not None
    assert info.version == _installed_version("swiss-statistics-mcp")
    assert info.title == "Swiss Statistics (BFS STAT-TAB)"


async def test_ein_server_ohne_identitaet_bleibt_leer() -> None:
    """Negativkontrolle, gleiches SDK, gleicher Client.

    Ohne sie waeren die Tests oben auch an dem Tag gruen, an dem das SDK
    anfinge, eine Version selbst einzusetzen — und wuerden dann nicht mehr
    pruefen, dass *wir* sie setzen. Faellt dieser Test, ist die Aussage des
    Moduls neu zu bewerten, nicht eine Zahl nachzuziehen.
    """
    async with Client(MCPServer("kontrolle")) as client:
        info = client.server_info

    assert info is not None
    assert info.version == ""
    assert info.title is None
    assert info.website_url is None


def test_user_agent_und_serverinfo_teilen_eine_quelle() -> None:
    """Zwei `importlib.metadata`-Aufrufe nebeneinander sind keine Redundanz,
    sondern zwei Wahrheiten: sie koennen sich nur unterscheiden, nie ergaenzen.
    Vorher hatten sie sogar verschiedene Fallbacks (`0.0.0` vs `0.0.0+source`).
    """
    installed = _installed_version("swiss-statistics-mcp")
    assert CKAN_USER_AGENT == f"swiss-statistics-mcp/{installed}"


def test_kein_metadaten_fallback_setzt_einen_leerstring() -> None:
    """Der Zweig, den kein Testlauf normal erreicht: der uninstallierte Baum.

    In `__init__.py` greift dort je ein `except PackageNotFoundError`. Was es
    einsetzt, entscheidet, was ein Aufrufer sieht — und `""` waere genau die
    Angabe, gegen die dieses Modul geschrieben ist, bloss an der Stelle, an der
    niemand hinsieht. Beim Schreiben stand dort einmal `""`; aufgefallen ist es
    nicht im Testlauf, sondern beim Nachmessen des Stempels.

    Statisch geprueft, und das ist Absicht. Den Zweig auszufuehren hiesse,
    `importlib.metadata` prozessweit umzubiegen und das Paket neu zu laden —
    ein Patch am Fremdmodul, der die Mechanik fuer alles andere im selben
    Prozess mit entschaerft. Ein Reload allein reicht nicht: er fuehrt das
    `from importlib.metadata import ...` erneut aus und holt sich das Original
    zurueck. Die schwaechere Form also, benannt statt verschwiegen — sie faengt
    dafuer jeden kuenftigen Fallback mit, nicht nur die drei von heute.

    `0.0.0+source` ist die begruendete Ausnahme: ein fehlendes `version`-Feld
    saehe nach einem Server ohne Identitaet aus, das lokale Segment sagt
    stattdessen, dass hier aus einem Quellbaum gefahren wird.
    """
    quelle = (
        pathlib.Path(__file__).resolve().parents[1] / "src" / "swiss_statistics_mcp" / "__init__.py"
    )
    baum = ast.parse(quelle.read_text(encoding="utf-8"))

    zuweisungen: list[tuple[str, object]] = []
    for knoten in ast.walk(baum):
        if not isinstance(knoten, ast.ExceptHandler):
            continue
        for stmt in ast.walk(knoten):
            if isinstance(stmt, ast.Assign | ast.AnnAssign) and isinstance(
                stmt.value, ast.Constant
            ):
                ziele = stmt.targets if isinstance(stmt, ast.Assign) else [stmt.target]
                for ziel in ziele:
                    if isinstance(ziel, ast.Name):
                        zuweisungen.append((ziel.id, stmt.value.value))

    assert zuweisungen, "keine Fallback-Zuweisung gefunden — hat sich der Aufbau geaendert?"

    leer = sorted(name for name, wert in zuweisungen if wert == "")
    assert not leer, (
        f"Fallback setzt einen Leerstring statt None: {leer}. Der Stempel wird "
        'mit `exclude_none` gedumpt — `""` kommt als leeres Feld beim Aufrufer '
        "an, `None` laesst es weg."
    )
