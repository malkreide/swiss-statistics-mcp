> 🇨🇭 **Part of the [Swiss Public Data MCP Portfolio](https://github.com/malkreide)**

# 📊 swiss-statistics-mcp

![Version](https://img.shields.io/badge/version-0.1.0-blue)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![MCP](https://img.shields.io/badge/MCP-Model%20Context%20Protocol-purple)](https://modelcontextprotocol.io/)
[![No Auth Required](https://img.shields.io/badge/auth-none%20required-brightgreen)](https://github.com/malkreide/swiss-statistics-mcp)
![CI](https://github.com/malkreide/swiss-statistics-mcp/actions/workflows/ci.yml/badge.svg)

> MCP Server for Swiss Federal Statistical Office (BFS) data via STAT-TAB PxWeb API — 682 datasets across 21 themes, no authentication required

[🇩🇪 Deutsche Version](README.de.md)

---

## Overview

`swiss-statistics-mcp` provides AI-native access to the Swiss Federal Statistical Office (BFS) via the STAT-TAB PxWeb API, without authentication:

| Property | Details |
|----------|---------|
| **API** | STAT-TAB PxWeb API v1 |
| **Endpoint** | `https://www.pxweb.bfs.admin.ch/api/v1/` |
| **Provider** | Swiss Federal Statistical Office (BFS) |
| **Datasets** | 682 tables across 21 thematic areas |
| **Languages** | German (`de`), French (`fr`), Italian (`it`), English (`en`) |
| **Licence** | Open Government Data (OGD) — [BFS Terms of Use](https://www.bfs.admin.ch/bfs/en/home/grundlagen/nutzungsbedingungen.html) |
| **Authentication** | None — fully public |

**Anchor demo query:** *"How many students attended lower secondary schools in the canton of Zurich in 2024?"* — real BFS figures, no hallucination.

---

## Features

- 📊 **9 tools** across 21 statistical themes (682 datasets)
- 🔍 **Full-text search** across the entire BFS data catalogue
- 🎓 **Convenience tools** for education statistics and population data
- 🏔️ **Cross-cantonal comparison** for any table and variable
- 🔓 **No API key required** — all data under open licences
- ☁️ **Dual transport** — stdio (Claude Desktop) + Streamable HTTP (cloud)

---

## Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) (recommended) or pip

---

## Installation

```bash
# Clone the repository
git clone https://github.com/malkreide/swiss-statistics-mcp.git
cd swiss-statistics-mcp

# Install
pip install -e .
# or with uv:
uv pip install -e .
```

Or with `uvx` (no permanent installation):

```bash
uvx swiss-statistics-mcp
```

---

## Quickstart

```bash
# stdio (for Claude Desktop)
python -m swiss_statistics_mcp.server

# Streamable HTTP (port 8000)
python -m swiss_statistics_mcp.server --http --port 8000
```

Try it immediately in Claude Desktop:

> *"How many teachers worked in the canton of Zurich in 2023?"*
> *"What is the population of canton Bern broken down by age?"*
> *"Compare the social assistance rate across all cantons for 2022."*

---

## Configuration

### Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "swiss-statistics": {
      "command": "python",
      "args": ["-m", "swiss_statistics_mcp.server"]
    }
  }
}
```

Or with `uvx`:

```json
{
  "mcpServers": {
    "swiss-statistics": {
      "command": "uvx",
      "args": ["swiss-statistics-mcp"]
    }
  }
}
```

**Config file locations:**
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

### Cursor / Windsurf / VS Code + Continue

The configuration syntax is identical to Claude Desktop. The file name depends on the client:

- **Cursor:** `.cursor/mcp.json` in the project folder, or `~/.cursor/mcp.json` globally
- **Windsurf:** `~/.codeium/windsurf/mcp_config.json`
- **VS Code + Continue:** `.continue/config.json`

### Cloud Deployment (SSE for browser access)

For use via **claude.ai in the browser** (e.g. on managed workstations without local software):

**Render.com (recommended):**
1. Push/fork the repository to GitHub
2. On [render.com](https://render.com): New Web Service → connect GitHub repo
3. Set start command: `python -m swiss_statistics_mcp.server --http --port 8000`
4. In claude.ai under Settings → MCP Servers, add: `https://your-app.onrender.com/sse`

> 💡 *"stdio for the developer laptop, SSE for the browser."*

---

## Available Tools

| Tool | Description |
|------|-------------|
| `bfs_featured_datasets` | Curated list of highly relevant datasets (focus on education and demographics) |
| `bfs_list_themes` | All 21 BFS themes with number of available datasets |
| `bfs_list_tables_by_theme` | All tables for a given theme (e.g. `"15"` = Education and Science) |
| `bfs_search_tables` | Full-text search across the entire data catalogue (682 datasets) |
| `bfs_get_table_metadata` | Variables, values and metadata for a specific table |
| `bfs_get_data` | Data retrieval with optional filters by dimensions and values |
| `bfs_education_stats` | Convenience tool: teachers, pupils, demographic scenarios, scholarships |
| `bfs_population` | Resident population by canton, year, age structure or sex |
| `bfs_compare_cantons` | Cross-cantonal comparison for any table and any variable |

### Example Use Cases

| Query | Tool |
|-------|------|
| *"How many teachers worked in Zurich in 2023?"* | `bfs_education_stats` |
| *"How will upper secondary enrolment develop until 2031?"* | `bfs_education_stats` |
| *"What is the population of canton Zurich by age?"* | `bfs_population` |
| *"Compare the social assistance rate across all cantons"* | `bfs_compare_cantons` |
| *"Is there data on school buildings?"* | `bfs_search_tables` |

---

## Themes

| Code | Theme | Code | Theme |
|------|-------|------|-------|
| 01 | Population | 12 | Money, banks, insurance |
| 02 | Territory and environment | 13 | Social security |
| 03 | Work and income | 14 | Health |
| 04 | National economy | **15** | **Education and science** |
| 05 | Prices | 16 | Culture, media, information society |
| 06 | Industry and services | 17 | Politics |
| 07 | Agriculture and forestry | 18 | General government |
| 08 | Energy | 19 | Crime and criminal justice |
| 09 | Construction and housing | 20 | Economic and social situation |
| 10 | Tourism | 21 | Sustainable development |
| 11 | Mobility and transport | | |

---

## Architecture

```
┌─────────────────┐     ┌──────────────────────────────┐     ┌──────────────────────────┐
│   Claude / AI   │────▶│  Swiss Statistics MCP          │────▶│  BFS STAT-TAB            │
│   (MCP Host)    │◀────│  (MCP Server)                │◀────│  PxWeb API v1            │
└─────────────────┘     │                              │     └──────────────────────────┘
                        │  9 Tools                     │
                        │  682 datasets · 21 themes    │
                        │  Stdio | Streamable HTTP     │
                        │                              │
                        │  No authentication required  │
                        └──────────────────────────────┘
```

### Data Source Characteristics

| Source | Protocol | Coverage | Auth |
|--------|----------|----------|------|
| BFS STAT-TAB | PxWeb REST API | 682 tables, 21 themes | None |

---

## Project Structure

```
swiss-statistics-mcp/
├── src/swiss_statistics_mcp/
│   ├── __init__.py              # Package
│   └── server.py                # 9 tools
├── tests/
│   └── test_server.py           # Unit + integration tests (mocked HTTP)
├── .github/workflows/ci.yml     # GitHub Actions (Python 3.11/3.12/3.13)
├── pyproject.toml
├── CHANGELOG.md
├── CONTRIBUTING.md
├── LICENSE
├── README.md                    # This file (English)
└── README.de.md                 # German version
```

---

## Known Limitations

- **PxWeb API:** Rate limiting may apply for rapid successive queries; the server uses a 1-hour cache for the catalogue index
- **Language:** Dataset titles and dimension values are in German by default; French, Italian and English coverage varies by table
- **JSON-STAT2:** Some complex cross-tabulations may return large result sets; use dimension filters to narrow queries

---

## Testing

```bash
# Unit tests (no API key required)
PYTHONPATH=src pytest tests/ -m "not live"

# Integration tests (live API calls)
pytest tests/ -m "live"
```

---

## Changelog

See [CHANGELOG.md](CHANGELOG.md)

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md)

---

## License

MIT License — see [LICENSE](LICENSE)

---

## Author

Hayal Oezkan · [malkreide](https://github.com/malkreide)

---

## Credits & Related Projects

- **BFS:** [www.bfs.admin.ch](https://www.bfs.admin.ch/) — Swiss Federal Statistical Office
- **STAT-TAB:** [www.pxweb.bfs.admin.ch](https://www.pxweb.bfs.admin.ch/) — PxWeb database interface
- **Protocol:** [Model Context Protocol](https://modelcontextprotocol.io/) — Anthropic / Linux Foundation
- **Related:** [swiss-cultural-heritage-mcp](https://github.com/malkreide/swiss-cultural-heritage-mcp) — SIK-ISEA, Nationalmuseum, Nationalbibliothek
- **Related:** [fedlex-mcp](https://github.com/malkreide/fedlex-mcp) — Swiss federal law via Fedlex SPARQL
- **Related:** [zurich-opendata-mcp](https://github.com/malkreide/zurich-opendata-mcp) — CKAN, weather, air quality, City of Zurich
- **Related:** [swiss-transport-mcp](https://github.com/malkreide/swiss-transport-mcp) — OJP journey planning, SIRI-SX disruptions
- **Related:** [global-education-mcp](https://github.com/malkreide/global-education-mcp) — UNESCO UIS and OECD Education at a Glance
- **Portfolio:** [Swiss Public Data MCP Portfolio](https://github.com/malkreide)
