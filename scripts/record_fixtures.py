#!/usr/bin/env python3
"""Zeichnet die Unit-Test-Fixtures von den echten Quellen auf.

    python scripts/record_fixtures.py

WARUM ES DIESES SKRIPT GIBT. Ein handgeschriebener Mock kodiert die Annahme
seines Autors und kann sie deshalb prinzipiell nicht widerlegen: Produktivcode
und Fixture stammen aus demselben Kopf, derselben Stunde, derselben Lektuere der
Doku. Wo beide irren, irren beide gleich, und die Suite bleibt gruen.

Dieses Repo spricht vier Quellen an, und die Fixtures dafuer standen bisher als
Literale im Testmodul — ohne Herkunft und ohne Datum. Ohne Datum ist
«aufgezeichnet» nach zwei Jahren von «ausgedacht» nicht mehr zu unterscheiden,
weil die Datei gleich aussieht.

**Es sind Ausschnitte, keine Vollabzuege.** Der AGVCH-Snapshot fuehrt 2280
Zeilen, das HSSO-Kapitel 215 KB Markup. Die Auswahlregel je Datei steht in
`tests/fixtures/PROVENANCE.md` neben dem Abrufdatum. Wo gekuerzt wird, bleiben
Kopfzeile und Struktur unangetastet — eine Fixture, die stillschweigend weniger
belegt, als sie aussieht, waere genau der Fehler, gegen den das hier angeht.

CKAN VERLANGT EINEN EIGENEN USER-AGENT. `ckan.opendata.swiss` antwortet auf den
Default von httpx/curl mit HTTP 403. Das Skript sendet denselben UA wie der
Server (`CKAN_USER_AGENT`) — sonst zeichnete es eine Fehlerseite auf und
merkte es nicht.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

import httpx

AGVCH = "https://www.agvchapp.bfs.admin.ch/api/communes"
CKAN = "https://ckan.opendata.swiss/api/3/action"
HSSO = "https://hsso.ch"
PXWEB = "https://www.pxweb.bfs.admin.ch/api/v1"

FIXTURES = Path(__file__).resolve().parent.parent / "tests" / "fixtures"

# Denselben UA wie der Server senden, sonst ist die Aufzeichnung eine 403-Seite.
try:
    from swiss_statistics_mcp.server import CKAN_USER_AGENT
except Exception:  # pragma: no cover — Skript laeuft auch ohne installiertes Paket
    CKAN_USER_AGENT = "swiss-statistics-mcp (+https://github.com/malkreide/swiss-statistics-mcp)"

# Der Zeitraum, in dem die Gemeindefusion Horgen/Hirzel liegt — der Fall, den die
# bestehenden Tests durchspielen. Fest, nicht «heute»: Eine Fixture, deren
# Auswahl vom Aufzeichnungstag abhaengt, erzeugt bei jedem Lauf einen Diff.
MUT_PERIOD = ("01-01-2018", "31-12-2018")
# Der Zeitraum, den `resolve_historical_commune` in seinem Anker-Fall abfragt.
CORR_PERIOD = ("01-01-2000", "01-01-2025")
CORR_KEEP_BFS = {"132", "133", "295"}
# ZWEI Snapshots, und das ist selbst ein Befund. Die erfundene Vorgaengerin
# fuehrte BFS 133 (Horgen, vor der Fusion) UND 295 (nachher) in EINER Datei —
# einen Zustand, den die Quelle nie liefert: Ein Snapshot ist ein Zeitpunkt.
# Der Server ruft ihn zweimal auf, zum from_date und zum to_date; erst zwei
# Dateien bilden das nach.
SNAPSHOT_DATES = {"historic": "01-01-2017", "current": "01-01-2019"}
# Die Kette, die die Tests brauchen: Kanton -> Bezirk -> Gemeinden, zweisprachig.
# Je Zeitpunkt die Kette, die dort existiert. `bfs` ist die harte Zusicherung:
# Fehlt eine dieser Nummern, bricht das Skript ab, statt eine Fixture zu
# schreiben, an der ein Test spaeter still vorbeilaeuft.
SNAPSHOT_KEEP = {
    "historic": {
        "names": {"Zürich", "Bezirk Horgen", "Valais / Wallis", "District de Monthey"},
        "bfs": {"132", "133", "6158"},  # Hirzel, Horgen (vor Fusion), Vionnaz
    },
    "current": {
        "names": {"Zürich", "Bezirk Horgen", "Valais / Wallis", "District de Monthey"},
        "bfs": {"295", "293", "6158"},  # Horgen (fusioniert), Wädenswil, Vionnaz
    },
}
HSSO_CHAPTER = "/de/2012/b"
PX_TABLE = "de/px-x-0102020000_101/px-x-0102020000_101.px"


def record() -> int:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    recorded_at = datetime.now(UTC).strftime("%Y-%m-%d")
    entries: list[dict] = []

    def write(name: str, text: str, url: str, rule: str) -> None:
        (FIXTURES / name).write_text(text, encoding="utf-8")
        entries.append(
            {
                "name": name,
                "url": url,
                "rule": rule,
                "bytes": len(text.encode("utf-8")),
                "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            }
        )
        print(f"ok  {name:<28} {len(text.encode('utf-8')):>7} B")

    with httpx.Client(timeout=120.0, follow_redirects=True) as c:
        # 1) AGVCH-Snapshots — je Zeitpunkt eine Datei.
        for label, date in SNAPSHOT_DATES.items():
            url = f"{AGVCH}/snapshot?date={date}"
            r = c.get(url)
            r.raise_for_status()
            lines = r.text.splitlines()
            header, rows = lines[0], lines[1:]
            cols = header.split(",")
            name_col, bfs_col = cols.index("Name"), cols.index("BfsCode")
            wanted = SNAPSHOT_KEEP[label]
            kept = [
                x
                for x in rows
                if x.split(",")[name_col].strip('"') in wanted["names"]
                or x.split(",")[bfs_col].strip('"') in wanted["bfs"]
            ]
            found_bfs = {x.split(",")[bfs_col].strip('"') for x in kept}
            missing = wanted["bfs"] - found_bfs
            if missing:
                # Laut scheitern statt eine lueckenhafte Fixture zu schreiben:
                # Eine Auswahlregel, die nichts mehr trifft, ist der Befund.
                raise SystemExit(
                    f"snapshot {date}: BFS {sorted(missing)} nicht im Bestand — "
                    "Auswahlregel oder Datum pruefen"
                )
            # Der Disambiguierungs-Test lebt von einer Eigenschaft der Quelle:
            # Ein `HistoricalCode` kann auf ZWEI Ebenen in zwei Kantonen
            # vorkommen — gemessen 11-mal, darunter 10078 als «Bezirk Horgen»
            # (Level 2, ZH) und «Vionnaz» (Level 3, VS). Ohne ein solches Paar
            # in der Fixture prueft der Test nichts und bleibt gruen.
            hist_col = cols.index("HistoricalCode")
            level_col = cols.index("Level")
            seen: dict[str, set[str]] = {}
            for x in kept:
                f = x.split(",")
                seen.setdefault(f[hist_col], set()).add(f[level_col])
            if not any(len(levels) > 1 for levels in seen.values()):
                raise SystemExit(
                    f"snapshot {date}: kein HistoricalCode auf zwei Ebenen in "
                    "der Auswahl — der Disambiguierungs-Test wuerde leer "
                    "bestehen. SNAPSHOT_KEEP pruefen."
                )

            write(
                f"agvch_snapshot_{label}.csv",
                header + "\n" + "\n".join(kept) + "\n",
                url,
                f"Stand {date}; Kopfzeile unveraendert, {len(kept)} von "
                f"{len(rows)} Zeilen — die Kette Kanton/Bezirk/Gemeinde, wie "
                "die Tests sie durchspielen",
            )

        # 2) Mutationen — Zeitraum der Fusion Hirzel/Horgen.
        start, end = MUT_PERIOD
        url = f"{AGVCH}/mutations?startPeriod={start}&endPeriod={end}"
        r = c.get(url)
        r.raise_for_status()
        body = r.text
        if len(body.splitlines()) < 2:
            raise SystemExit(f"mutations: keine Datenzeile im Zeitraum {start}..{end}")
        write(
            "agvch_mutations.csv",
            body if body.endswith("\n") else body + "\n",
            url,
            f"vollstaendig fuer den Zeitraum {start} bis {end}; "
            f"{len(body.splitlines()) - 1} Datenzeilen",
        )

        # 3) Korrespondenzen — MIT DEN PARAMETERN, DIE DER SERVER SENDET.
        #
        # Das ist keine Kleinigkeit: `resolve_historical_commune` ruft
        # `includeUnmodified=true&includeTerritoryExchange=false` ueber den
        # gesamten Zeitraum ab und liest daraus die Aufloesung. Wer die Fixture
        # mit anderen Parametern aufzeichnet, legt dem Mock eine Antwort in den
        # Mund, die der Server nie anfordert — und der Test prueft dann einen
        # Pfad, den es nicht gibt.
        params = (
            "includeUnmodified=true&includeTerritoryExchange=false"
            f"&startPeriod={CORR_PERIOD[0]}&endPeriod={CORR_PERIOD[1]}"
        )
        url = f"{AGVCH}/correspondances?{params}"
        r = c.get(url)
        r.raise_for_status()
        lines = r.text.splitlines()
        header, rows = lines[0], lines[1:]
        cols = header.split(",")
        ini_col, term_col = cols.index("InitialCode"), cols.index("TerminalCode")
        kept = [
            x
            for x in rows
            if x.split(",")[ini_col] in CORR_KEEP_BFS or x.split(",")[term_col] in CORR_KEEP_BFS
        ]
        if len(kept) < 2:
            raise SystemExit(
                f"correspondances: nur {len(kept)} Zeile(n) zu {sorted(CORR_KEEP_BFS)} "
                "— die Aufloesungskette ist weg, CORR_KEEP_BFS pruefen"
            )
        write(
            "agvch_correspondances.csv",
            header + "\n" + "\n".join(kept) + "\n",
            url,
            f"Kopfzeile unveraendert; {len(kept)} von {len(rows)} Zeilen — die "
            f"Zeilen zu BFS {sorted(CORR_KEEP_BFS)} (Fusion Hirzel/Horgen). "
            "Parameter wie vom Server gesendet, inkl. includeUnmodified=true",
        )

        # 3) CKAN — mit dem Pflicht-User-Agent.
        url = f"{CKAN}/package_search?q=bevoelkerung&rows=2"
        r = c.get(url, headers={"User-Agent": CKAN_USER_AGENT})
        if r.status_code == 403:
            raise SystemExit(
                "CKAN antwortet 403 trotz User-Agent — der UA-Quirk hat sich "
                "geaendert, siehe server.py"
            )
        r.raise_for_status()
        payload = r.json()
        if not payload.get("success"):
            raise SystemExit("CKAN meldet success=false")
        write(
            "ckan_package_search.json",
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            url,
            f"Suche «bevoelkerung» mit rows=2; `count` ist der echte "
            f"Gesamtbestand ({payload['result'].get('count')})",
        )

        # 4) HSSO-Kapitel, auf die Anker gekuerzt, die der Parser liest.
        url = f"{HSSO}{HSSO_CHAPTER}"
        r = c.get(url)
        r.raise_for_status()
        anchors = re.findall(r'<a[^>]*class="[^"]*explorer-item[^"]*"[^>]*>.*?</a>', r.text, re.S)
        items = [a for a in anchors if "explorer-item__title" in a][:4]
        if len(items) < 2:
            raise SystemExit(
                f"HSSO: nur {len(items)} explorer-item-Anker gefunden — Markup "
                "geaendert, der Parser liest genau diese"
            )
        write(
            "hsso_chapter_b.html",
            "<html><body>" + "".join(items) + "</body></html>\n",
            url,
            f"die ersten {len(items)} von {len(anchors)} explorer-item-Ankern; "
            "das umgebende Markup (215 KB) liest der Parser nie",
        )

        # 5) PXWeb-Tabellenmetadaten.
        url = f"{PXWEB}/{PX_TABLE}"
        r = c.get(url)
        r.raise_for_status()
        meta = r.json()
        write(
            "pxweb_metadata.json",
            json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
            url,
            f"vollstaendig; Tabelle «{meta.get('title', '?')}» mit "
            f"{len(meta.get('variables', []))} Variablen",
        )

    _write_provenance(recorded_at, entries)
    print(f"\nPROVENANCE.md geschrieben, Aufzeichnungsdatum {recorded_at}")
    return 0


def _write_provenance(recorded_at: str, entries: list[dict]) -> None:
    lines = [
        "# Herkunft der Fixtures",
        "",
        "**Erzeugt von `scripts/record_fixtures.py`. Nicht von Hand pflegen.**",
        "",
        f"Aufgezeichnet am **{recorded_at}** von den vier Quellen dieses Servers:",
        f"`{AGVCH}`, `{CKAN}`, `{HSSO}`, `{PXWEB}`.",
        "",
        "Ohne Datum ist «aufgezeichnet» nach zwei Jahren von «ausgedacht» nicht",
        "mehr zu unterscheiden — die Datei sieht gleich aus, und niemand weiss,",
        "ob sie den Stand von gestern zeigt oder den von vor drei",
        "Schema-Wechseln.",
        "",
        "**Es sind Ausschnitte, keine Vollabzuege.** Die Auswahlregel steht je",
        "Datei dabei; Kopfzeilen und Struktur sind unangetastet. Eine Fixture",
        "belegt damit die *Form* der Antwort und einen datierten Ausschnitt ihres",
        "Inhalts — nicht den Bestand. Aussagen ueber Vollstaendigkeit gehoeren in",
        "Live-Tests.",
        "",
        "**CKAN verlangt einen eigenen User-Agent** (sonst HTTP 403). Das Skript",
        "sendet denselben wie der Server; ohne ihn zeichnete es eine Fehlerseite",
        "auf und merkte es nicht.",
        "",
    ]
    for e in entries:
        lines += [
            f"## `{e['name']}`",
            "",
            f"- **Quelle:** `{e['url']}`",
            f"- **Aufgezeichnet:** {recorded_at}",
            f"- **Auswahl:** {e['rule']}",
            f"- **Groesse:** {e['bytes']} B",
            f"- **SHA-256:** `{e['sha256']}`",
            "",
        ]
    (FIXTURES / "PROVENANCE.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    try:
        raise SystemExit(record())
    except httpx.HTTPError as exc:
        print(f"FEHLER: Quelle nicht erreichbar: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
