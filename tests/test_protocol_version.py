"""ARCH-012: die beiden Spec-Revisionen, gegen die dieser Server geprueft ist.

Das SDK bietet keinen setzbaren Pin — die Aushandlung liegt in der
Session-Schicht, weder `MCPServer.__init__` noch `Settings` nimmt den Parameter
entgegen. Ein Pin ist hier deshalb eine erklaerte Konstante plus eine
Zusicherung, die bricht, sobald ein SDK-Bump sie verschiebt. Bewusst CI-seitig
und nicht zur Laufzeit: brechen soll unser Build, nicht der Betrieb von
jemandem, der `mcp` weiter oben aktualisiert hat.

`mcp` 2.x bedient ZWEI Protokoll-Aeren ueber denselben Server; die erste
Anfrage einer Verbindung entscheidet, welche gilt:

* die **Legacy-Aera** mit `initialize`-Handshake — was heutige Clients
  sprechen. Sie deckelt bei `LATEST_HANDSHAKE_VERSION`.
* die **Modern-Aera** mit Pro-Request-Envelope, die `LATEST_MODERN_VERSION`
  erreicht.

**`LATEST_PROTOCOL_VERSION` ist ein Alias auf die MODERNE Version.** Wer nur
dagegen pinnt — die naheliegende Einzelzeile — sichert die Aera, in der heute
praktisch niemand spricht, und laesst die andere frei wandern. Beide stehen
deshalb getrennt hier.

Nachgemessen statt aus Konstantennamen geschlossen: die Aushandlung steht in
`mcp/server/runner.py::_negotiate_initialize` und lautet

    negotiated = requested if requested in HANDSHAKE_PROTOCOL_VERSIONS
                 else LATEST_HANDSHAKE_VERSION

— sie haengt an keinem Transport, gilt also fuer stdio ebenso wie fuer HTTP.

Der gemessene Teil ist nachgeliefert. Der Satz, der hier stand — dieses Repo
baue keine ASGI-App, durch die sich eine Anfrage schicken liesse, die
Zusicherungen haengen deshalb an den SDK-Konstanten — war eine Annahme, keine
Messung: `MCPServer.streamable_http_app()` gibt die App her, und
`tests/test_modern_wire.py` faehrt sie. Unten steht zusaetzlich die
ausgehandelte Revision beider Aeren, an einer echten Verbindung abgelesen statt
aus Konstantennamen geschlossen.

Die Konstanten-Zusicherungen bleiben trotzdem stehen, und zwar nicht aus
Bequemlichkeit: eine gemessene Verbindung sagt, welche Revision *heute*
ausgehandelt wurde. Sie kann nicht sagen, dass ein SDK-Bump die Obergrenze
verschoben hat, denn sie wuerde dann stillschweigend die neue messen. Genau das
faengt der Konstanten-Pin ab. Die beiden Formen pruefen Verschiedenes; keine
ersetzt die andere.
"""

from __future__ import annotations

import pathlib
import re

from mcp import Client
from mcp.types.version import (
    LATEST_HANDSHAKE_VERSION,
    LATEST_MODERN_VERSION,
    LATEST_PROTOCOL_VERSION,
)

from swiss_statistics_mcp.server import mcp

REPO = pathlib.Path(__file__).resolve().parents[1]

# Die Revisionen, die die READMEs nennen. Sie stehen hier und nicht im `src/`:
# das SDK bestimmt sie, der Server setzt sie nicht. Eine Konstante im
# Auslieferungspfad waere eine zweite Wahrheit, die driften kann — genau so kam
# `bag-epl-mcp` dazu, Aufrufern `2025-06-18` zu melden.
DOCUMENTED_HANDSHAKE_VERSION = "2025-11-25"
DOCUMENTED_MODERN_VERSION = "2026-07-28"

# Datei und Ueberschrift, unter der die beiden Revisionen dokumentiert stehen.
README_SECTIONS = (
    ("README.md", "## MCP Protocol Version"),
    ("README.de.md", "## MCP-Protokollversion"),
)


