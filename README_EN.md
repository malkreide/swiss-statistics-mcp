# swiss-statistics-mcp

**🇩🇪 [Deutsche Version → README.md](README.md)**

An MCP server for direct access to Swiss Federal Statistical Office (BFS) data via the STAT-TAB PxWeb API — 682 datasets across 21 themes, no authentication required.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![MCP](https://img.shields.io/badge/MCP-compatible-green.svg)](https://modelcontextprotocol.io)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Open Data](https://img.shields.io/badge/Open%20Data-BFS-red.svg)](https://www.bfs.admin.ch/bfs/en/home.html)
[![CI](https://github.com/malkreide/swiss-statistics-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/malkreide/swiss-statistics-mcp/actions)

---

## What is this?

Imagine asking an AI assistant: *"How many students attended lower secondary schools in the canton of Zurich in 2024?"* — and instead of an estimate, the model responds with real, current figures drawn directly from official BFS statistics.

That is the core idea of this server. Think of it as a **simultaneous interpreter between an AI model and the BFS STAT-TAB database**: the model asks in natural language, the server translates the request into API calls, and structured data flows back.

> **Example from a school administration context:** *"How did teacher numbers at Zurich public schools evolve between 2015 and 2023?"* → `bfs_education_stats(topic="teachers", canton="Zürich")` → real BFS figures, no hallucination.

---

## Tools

| Tool | Description |
|---|---|
| `bfs_featured_datasets` | Curated list of highly relevant datasets (focus on education and demographics) |
| `bfs_list_themes` | All 21 BFS themes with number of available datasets |
| `bfs_list_tables_by_theme` | All tables for a given theme (e.g. `"15"` = Education and Science) |
| `bfs_search_tables` | Full-text search across the entire data catalogue (682 datasets) |
| `bfs_get_table_metadata` | Variables, values and metadata for a specific table |
| `bfs_get_data` | Data retrieval with optional filters by dimensions and values |
| `bfs_education_stats` | Convenience tool: teachers, pupils, demographic scenarios, scholarships |
| `bfs_population` | Resident population by canton, year, age structure or sex |
| `bfs_compare_cantons` | Cross-cantonal comparison for any table and any variable |

---

## Example Queries

```text
# Education
How many teachers worked in the canton of Zurich in 2023?
→ bfs_education_stats(topic="teachers", canton="Zürich")

How will upper secondary enrolment numbers develop until 2031?
→ bfs_education_stats(topic="scenarios")

What scholarship data does BFS provide?
→ bfs_education_stats(topic="grants")

# Population
What is the population of the canton of Zurich broken down by age (0–18)?
→ bfs_population(region="Zürich", breakdown="age")

How has Switzerland's population developed by sex?
→ bfs_population(breakdown="sex")

# Topic exploration
Which tables exist on the topic of social assistance?
→ bfs_list_tables_by_theme(theme_code="13")

Is there data on school buildings?
→ bfs_search_tables(query="Schulliegenschaften")

What subject areas does BFS offer?
→ bfs_list_themes()

# Cantonal comparison
Compare the social assistance rate across all cantons for 2022.
→ bfs_compare_cantons(table_id="13.2.2.3", variable="Kanton", year="2022")
```

---

## Data Source

| Property | Details |
|---|---|
| **API** | STAT-TAB PxWeb API v1 |
| **Endpoint** | `https://www.pxweb.bfs.admin.ch/api/v1/` |
| **Provider** | Swiss Federal Statistical Office (BFS) |
| **Datasets** | 682 tables across 21 thematic areas |
| **Languages** | German (`de`), French (`fr`), Italian (`it`), English (`en`) |
| **Licence** | Open Government Data (OGD) — [BFS Terms of Use](https://www.bfs.admin.ch/bfs/en/home/grundlagen/nutzungsbedingungen.html) |
| **Authentication** | None — fully public |

---

## Themes

| Code | Theme | Code | Theme |
|---|---|---|---|
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

## Installation

### Prerequisites

- Python ≥ 3.11
- `uvx` (recommended) or `pip`

### Claude Desktop

Open the configuration file:

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

Restart Claude Desktop — the server is immediately available.

### Cursor / Windsurf / VS Code + Continue

The configuration syntax is identical to Claude Desktop. The file name depends on the client:

- **Cursor:** `.cursor/mcp.json` in the project folder, or `~/.cursor/mcp.json` globally
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

### LibreChat / Cline (SSE Transport)

For web-based or remotely hosted clients, use the SSE transport:

```bash
MCP_TRANSPORT=sse python -m swiss_statistics_mcp.server
# Starts on port 8052 (or $PORT if set)
```

Client configuration:

```json
{
  "mcpServers": {
    "swiss-statistics": {
      "url": "http://localhost:8052/sse"
    }
  }
}
```

### Local Development

```bash
git clone https://github.com/malkreide/swiss-statistics-mcp
cd swiss-statistics-mcp
pip install -e .
```

Claude Desktop config for local installation:

```json
{
  "mcpServers": {
    "swiss-statistics": {
      "command": "python",
      "args": ["-m", "swiss_statistics_mcp.server"],
      "env": {
        "PYTHONPATH": "/absolute/path/to/swiss-statistics-mcp/src"
      }
    }
  }
}
```

### Deployment on Render.com (SSE)

```bash
# Set environment variable
MCP_TRANSPORT=sse

# Start command
python -m swiss_statistics_mcp.server
```

The server binds to `$PORT` (set automatically by Render.com).

---

## Compatibility

This server implements the open [Model Context Protocol (MCP)](https://modelcontextprotocol.io) and is **model-agnostic** — it works with any MCP-compatible client, regardless of the underlying AI model.

| Client | Transport | Status |
|---|---|---|
| Claude Desktop | stdio | ✅ Supported |
| Cursor | stdio | ✅ Supported |
| Windsurf | stdio | ✅ Supported |
| VS Code + Continue | stdio | ✅ Supported |
| LibreChat | SSE | ✅ Supported |
| Cline | stdio | ✅ Supported |
| Self-hosted via mcp-proxy | SSE | ✅ Supported |

---

## Development and Testing

```bash
# Tests without network access (recommended for CI)
PYTHONPATH=src python -m pytest tests/ -m "not live"

# Live tests against the real BFS API
PYTHONPATH=src python -m pytest tests/ -m live -v

# Quick smoke test
PYTHONPATH=src python -c "
import asyncio
from swiss_statistics_mcp.server import bfs_list_themes
print(asyncio.run(bfs_list_themes()))
"
```

### CI/CD

The server uses GitHub Actions with a matrix across Python 3.11, 3.12 and 3.13. Every push and pull request is tested automatically (Ruff linting + pytest).

---

## Related Projects

Further Swiss open data MCP servers by [@malkreide](https://github.com/malkreide):

| Server | Description |
|---|---|
| [zurich-opendata-mcp](https://github.com/malkreide/zurich-opendata-mcp) | CKAN, weather, air quality, parking, City of Zurich council data |
| [fedlex-mcp](https://github.com/malkreide/fedlex-mcp) | Swiss federal law via Fedlex SPARQL |
| [swiss-transport-mcp](https://github.com/malkreide/swiss-transport-mcp) | OJP journey planning, SIRI-SX disruptions, fares |
| [swiss-road-mobility-mcp](https://github.com/malkreide/swiss-road-mobility-mcp) | Shared mobility, EV charging, traffic data |
| [global-education-mcp](https://github.com/malkreide/global-education-mcp) | UNESCO UIS and OECD Education at a Glance |
| [eth-library-mcp](https://github.com/malkreide/eth-library-mcp) | ETH Library catalogue search |
| [patent-mcp](https://github.com/malkreide/patent-mcp) | EPO Open Patent Services + IGE/Swissreg |

---

## Licence

MIT — see [LICENSE](LICENSE)

Data: Open Government Data (OGD) of the Swiss Federal Statistical Office (BFS). Usage subject to [BFS Terms of Use](https://www.bfs.admin.ch/bfs/en/home/grundlagen/nutzungsbedingungen.html).

---

*Developed by [@malkreide](https://github.com/malkreide) · Not officially affiliated with BFS · Contributions welcome*
