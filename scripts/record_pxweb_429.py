#!/usr/bin/env python3
"""Zeichnet eine echte HTTP-429-Antwort von STAT-TAB auf — absichtlich, von Hand.

    python scripts/record_pxweb_429.py

ACHTUNG: DIESES SKRIPT UEBERSCHREITET DAS LIMIT DER QUELLE MIT ABSICHT. Es
sendet dieselbe Metadaten-Anfrage, bis STAT-TAB mit 429 antwortet, und hoert
dann sofort auf. Deshalb steht es nicht in `record_fixtures.py`, das bei jedem
Neu-Aufzeichnen alles abruft. Selten laufen lassen, nie in einer Schleife.

WARUM. Am 2.11.2026 wies STAT-TAB den Live-Lauf mit 429 ab, und jeder dieser
Aufrufe dauerte 9,4 bis 10,0 s. Das passt dazu, dass `_retry_wait` einen
`Retry-After` ab 4 s auf `RETRY_WAIT_MAX` kappt — oder zu langsamen
429-Antworten ohne Header. Welches von beiden, sagte das Log nicht, und die
Unit-Tests pruefen `Retry-After` nur mit erfundenen Werten. Eine Entscheidung
ueber die Kappung braucht die echte Antwort.

WAS AUFGEZEICHNET WIRD (`tests/fixtures/pxweb_429.json`):

- das deklarierte Limit (`?config`) zum Zeitpunkt der Aufnahme;
- dieselbe Anfrage zweimal beantwortet: einmal 200, einmal 429 — Status,
  Kopfzeilen und beim 429 der Koerper. Eine Aufzeichnung nur des Fehlschlags
  koennte nicht zeigen, dass dieselbe Anfrage sonst gelingt;
- der Verlauf danach: zuerst die Versuche, die der Server heute machen wuerde
  (Wartezeit aus `_retry_wait` ohne Zufall), dann Versuche im Abstand des
  zuletzt genannten `Retry-After` (ohne Header: das deklarierte Zeitfenster),
  bis wieder 200 kommt oder `RECOVERY_LIMIT` Sekunden vergangen sind.

Cookies werden geschwaerzt (Name bleibt, Wert nicht): Sie sind Sitzungskennungen
des Aufnahmeclients und keine Eigenschaft der Quelle.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx

PXWEB = "https://www.pxweb.bfs.admin.ch/api/v1"
# Dieselbe Tabelle wie `pxweb_metadata.json`: Der 200er dort und hier stammen
# aus derselben Anfrage.
PX_TABLE = "de/px-x-0102020000_101/px-x-0102020000_101.px"
URL = f"{PXWEB}/{PX_TABLE}"
CONFIG_URL = f"{PXWEB}/de/?config"

FIXTURE = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "pxweb_429.json"

CONCURRENCY = 4  # nacheinander allein kommt eine Antwortzeit nicht unter das Limit
BURST_LIMIT = 150  # Obergrenze, falls nie ein 429 kommt — dann ist DAS der Befund
RECOVERY_LIMIT = 300.0  # Sekunden nach dem ersten 429, danach wird aufgegeben
SERVER_ATTEMPTS = 3  # RETRY_MAX_ATTEMPTS: der erste 429 zaehlt als Versuch 1

try:
    import swiss_statistics_mcp.server as srv
except Exception as exc:  # pragma: no cover
    raise SystemExit(f"Paket nicht importierbar ({exc}); `pip install -e .` zuerst") from exc


def _headers(resp: httpx.Response) -> list[list[str]]:
    out = []
    for name, value in resp.headers.multi_items():
        if name.lower() == "set-cookie":
            cookie_name = value.split("=", 1)[0]
            attrs = value.split(";", 1)[1] if ";" in value else ""
            value = (
                f"{cookie_name}=<geschwaerzt>;{attrs}" if attrs else f"{cookie_name}=<geschwaerzt>"
            )
        out.append([name, value])
    return out


def _retry_after(resp: httpx.Response) -> float | None:
    """Was der Server aus dieser Antwort lesen wuerde — mit seiner eigenen Funktion."""
    return srv._parse_retry_after(httpx.HTTPStatusError("", request=resp.request, response=resp))


def _server_wait(attempt: int, resp: httpx.Response) -> float:
    """`_retry_wait` ohne Zufall: die Untergrenze seiner Spanne.

    Mit `Retry-After` ist das der Wert selbst (gekappt), ohne die exponentielle
    Kurve mit Jitter-Faktor 1.0.
    """
    hinted = _retry_after(resp)
    if hinted is not None:
        return min(hinted, srv.RETRY_WAIT_MAX)
    return min(srv.RETRY_WAIT_INITIAL * 2 ** (attempt - 1), srv.RETRY_WAIT_MAX)


async def record() -> int:
    recorded_at = datetime.now(UTC)
    async with httpx.AsyncClient(timeout=60.0) as c:
        cfg = (await c.get(CONFIG_URL)).json()
        print(f"deklariertes Limit: {cfg}")

        # 1) Burst bis zum ersten 429.
        t0 = time.monotonic()
        sent = 0
        statuses: list[int] = []
        ok: httpx.Response | None = None
        throttled: httpx.Response | None = None
        t_429 = 0.0
        stop = asyncio.Event()

        async def worker() -> None:
            nonlocal sent, ok, throttled, t_429
            while not stop.is_set() and sent < BURST_LIMIT:
                sent += 1
                r = await c.get(URL)
                statuses.append(r.status_code)
                if r.status_code == 200 and ok is None:
                    ok = r
                elif r.status_code == 429 and throttled is None:
                    throttled, t_429 = r, time.monotonic()
                    stop.set()
                elif r.status_code not in (200, 429):
                    print(f"unerwarteter Status {r.status_code}: {r.text[:200]}", file=sys.stderr)
                    stop.set()

        await asyncio.gather(*(worker() for _ in range(CONCURRENCY)))
        if throttled is None or ok is None:
            print(
                f"kein 429 nach {sent} Anfragen in {time.monotonic() - t0:.1f} s "
                f"(Status: {sorted(set(statuses))}) — nichts geschrieben",
                file=sys.stderr,
            )
            return 1
        before = statuses.index(429)
        print(f"429 nach {before} erfolgreichen Anfragen, {t_429 - t0:.1f} s; {sent} gesendet")

        # 2) Was der Server heute taete: weitere Versuche nach `_retry_wait`.
        recovery: list[dict] = []
        last = throttled

        async def probe(phase: str) -> httpx.Response:
            r = await c.get(URL)
            after = round(time.monotonic() - t_429, 2)
            recovery.append(
                {
                    "phase": phase,
                    "after_s": after,
                    "status": r.status_code,
                    "retry_after": r.headers.get("retry-after"),
                }
            )
            print(
                f"  +{after:6.2f} s  {phase:<16} {r.status_code}  Retry-After={r.headers.get('retry-after')}"
            )
            return r

        for attempt in range(1, SERVER_ATTEMPTS):
            await asyncio.sleep(_server_wait(attempt, last))
            last = await probe("server_retry")
            if last.status_code != 429:
                break

        # 3) Dem Header folgen, bis die Quelle wieder antwortet.
        while last.status_code == 429 and time.monotonic() - t_429 < RECOVERY_LIMIT:
            wait = _retry_after(last)
            if wait is None:
                wait = float(cfg.get("timeWindow", 15))
            # Mindestens 1 s (ein `Retry-After: 0` waere sonst eine Schleife ohne
            # Pause gegen eine Quelle, die gerade sperrt), hoechstens bis zum Ende.
            remaining = RECOVERY_LIMIT - (time.monotonic() - t_429)
            await asyncio.sleep(min(max(wait, 1.0), max(remaining, 0.0)))
            last = await probe("honour_header")

    ok_body = ok.content
    doc = {
        "_provenance": {
            "recorded_at": recorded_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "script": "scripts/record_pxweb_429.py",
            "url": URL,
            "declared_limit": cfg,
            "burst": {
                "concurrency": CONCURRENCY,
                "sent": sent,
                "ok_before_first_429": before,
                "seconds_to_first_429": round(t_429 - t0, 2),
            },
            "note": (
                "Aufgenommen hinter einem HTTPS-Proxy der Aufnahmeumgebung; die "
                "Kopfzeilen sind die, die beim Client ankamen. Cookies geschwaerzt."
            ),
        },
        "ok": {
            "status": ok.status_code,
            "headers": _headers(ok),
            "body_bytes": len(ok_body),
            "body_sha256": hashlib.sha256(ok_body).hexdigest(),
        },
        "throttled": {
            "status": throttled.status_code,
            "headers": _headers(throttled),
            "body": throttled.text,
        },
        "recovery": recovery,
    }
    FIXTURE.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"geschrieben: {FIXTURE}")
    return 0 if last.status_code == 200 else 2


if __name__ == "__main__":
    raise SystemExit(asyncio.run(record()))
