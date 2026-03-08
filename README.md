# swiss-statistics-mcp

Ein MCP-Server für den Zugriff auf Schweizer Statistikdaten des Bundesamts für Statistik (BFS) via STAT-TAB PxWeb API.

**A MCP server for Swiss Federal Statistical Office (BFS) data via the STAT-TAB PxWeb API.**

---

## Überblick / Overview

Dieser Server verbindet KI-Modelle direkt mit dem vollständigen Statistikangebot des BFS — 682 Datensätze aus 21 Themengebieten, von Bildung und Bevölkerung bis hin zu Politik und Sozialversicherungen. Keine Authentifizierung erforderlich, vollständig Open Data.

This server connects AI models directly to the complete BFS statistical offering — 682 datasets across 21 themes, from education and population to politics and social security. No authentication required, fully open data.

---

## Werkzeuge / Tools

| Tool | Beschreibung |
|---|---|
| `bfs_featured_datasets` | Kuratierte Liste hochrelevanter Datensätze (besonders Bildungskontext) |
| `bfs_list_themes` | Alle 21 BFS-Themen mit Anzahl Datensätze |
| `bfs_list_tables_by_theme` | Alle Tabellen eines Themas (z.B. `"15"` = Bildung) |
| `bfs_search_tables` | Freitextsuche über den gesamten Datenkatalog |
| `bfs_get_table_metadata` | Variablen, Ausprägungen und Metadaten einer Tabelle |
| `bfs_get_data` | Datenabruf mit optionalen Filtern (Dimensionen/Werte) |
| `bfs_education_stats` | Convenience-Tool: Lehrkräfte, Schüler, Szenarien, Stipendien |
| `bfs_population` | Wohnbevölkerung nach Kanton, Jahr, Altersstruktur oder Geschlecht |
| `bfs_compare_cantons` | Kantonsvergleich für eine beliebige Tabelle |

---

## Anwendungsbeispiele / Example Queries

```
Wie viele Lehrkräfte unterrichteten 2023 im Kanton Zürich?
→ bfs_education_stats(topic="teachers", canton="Zürich")

Wie entwickeln sich die Schülerzahlen der Sekundarstufe II bis 2031?
→ bfs_education_stats(topic="scenarios")

Wie gross ist die Bevölkerung im Kanton Zürich, aufgeteilt nach Alter (0–18)?
→ bfs_population(region="Zürich", breakdown="age")

Welche Tabellen gibt es zum Thema Sozialhilfe?
→ bfs_list_tables_by_theme(theme_code="13")

Gibt es Daten zu Schulliegenschaften?
→ bfs_search_tables(query="Schulliegenschaften")
```

---

## Installation

### Voraussetzungen / Requirements

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

### Lokale Entwicklung / Local Development

```bash
git clone https://github.com/malkreide/swiss-statistics-mcp
cd swiss-statistics-mcp
pip install -e .
```

Claude Desktop config (lokale Installation):

```json
{
  "mcpServers": {
    "swiss-statistics": {
      "command": "python",
      "args": ["-m", "swiss_statistics_mcp.server"],
      "env": {
        "PYTHONPATH": "/pfad/zu/swiss-statistics-mcp/src"
      }
    }
  }
}
```

### SSE Transport (Render.com / Cloud)

```bash
MCP_TRANSPORT=sse python -m swiss_statistics_mcp.server
# Startet auf Port 8052 (oder $PORT)
```

---

## Datenbasis / Data Source

- **API:** STAT-TAB PxWeb API v1 — `https://www.pxweb.bfs.admin.ch/api/v1/`
- **Anbieter:** Bundesamt für Statistik (BFS), Schweiz
- **Sprachen:** Deutsch (`de`), Französisch (`fr`), Italienisch (`it`), Englisch (`en`)
- **Lizenz:** Open Government Data (OGD), [BFS-Nutzungsbedingungen](https://www.bfs.admin.ch/bfs/de/home/grundlagen/nutzungsbedingungen.html)
- **Authentifizierung:** Keine

---

## Themen / Themes

| Code | Thema | Code | Thema |
|---|---|---|---|
| 01 | Bevölkerung | 12 | Geld, Banken, Versicherungen |
| 02 | Raum und Umwelt | 13 | Soziale Sicherheit |
| 03 | Arbeit und Erwerb | 14 | Gesundheit |
| 04 | Volkswirtschaft | 15 | **Bildung und Wissenschaft** |
| 05 | Preise | 16 | Kultur, Medien, Informationsgesellschaft |
| 06 | Industrie und Dienstleistungen | 17 | Politik |
| 07 | Land- und Forstwirtschaft | 18 | Öffentliche Verwaltung |
| 08 | Energie | 19 | Kriminalität und Strafrecht |
| 09 | Bau- und Wohnungswesen | 20 | Wirtschaftliche und soziale Situation |
| 10 | Tourismus | 21 | Nachhaltige Entwicklung |
| 11 | Mobilität und Verkehr | | |

---

## Kompatibilität / Compatibility

Dieser Server implementiert das offene [Model Context Protocol (MCP)](https://modelcontextprotocol.io) und ist modellunabhängig.

| Client | Transport | Status |
|---|---|---|
| Claude Desktop | stdio | ✅ |
| Cursor / Windsurf | stdio | ✅ |
| VS Code + Continue | stdio | ✅ |
| LibreChat | SSE | ✅ |
| Cline | stdio | ✅ |
| Self-hosted via mcp-proxy | SSE | ✅ |

---

## Entwicklung / Development

```bash
# Tests ausführen (ohne Netzwerk)
PYTHONPATH=src python -m pytest tests/ -m "not live"

# Live-Tests gegen echte BFS-API
PYTHONPATH=src python -m pytest tests/ -m live -v
```

---

## Lizenz / License

MIT — siehe [LICENSE](LICENSE)

---

*Entwickelt von [@malkreide](https://github.com/malkreide) · Nicht offiziell affiliiert mit dem BFS*
