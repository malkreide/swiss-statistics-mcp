# swiss-statistics-mcp

**🇬🇧 [English version → README_EN.md](README_EN.md)**

Ein MCP-Server für den direkten Zugriff auf Schweizer Statistikdaten des Bundesamts für Statistik (BFS) via STAT-TAB PxWeb API — 682 Datensätze aus 21 Themengebieten, keine Authentifizierung erforderlich.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![MCP](https://img.shields.io/badge/MCP-kompatibel-green.svg)](https://modelcontextprotocol.io)
[![Lizenz: MIT](https://img.shields.io/badge/Lizenz-MIT-yellow.svg)](LICENSE)
[![Open Data](https://img.shields.io/badge/Open%20Data-BFS-red.svg)](https://www.bfs.admin.ch)
[![CI](https://github.com/malkreide/swiss-statistics-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/malkreide/swiss-statistics-mcp/actions)

---

## Was ist das?

Stellen Sie sich vor, Sie könnten einem KI-Assistenten eine Frage stellen wie: *«Wie viele Schülerinnen und Schüler besuchen 2024 die Sekundarstufe I im Kanton Zürich?»* — und das Modell antwortet nicht mit einer Schätzung, sondern mit echten, aktuellen Zahlen direkt aus der offiziellen BFS-Statistik.

Das ist die Kernidee dieses Servers. Er funktioniert wie ein **Dolmetscher zwischen KI-Modell und der STAT-TAB-Datenbank des BFS**: Das Modell fragt auf natürliche Weise, der Server übersetzt die Anfrage in API-Aufrufe und liefert strukturierte Daten zurück.

> **Anwendungsbeispiel aus dem Schulkontext:** *«Wie hat sich die Anzahl Lehrkräfte an Zürcher Volksschulen zwischen 2015 und 2023 entwickelt?»* → `bfs_education_stats(topic="teachers", canton="Zürich")` → reale BFS-Zahlen, keine Halluzination.

---

## Werkzeuge (Tools)

| Tool | Beschreibung |
|---|---|
| `bfs_featured_datasets` | Kuratierte Liste hochrelevanter Datensätze (Schwerpunkt Bildung und Demografie) |
| `bfs_list_themes` | Alle 21 BFS-Themen mit Anzahl verfügbarer Datensätze |
| `bfs_list_tables_by_theme` | Alle Tabellen eines Themas (z.B. `"15"` = Bildung und Wissenschaft) |
| `bfs_search_tables` | Freitextsuche über den gesamten Datenkatalog (682 Datensätze) |
| `bfs_get_table_metadata` | Variablen, Ausprägungen und Metadaten einer spezifischen Tabelle |
| `bfs_get_data` | Datenabruf mit optionalen Filtern nach Dimensionen und Werten |
| `bfs_education_stats` | Convenience-Tool: Lehrkräfte, Schüler/-innen, Szenarien, Stipendien |
| `bfs_population` | Wohnbevölkerung nach Kanton, Jahr, Altersstruktur oder Geschlecht |
| `bfs_compare_cantons` | Kantonsvergleich für eine beliebige Tabelle und ein beliebiges Merkmal |

---

## Anwendungsbeispiele

```text
# Bildung
Wie viele Lehrkräfte unterrichteten 2023 im Kanton Zürich?
→ bfs_education_stats(topic="teachers", canton="Zürich")

Wie entwickeln sich die Schülerzahlen der Sekundarstufe II bis 2031?
→ bfs_education_stats(topic="scenarios")

Welche Bildungsdaten gibt es zum Thema Stipendien?
→ bfs_education_stats(topic="grants")

# Bevölkerung
Wie gross ist die Bevölkerung im Kanton Zürich, aufgeteilt nach Alter (0–18)?
→ bfs_population(region="Zürich", breakdown="age")

Wie hat sich die Bevölkerung der Schweiz nach Geschlecht entwickelt?
→ bfs_population(breakdown="sex")

# Themensuche und Exploration
Welche Tabellen gibt es zum Thema Sozialhilfe?
→ bfs_list_tables_by_theme(theme_code="13")

Gibt es Daten zu Schulliegenschaften?
→ bfs_search_tables(query="Schulliegenschaften")

Welche Themengebiete bietet das BFS an?
→ bfs_list_themes()

# Kantonsvergleich
Vergleiche die Sozialhilfequote aller Kantone für 2022.
→ bfs_compare_cantons(table_id="13.2.2.3", variable="Kanton", year="2022")
```

---

## Datenbasis

| Eigenschaft | Details |
|---|---|
| **API** | STAT-TAB PxWeb API v1 |
| **Endpoint** | `https://www.pxweb.bfs.admin.ch/api/v1/` |
| **Anbieter** | Bundesamt für Statistik (BFS), Schweiz |
| **Datensätze** | 682 Tabellen in 21 Themengebieten |
| **Sprachen** | Deutsch (`de`), Französisch (`fr`), Italienisch (`it`), Englisch (`en`) |
| **Lizenz** | Open Government Data (OGD) — [BFS-Nutzungsbedingungen](https://www.bfs.admin.ch/bfs/de/home/grundlagen/nutzungsbedingungen.html) |
| **Authentifizierung** | Keine — vollständig öffentlich zugänglich |

---

## Themengebiete

| Code | Thema | Code | Thema |
|---|---|---|---|
| 01 | Bevölkerung | 12 | Geld, Banken, Versicherungen |
| 02 | Raum und Umwelt | 13 | Soziale Sicherheit |
| 03 | Arbeit und Erwerb | 14 | Gesundheit |
| 04 | Volkswirtschaft | **15** | **Bildung und Wissenschaft** |
| 05 | Preise | 16 | Kultur, Medien, Informationsgesellschaft |
| 06 | Industrie und Dienstleistungen | 17 | Politik |
| 07 | Land- und Forstwirtschaft | 18 | Öffentliche Verwaltung |
| 08 | Energie | 19 | Kriminalität und Strafrecht |
| 09 | Bau- und Wohnungswesen | 20 | Wirtschaftliche und soziale Situation |
| 10 | Tourismus | 21 | Nachhaltige Entwicklung |
| 11 | Mobilität und Verkehr | | |

---

## Installation

### Voraussetzungen

- Python ≥ 3.11
- `uvx` (empfohlen) oder `pip`

### Claude Desktop

Konfigurationsdatei öffnen:

- **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "swiss-statistics": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/malkreide/swiss-statistics-mcp",
        "swiss-statistics-mcp"
      ]
    }
  }
}
```

Claude Desktop neu starten — der Server ist danach direkt verfügbar.

### Cursor / Windsurf / VS Code + Continue

Die Konfigurationssyntax ist identisch zu Claude Desktop. Die JSON-Datei heisst je nach Client:

- **Cursor:** `.cursor/mcp.json` im Projektordner oder `~/.cursor/mcp.json` global
- **Windsurf:** `~/.codeium/windsurf/mcp_config.json`
- **VS Code + Continue:** `.continue/config.json`

```json
{
  "mcpServers": {
    "swiss-statistics": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/malkreide/swiss-statistics-mcp",
        "swiss-statistics-mcp"
      ]
    }
  }
}
```

### LibreChat / Cline (SSE-Transport)

Für webbasierte oder remote betriebene Clients wird der SSE-Transport verwendet:

```bash
MCP_TRANSPORT=sse python -m swiss_statistics_mcp.server
# Startet auf Port 8052 (oder $PORT falls gesetzt)
```

In der Client-Konfiguration:

```json
{
  "mcpServers": {
    "swiss-statistics": {
      "url": "http://localhost:8052/sse"
    }
  }
}
```

### Lokale Entwicklung

```bash
git clone https://github.com/malkreide/swiss-statistics-mcp
cd swiss-statistics-mcp
pip install -e .
```

Claude Desktop config für lokale Installation:

```json
{
  "mcpServers": {
    "swiss-statistics": {
      "command": "python",
      "args": ["-m", "swiss_statistics_mcp.server"],
      "env": {
        "PYTHONPATH": "/absoluter/pfad/zu/swiss-statistics-mcp/src"
      }
    }
  }
}
```

### Deployment auf Render.com (SSE)

```bash
# Umgebungsvariable setzen
MCP_TRANSPORT=sse

# Startbefehl
python -m swiss_statistics_mcp.server
```

Der Server startet auf `$PORT` (Render.com setzt diese Variable automatisch).

---

## Kompatibilität

Dieser Server implementiert das offene [Model Context Protocol (MCP)](https://modelcontextprotocol.io) und ist **modellunabhängig** — er funktioniert mit jedem MCP-kompatiblen Client.

| Client | Transport | Status |
|---|---|---|
| Claude Desktop | stdio | ✅ Unterstützt |
| Cursor | stdio | ✅ Unterstützt |
| Windsurf | stdio | ✅ Unterstützt |
| VS Code + Continue | stdio | ✅ Unterstützt |
| LibreChat | SSE | ✅ Unterstützt |
| Cline | stdio | ✅ Unterstützt |
| Self-hosted via mcp-proxy | SSE | ✅ Unterstützt |

---

## Entwicklung und Tests

```bash
# Tests ohne Netzwerkzugriff (empfohlen für CI)
PYTHONPATH=src python -m pytest tests/ -m "not live"

# Live-Tests gegen die echte BFS-API
PYTHONPATH=src python -m pytest tests/ -m live -v

# Einzelnen Smoke-Test
PYTHONPATH=src python -c "
import asyncio
from swiss_statistics_mcp.server import bfs_list_themes
print(asyncio.run(bfs_list_themes()))
"
```

### CI/CD

Der Server verwendet GitHub Actions mit einer Matrix über Python 3.11, 3.12 und 3.13. Jeder Push und Pull Request wird automatisch getestet (Ruff-Linting + pytest).

---

## Verwandte Projekte

Weitere Open-Data MCP-Server von [@malkreide](https://github.com/malkreide):

| Server | Beschreibung |
|---|---|
| [zurich-opendata-mcp](https://github.com/malkreide/zurich-opendata-mcp) | CKAN, Wetter, Luftqualität, Parkplätze, Gemeinderat Zürich |
| [fedlex-mcp](https://github.com/malkreide/fedlex-mcp) | Schweizer Bundesrecht via Fedlex SPARQL |
| [swiss-transport-mcp](https://github.com/malkreide/swiss-transport-mcp) | OJP Reiseplanung, SIRI-SX Störungen, Tarife |
| [swiss-road-mobility-mcp](https://github.com/malkreide/swiss-road-mobility-mcp) | Shared Mobility, E-Ladestationen, Verkehrsdaten |
| [global-education-mcp](https://github.com/malkreide/global-education-mcp) | UNESCO UIS und OECD Education at a Glance |
| [eth-library-mcp](https://github.com/malkreide/eth-library-mcp) | ETH-Bibliothek Katalogsuche |
| [patent-mcp](https://github.com/malkreide/patent-mcp) | EPO Open Patent Services + IGE/Swissreg |

---

## Lizenz

MIT — siehe [LICENSE](LICENSE)

Daten: Open Government Data (OGD) des Bundesamts für Statistik (BFS). Nutzung gemäss [BFS-Nutzungsbedingungen](https://www.bfs.admin.ch/bfs/de/home/grundlagen/nutzungsbedingungen.html).

---

*Entwickelt von [@malkreide](https://github.com/malkreide) · Nicht offiziell affiliiert mit dem BFS · Beiträge willkommen*
