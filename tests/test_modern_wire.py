"""Die moderne Aera (Spec `2026-07-28`) an der Drahtform gemessen.

Die READMEs trugen bis hierher den Satz, dieser Server baue «keine ASGI-App,
durch die sich ein `initialize` schicken liesse», das Gate haenge deshalb an den
SDK-Konstanten — die schwaechere Form, benannt statt verschwiegen. Der Satz war
eine Annahme, keine Messung: `MCPServer.streamable_http_app()` gibt genau diese
App her, und unten faehrt sie.

Warum das nicht schon `tests/test_cache_hints.py` erledigt: der In-Process-
`Client` dispatcht ueber ein `DirectDispatcher`-Paar — «no streams, no JSON-RPC
framing, no initialize handshake» (`mcp/client/client.py`). Er prueft die
Handler, aber nie den HTTP-Eingang. Das Era-Routing ist dort aber
**header-basiert** (`streamable_http_manager.py`: `MCP-Protocol-Version` ausser
den Handshake-Revisionen geht an den modernen Eingang), und die
Envelope-Pflicht steht im Klassifizierer dahinter. Beides erreicht nur eine
echte Anfrage.

Drei Dinge, die diese Datei beim Schreiben gekostet haben und die deshalb
hier stehen, statt noch einmal gesucht zu werden:

* **Die App braucht ihren ASGI-Lifespan.** Ohne ihn ist die Task-Gruppe des
  Session-Managers nicht initialisiert und jede Anfrage endet in einem
  `RuntimeError` — der nicht nach «Lifespan fehlt» aussieht.
* **Der Host muss `127.0.0.1` sein.** Gegen `http://test` antwortet das SDK mit
  **421 Misdirected Request**; das ist kein Testfehler, sondern der aktive
  DNS-Rebinding-Schutz. Ein Test, der den 421 fuer kaputte Verdrahtung haelt,
  entschaerft ihn.
* **Der Envelope-Schluessel heisst `protocolVersion`, nicht `protocol-version`.**
  Mit dem falschen Namen faellt die Anfrage aus dem modernen Routing heraus und
  bekommt «Missing session ID» — eine Meldung aus der *Legacy*-Haelfte, die
  ueber die moderne Aera nichts aussagt.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest

from swiss_statistics_mcp.server import LIST_CACHE_TTL_MS, mcp

PROTOCOL_VERSION = "2026-07-28"
SERVER_INFO_KEY = "io.modelcontextprotocol/serverInfo"

# Loopback, nicht `test`: siehe Modul-Docstring (421 statt Testfehler).
BASE_URL = "http://127.0.0.1:8000"


@contextlib.asynccontextmanager
async def _running_app(app: Any) -> AsyncIterator[httpx.AsyncClient]:
    """Die ASGI-App mit gefahrenem Lifespan, als HTTP-Client."""
    to_app: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    from_app: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

    async def receive() -> dict[str, Any]:
        return await to_app.get()

    async def send(message: dict[str, Any]) -> None:
        await from_app.put(message)

    task = asyncio.create_task(app({"type": "lifespan", "asgi": {"version": "3.0"}}, receive, send))
    await to_app.put({"type": "lifespan.startup"})
    started = await asyncio.wait_for(from_app.get(), 10)
    assert started["type"] == "lifespan.startup.complete", started

    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url=BASE_URL, timeout=30) as client:
            yield client
    finally:
        await to_app.put({"type": "lifespan.shutdown"})
        with contextlib.suppress(Exception):
            await asyncio.wait_for(from_app.get(), 10)
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await task


async def _post(
    client: httpx.AsyncClient,
    method: str,
    *,
    meta: dict[str, Any] | None = None,
    header_version: str = PROTOCOL_VERSION,
) -> httpx.Response:
    envelope: dict[str, Any] = {
        "io.modelcontextprotocol/protocolVersion": PROTOCOL_VERSION,
        "io.modelcontextprotocol/clientCapabilities": {},
        "io.modelcontextprotocol/clientInfo": {"name": "wire-test", "version": "0"},
    }
    if meta is not None:
        envelope = meta
    return await client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": 1, "method": method, "params": {"_meta": envelope}},
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": header_version,
            "MCP-Method": method,
        },
    )


@pytest.fixture
async def wire() -> AsyncIterator[httpx.AsyncClient]:
    async with _running_app(mcp.streamable_http_app()) as client:
        yield client


async def test_discover_antwortet_auf_der_modernen_aera(wire: httpx.AsyncClient) -> None:
    """`server/discover` ist die Entdeckungsmethode der modernen Aera."""
    response = await _post(wire, "server/discover")

    assert response.status_code == 200, response.text
    result = response.json()["result"]
    assert result["supportedVersions"] == [PROTOCOL_VERSION]
    assert result["instructions"], "ohne Instructions findet ein Modell den Einstieg nicht"


async def test_jede_antwort_traegt_die_serverinfo_identitaet(wire: httpx.AsyncClient) -> None:
    """Spec #3002 — und der Grund, warum eine leere Version hier teuer ist:
    sie wiederholt sich in *jeder* Antwort, nicht einmal pro Verbindung."""
    for method in ("server/discover", "tools/list"):
        response = await _post(wire, method)
        assert response.status_code == 200, response.text

        info = response.json()["result"]["_meta"][SERVER_INFO_KEY]
        assert info["name"] == "swiss_statistics_mcp"
        assert info["version"], f"{method} stempelt eine leere Version"
        assert info["title"]
        assert info["websiteUrl"]


async def test_jedes_resultat_nennt_seinen_resulttype(wire: httpx.AsyncClient) -> None:
    """`Result.resultType` ist ab `2026-07-28` Pflicht; die Bruecke
    «abwesend heisst vollstaendig» gilt nur fuer Clients aelterer Server."""
    for method in ("server/discover", "tools/list"):
        result = (await _post(wire, method)).json()["result"]
        assert result["resultType"] == "complete", method


async def test_die_werkzeugliste_traegt_ihren_frischehinweis(wire: httpx.AsyncClient) -> None:
    """SEP-2549 auf dem Draht statt im Konstruktor-Dict."""
    result = (await _post(wire, "tools/list")).json()["result"]

    assert result["ttlMs"] == LIST_CACHE_TTL_MS
    assert result["cacheScope"] == "public"
    assert len(result["tools"]) == 15


async def test_jedes_werkzeug_nennt_sein_ausgabeschema(wire: httpx.AsyncClient) -> None:
    """Strukturierte Ausgabe ist das, was ein Modell ohne Raten weiterverarbeitet."""
    tools = (await _post(wire, "tools/list")).json()["result"]["tools"]

    ohne = sorted(t["name"] for t in tools if not t.get("outputSchema"))
    assert not ohne, f"ohne outputSchema: {ohne}"


async def test_ein_halber_envelope_wird_benannt_abgewiesen(wire: httpx.AsyncClient) -> None:
    """Gegenprobe zum Routing: die Anfrage erreicht den modernen Klassifizierer
    und bekommt dessen INVALID_PARAMS — nicht die Legacy-Antwort «Missing
    session ID», die ueber die moderne Aera nichts aussagt."""
    response = await _post(
        wire,
        "tools/list",
        meta={"io.modelcontextprotocol/protocolVersion": PROTOCOL_VERSION},
    )

    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == -32602
    assert "clientCapabilities" in error["message"]


async def test_der_host_header_schutz_ist_scharf() -> None:
    """Kein Nebenschauplatz: derselbe Schutz macht den 421 oben zur Messung.

    Ohne diese Zusicherung liest sich die `127.0.0.1`-Zeile in `BASE_URL` wie
    eine Marotte, und wer sie spaeter auf einen beliebigen Host lockert, merkt
    nicht, dass er den Schutz mit abschaltet.
    """
    async with _running_app(mcp.streamable_http_app()) as client:
        response = await client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
            headers={"Host": "angreifer.example", "Content-Type": "application/json"},
        )

    assert response.status_code == 421
