# Herkunft der Fixtures

**Erzeugt von `scripts/record_fixtures.py`. Nicht von Hand pflegen.**

Aufgezeichnet am **2026-08-07** von den vier Quellen dieses Servers:
`https://www.agvchapp.bfs.admin.ch/api/communes`, `https://ckan.opendata.swiss/api/3/action`, `https://hsso.ch`, `https://www.pxweb.bfs.admin.ch/api/v1`.

Ohne Datum ist «aufgezeichnet» nach zwei Jahren von «ausgedacht» nicht
mehr zu unterscheiden — die Datei sieht gleich aus, und niemand weiss,
ob sie den Stand von gestern zeigt oder den von vor drei
Schema-Wechseln.

**Es sind Ausschnitte, keine Vollabzuege.** Die Auswahlregel steht je
Datei dabei; Kopfzeilen und Struktur sind unangetastet. Eine Fixture
belegt damit die *Form* der Antwort und einen datierten Ausschnitt ihres
Inhalts — nicht den Bestand. Aussagen ueber Vollstaendigkeit gehoeren in
Live-Tests.

**CKAN verlangt einen eigenen User-Agent** (sonst HTTP 403). Das Skript
sendet denselben wie der Server; ohne ihn zeichnete es eine Fehlerseite
auf und merkte es nicht.

## `agvch_snapshot_historic.csv`

- **Quelle:** `https://www.agvchapp.bfs.admin.ch/api/communes/snapshot?date=01-01-2017`
- **Aufgezeichnet:** 2026-08-07
- **Auswahl:** Stand 01-01-2017; Kopfzeile unveraendert, 8 von 2429 Zeilen — die Kette Kanton/Bezirk/Gemeinde, wie die Tests sie durchspielen
- **Groesse:** 539 B
- **SHA-256:** `d3e65d0651e626bedceae99c23149b46543f7531ca4f6a0b758091b1d7c51cd3`

## `agvch_snapshot_current.csv`

- **Quelle:** `https://www.agvchapp.bfs.admin.ch/api/communes/snapshot?date=01-01-2019`
- **Aufgezeichnet:** 2026-08-07
- **Auswahl:** Stand 01-01-2019; Kopfzeile unveraendert, 8 von 2381 Zeilen — die Kette Kanton/Bezirk/Gemeinde, wie die Tests sie durchspielen
- **Groesse:** 527 B
- **SHA-256:** `081a3ee65fb12a87115b219394146ae5dbae8e3aaa06637997c085b5cf4ae7f8`

## `agvch_mutations.csv`

- **Quelle:** `https://www.agvchapp.bfs.admin.ch/api/communes/mutations?startPeriod=01-01-2018&endPeriod=31-12-2018`
- **Aufgezeichnet:** 2026-08-07
- **Auswahl:** vollstaendig fuer den Zeitraum 01-01-2018 bis 31-12-2018; 60 Datenzeilen
- **Groesse:** 7626 B
- **SHA-256:** `e30960333e6f712502fe0dee2ed9910fc8beabfdebbb0b527834b636dd7149a2`

## `agvch_correspondances.csv`

- **Quelle:** `https://www.agvchapp.bfs.admin.ch/api/communes/correspondances?includeUnmodified=true&includeTerritoryExchange=false&startPeriod=01-01-2000&endPeriod=01-01-2025`
- **Aufgezeichnet:** 2026-08-07
- **Auswahl:** Kopfzeile unveraendert; 2 von 2903 Zeilen — die Zeilen zu BFS ['132', '133', '295'] (Fusion Hirzel/Horgen). Parameter wie vom Server gesendet, inkl. includeUnmodified=true
- **Groesse:** 374 B
- **SHA-256:** `072d136423a62c09a4d0ce4cf45112206b4e628a5a78e813462520d4bb3cb96a`

## `ckan_package_search.json`

- **Quelle:** `https://ckan.opendata.swiss/api/3/action/package_search?q=bevoelkerung&rows=2`
- **Aufgezeichnet:** 2026-08-07
- **Auswahl:** Suche «bevoelkerung» mit rows=2; `count` ist der echte Gesamtbestand (2837)
- **Groesse:** 28160 B
- **SHA-256:** `5f2f8e1814d47788a7a497914d4936ff7a735dfe4dd79576aa90b03268f49d4f`

## `hsso_chapter_b.html`

- **Quelle:** `https://hsso.ch/de/2012/b`
- **Aufgezeichnet:** 2026-08-07
- **Auswahl:** die ersten 4 von 53 explorer-item-Ankern; das umgebende Markup (215 KB) liest der Parser nie
- **Groesse:** 792 B
- **SHA-256:** `9697f07b75f9dda58df4e81f37b04f394442140691c62d572785143651ca2627`

## `pxweb_metadata.json`

- **Quelle:** `https://www.pxweb.bfs.admin.ch/api/v1/de/px-x-0102020000_101/px-x-0102020000_101.px`
- **Aufgezeichnet:** 2026-08-07
- **Auswahl:** vollstaendig; Tabelle «Demografische Bilanz nach Kanton» mit 5 Variablen
- **Groesse:** 4652 B
- **SHA-256:** `8aac778e9597fbf316cbfe74a54757f1c3a6e221a3b5decc40260ae1d588782d`