def test_die_handshake_aera_steht_wo_die_readme_sie_nennt() -> None:
    """Die Aera, die bestehende Clients sprechen — der lasttragende Pin."""
    assert LATEST_HANDSHAKE_VERSION == DOCUMENTED_HANDSHAKE_VERSION, (
        f"das SDK deckelt den Handshake jetzt bei {LATEST_HANDSHAKE_VERSION}, "
        f"die READMEs sagen {DOCUMENTED_HANDSHAKE_VERSION}. Nicht blind "
        "nachziehen: erst das Spec-Changelog zwischen den beiden Revisionen "
        "lesen, dann README.md, README.de.md und CHANGELOG.md zusammen mit "
        "dieser Konstante bewegen."
    )


def test_die_moderne_aera_steht_wo_die_readme_sie_nennt() -> None:
    assert LATEST_MODERN_VERSION == DOCUMENTED_MODERN_VERSION, (
        f"das SDK erreicht modern jetzt {LATEST_MODERN_VERSION}, die READMEs "
        f"sagen {DOCUMENTED_MODERN_VERSION}"
    )


def test_latest_protocol_version_ist_der_alias_auf_die_moderne_aera() -> None:
    """Die Falle, gegen die dieses Repo abgesichert wird, benannt.

    Ohne diese Zeile liest sich der naheliegende Einzeiler
    `PIN == LATEST_PROTOCOL_VERSION` wie eine vollstaendige Zusicherung. Sie
    ist es nicht, und man sieht es dem Namen nicht an. Faellt dieser Test, hat
    das SDK die Bedeutung des Alias geaendert — dann ist die Aufteilung oben
    neu zu bewerten, nicht nur eine Zahl.
    """
    assert LATEST_PROTOCOL_VERSION == LATEST_MODERN_VERSION
    assert LATEST_PROTOCOL_VERSION != LATEST_HANDSHAKE_VERSION


def test_die_beiden_aeren_sind_verschieden() -> None:
    """Sagt, wann die Aufteilung oben wieder verschwinden darf.

    Faellt das SDK die Aeren eines Tages auf eine Revision zusammen, ist die
    doppelte Zusicherung redundant und gehoert zurueckgebaut. Dieser Test ist
    die Stelle, an der das auffaellt.
    """
    assert LATEST_MODERN_VERSION > LATEST_HANDSHAKE_VERSION


def test_der_pin_ist_eine_datierte_revision_kein_bewegliches_ziel() -> None:
    """«latest» oder eine Spanne wuerde den Zweck des Pins aufheben."""
    for value in (DOCUMENTED_HANDSHAKE_VERSION, DOCUMENTED_MODERN_VERSION):
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", value), value


def test_beide_readmes_nennen_dieselben_beiden_revisionen() -> None:
    """Ein Pin, den die Doku anders angibt, ist kein Pin.

    Jede Sprache einzeln geprueft: im Portfolio sind EN und DE desselben Repos
    schon dreimal auseinandergelaufen, weil nur eine Fassung nachgezogen wurde
    und niemand die andere daneben gelegt hat.
    """
    for name, anchor in README_SECTIONS:
        text = (REPO / name).read_text(encoding="utf-8")
        parts = text.split(anchor, 1)
        assert len(parts) > 1, f"{name} hat keinen Abschnitt «{anchor}»"
        body = parts[1][:2500]
        for value in (DOCUMENTED_HANDSHAKE_VERSION, DOCUMENTED_MODERN_VERSION):
            assert value in body, f"{name} nennt {value} nicht im Abschnitt «{anchor}»"


async def test_eine_echte_verbindung_landet_auf_der_modernen_aera() -> None:
    """Gemessen statt geschlossen: `mode="auto"` probt `server/discover`.

    Das ist die Zusicherung, die der Konstanten-Pin nicht geben kann — er sagt,
    was das SDK *koennte*, nicht, worauf dieser Server eine Verbindung
    tatsaechlich fuehrt.
    """
    async with Client(mcp) as client:
        assert client.protocol_version == DOCUMENTED_MODERN_VERSION


async def test_eine_legacy_verbindung_landet_auf_der_handshake_aera() -> None:
    """Die Aera, die heutige Clients sprechen — ebenfalls abgelesen.

    Zusammen mit dem Test darueber steht damit gemessen, was die Tabelle in
    beiden READMEs behauptet: derselbe Server, zwei Aeren, die erste Anfrage
    entscheidet.
    """
    async with Client(mcp, mode="legacy") as client:
        assert client.protocol_version == DOCUMENTED_HANDSHAKE_VERSION
