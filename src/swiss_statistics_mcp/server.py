"""
Swiss Statistics MCP Server
============================
Provides access to Swiss Federal Statistical Office (BFS) data
via the STAT-TAB PxWeb API (pxweb.bfs.admin.ch).

All 682 statistical datasets across 21 themes are accessible:
Bevölkerung, Bildung, Arbeit, Gesundheit, Politik, and more.

No authentication required. Open data under BFS usage terms.
"""

from __future__ import annotations

import json
import time
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BFS_API_BASE = "https://www.pxweb.bfs.admin.ch/api/v1"
DEFAULT_LANGUAGE = "de"
HTTP_TIMEOUT = 30.0
CATALOG_CACHE_TTL = 3600  # 1 hour

BFS_THEMES: dict[str, str] = {
    "01": "Bevölkerung",
    "02": "Raum und Umwelt",
    "03": "Arbeit und Erwerb",
    "04": "Volkswirtschaft",
    "05": "Preise",
    "06": "Industrie und Dienstleistungen",
    "07": "Land- und Forstwirtschaft",
    "08": "Energie",
    "09": "Bau- und Wohnungswesen",
    "10": "Tourismus",
    "11": "Mobilität und Verkehr",
    "12": "Geld, Banken, Versicherungen",
    "13": "Soziale Sicherheit",
    "14": "Gesundheit",
    "15": "Bildung und Wissenschaft",
    "16": "Kultur, Medien, Informationsgesellschaft",
    "17": "Politik",
    "18": "Öffentliche Verwaltung und Finanzen",
    "19": "Kriminalität und Strafrecht",
    "20": "Wirtschaftliche und soziale Situation",
    "21": "Nachhaltige Entwicklung",
}

# Curated high-value tables for Schulamt / education context
FEATURED_TABLES: dict[str, str] = {
    "px-x-1504000000_173": "Lehrkräfte nach Schuljahr, Kanton und Bildungsstufe",
    "px-x-1504000000_172": "Lehrkräfte nach Schuljahr, Kanton und Staatsangehörigkeit",
    "px-x-0102010000_101": "Ständige Wohnbevölkerung nach Kanton, Alter und Geschlecht",
    "px-x-1509090000_101": "Szenarien Sekundarstufe II: Entwicklung Schülerzahlen",
    "px-x-1509090000_113": "Szenarien Hochschulen: Entwicklung Studierendenzahlen",
    "px-x-1502020100_101": "Schülerinnen und Schüler nach Bildungsstufe und Kanton",
    "px-x-1503040100_101": "Abschlüsse Sekundarstufe II nach Kanton",
    "px-x-1506020000_114": "Stipendien und Darlehen nach Kanton",
    "px-x-1703030000_101": "Nationalratswahlen: Resultate nach Kanton",
    "px-x-1703030000_100": "Volksabstimmungen: Resultate",
    "px-x-0301000000_101": "Erwerbstätige nach Wirtschaftszweig",
    "px-x-1302020000_101": "Sozialhilfe: Quoten nach Kanton",
}

# ---------------------------------------------------------------------------
# In-memory catalog cache
# ---------------------------------------------------------------------------

_catalog_cache: dict[str, Any] = {}
_catalog_timestamp: float = 0.0


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

async def _get(url: str) -> Any:
    """Perform a GET request and return parsed JSON."""
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.json()


async def _post(url: str, body: dict[str, Any]) -> Any:
    """Perform a POST request and return parsed JSON."""
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        resp = await client.post(url, json=body)
        resp.raise_for_status()
        return resp.json()


def _theme_code_from_dbid(dbid: str) -> str:
    """Extract the 2-digit BFS theme code from a database ID.

    E.g. 'px-x-1504000000_173' → '15' (Bildung und Wissenschaft)
    """
    # Format: px-x-{THEME}{rest}_{suffix}
    # The numeric part starts after 'px-x-'
    numeric_part = dbid.replace("px-x-", "")
    return numeric_part[:2]


def _format_table_url(dbid: str, lang: str = DEFAULT_LANGUAGE) -> str:
    return f"{BFS_API_BASE}/{lang}/{dbid}/{dbid}.px"


def _build_data_url(dbid: str, lang: str = DEFAULT_LANGUAGE) -> str:
    return f"{BFS_API_BASE}/{lang}/{dbid}/{dbid}.px"


def _format_error(msg: str, hint: str = "") -> str:
    result = {"error": msg}
    if hint:
        result["hint"] = hint
    return json.dumps(result, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Catalog management
# ---------------------------------------------------------------------------

async def _ensure_catalog(lang: str = DEFAULT_LANGUAGE) -> dict[str, str]:
    """Return the full catalog {dbid: title}, with TTL-based caching.

    Since the PxWeb API doesn't support text search natively, we build
    a local index by fetching metadata for every table once per hour.
    This is done lazily when search_tables is called.
    """
    global _catalog_cache, _catalog_timestamp

    cache_key = f"catalog_{lang}"
    now = time.time()

    if cache_key in _catalog_cache and (now - _catalog_timestamp) < CATALOG_CACHE_TTL:
        return _catalog_cache[cache_key]

    # Fetch all database IDs
    url = f"{BFS_API_BASE}/{lang}/"
    all_dbs = await _get(url)

    catalog: dict[str, str] = {}
    # Fetch titles in batches to avoid overwhelming the API
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        for db in all_dbs:
            dbid = db["dbid"]
            try:
                meta_url = f"{BFS_API_BASE}/{lang}/{dbid}/{dbid}.px"
                resp = await client.get(meta_url)
                if resp.status_code == 200:
                    meta = resp.json()
                    catalog[dbid] = meta.get("title", dbid)
            except Exception:
                catalog[dbid] = dbid  # fallback to ID if metadata unavailable

    _catalog_cache[cache_key] = catalog
    _catalog_timestamp = now
    return catalog


# ---------------------------------------------------------------------------
# Pydantic input models
# ---------------------------------------------------------------------------

class ListThemesInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    lang: str = Field(
        default="de",
        description="Language code: 'de' (German), 'fr' (French), 'it' (Italian), 'en' (English)",
        pattern="^(de|fr|it|en)$",
    )


class ListTablesByThemeInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    theme_code: str = Field(
        ...,
        description=(
            "2-digit BFS theme code, e.g. '15' for Bildung, '01' for Bevölkerung. "
            "Use bfs_list_themes to see all codes."
        ),
        pattern="^\\d{2}$",
    )
    lang: str = Field(
        default="de",
        description="Language code: 'de', 'fr', 'it', 'en'",
        pattern="^(de|fr|it|en)$",
    )
    limit: int = Field(
        default=20,
        description="Maximum number of tables to return",
        ge=1,
        le=100,
    )


class SearchTablesInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(
        ...,
        description=(
            "Keyword(s) to search in table titles. Examples: 'Lehrkräfte', "
            "'Bevölkerung Kanton', 'Schüler Bildungsstufe', 'Abstimmung'"
        ),
        min_length=2,
        max_length=100,
    )
    theme_code: str | None = Field(
        default=None,
        description="Optional: filter to a specific theme code, e.g. '15' for Bildung",
        pattern="^\\d{2}$",
    )
    lang: str = Field(
        default="de",
        description="Language code: 'de', 'fr', 'it', 'en'",
        pattern="^(de|fr|it|en)$",
    )
    limit: int = Field(
        default=10,
        description="Maximum number of results to return",
        ge=1,
        le=50,
    )


class GetTableMetadataInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    table_id: str = Field(
        ...,
        description=(
            "BFS table/database ID, e.g. 'px-x-1504000000_173'. "
            "Obtain from bfs_search_tables or bfs_list_tables_by_theme."
        ),
        min_length=5,
    )
    lang: str = Field(
        default="de",
        description="Language code: 'de', 'fr', 'it', 'en'",
        pattern="^(de|fr|it|en)$",
    )


class DimensionFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str = Field(..., description="Variable code from table metadata, e.g. 'Kanton'")
    values: list[str] = Field(
        ...,
        description=(
            "List of value codes to include. Get codes from bfs_get_table_metadata. "
            "Example: ['1', '2'] for Zürich and Bern"
        ),
        min_length=1,
    )


class GetDataInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    table_id: str = Field(
        ...,
        description="BFS table ID, e.g. 'px-x-1504000000_173'",
        min_length=5,
    )
    filters: list[DimensionFilter] | None = Field(
        default=None,
        description=(
            "Optional dimension filters to narrow results. "
            "Without filters, all combinations are returned (may be large). "
            "Each filter specifies a variable code and the values to include."
        ),
    )
    lang: str = Field(
        default="de",
        description="Language code: 'de', 'fr', 'it', 'en'",
        pattern="^(de|fr|it|en)$",
    )
    max_rows: int = Field(
        default=500,
        description="Maximum number of data rows to return (safety limit)",
        ge=1,
        le=5000,
    )


class GetEducationStatsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    topic: str = Field(
        ...,
        description=(
            "Education topic to retrieve: "
            "'teachers' (Lehrkräfte nach Kanton), "
            "'students' (Schüler nach Bildungsstufe), "
            "'scenarios' (Szenarien Schülerzahlen Sek II), "
            "'scholarships' (Stipendien nach Kanton)"
        ),
        pattern="^(teachers|students|scenarios|scholarships)$",
    )
    canton: str | None = Field(
        default=None,
        description=(
            "Optional canton filter. Use canton name or index value from metadata. "
            "Examples: 'Zürich' → value '1', 'Bern / Berne' → '2'. "
            "Leave empty for all cantons."
        ),
    )
    lang: str = Field(
        default="de",
        description="Language code: 'de', 'fr', 'it', 'en'",
        pattern="^(de|fr|it|en)$",
    )


class GetPopulationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    region: str = Field(
        default="Schweiz",
        description=(
            "Region to query. Options: 'Schweiz' (national), "
            "or a canton name like 'Zürich', 'Bern / Berne', 'Luzern'. "
            "Use the exact name from BFS metadata."
        ),
    )
    year: str | None = Field(
        default=None,
        description="Year to filter, e.g. '2024'. Leave empty for all available years.",
    )
    breakdown: str = Field(
        default="total",
        description=(
            "Breakdown type: 'total' (all ages combined), "
            "'age' (by single year of age), "
            "'gender' (by gender)"
        ),
        pattern="^(total|age|gender)$",
    )


class CompareCantonsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    table_id: str = Field(
        ...,
        description="BFS table ID to compare across cantons",
        min_length=5,
    )
    canton_values: list[str] = Field(
        ...,
        description=(
            "List of canton value codes to compare. "
            "Get codes from bfs_get_table_metadata. "
            "Example: ['1', '2', '3'] for ZH, BE, LU. "
            "Use value '0' for Switzerland total."
        ),
        min_length=2,
        max_length=27,
    )
    additional_filters: list[DimensionFilter] | None = Field(
        default=None,
        description="Optional additional dimension filters beyond canton selection",
    )
    lang: str = Field(
        default="de",
        description="Language code: 'de', 'fr', 'it', 'en'",
        pattern="^(de|fr|it|en)$",
    )


# ---------------------------------------------------------------------------
# Response formatting helpers
# ---------------------------------------------------------------------------

def _format_jsonstat2_as_table(data: dict[str, Any], max_rows: int = 500) -> dict[str, Any]:
    """Convert JSON-stat2 response to a readable table format."""
    dimensions = data.get("id", [])
    dimension_info = data.get("dimension", {})
    values = data.get("value", [])
    size = data.get("size", [])

    # Build label lookups for each dimension
    dim_labels: list[list[tuple[str, str]]] = []
    for dim_id in dimensions:
        dim_data = dimension_info.get(dim_id, {})
        cats = dim_data.get("category", {})
        index_map = cats.get("index", {})
        label_map = cats.get("label", {})

        if isinstance(index_map, dict):
            # index_map: {value_code: position}
            ordered = sorted(index_map.items(), key=lambda x: x[1])
            pairs = [(code, label_map.get(code, code)) for code, _ in ordered]
        else:
            # index_map is a list
            pairs = [(code, label_map.get(code, code)) for code in index_map]

        if not pairs:
            # Fallback: use label map directly
            pairs = list(label_map.items())

        dim_labels.append(pairs)

    # Generate all combinations
    import itertools
    combos = list(itertools.product(*dim_labels))

    rows = []
    for i, (combo, value) in enumerate(zip(combos, values)):
        if i >= max_rows:
            break
        row: dict[str, str | float | None] = {}
        for dim_id, (code, label) in zip(dimensions, combo):
            row[dim_id] = label
        row["Wert"] = value
        rows.append(row)

    return {
        "title": data.get("label", ""),
        "source": data.get("source", "BFS"),
        "updated": data.get("updated", ""),
        "dimensions": [
            {
                "id": dim_id,
                "label": dimension_info.get(dim_id, {}).get("label", dim_id),
                "n_values": sz,
            }
            for dim_id, sz in zip(dimensions, size)
        ],
        "total_rows": len(values),
        "returned_rows": len(rows),
        "rows": rows,
    }


# ---------------------------------------------------------------------------
# MCP Server
# ---------------------------------------------------------------------------

mcp = FastMCP(
    "swiss_statistics_mcp",
    instructions=(
        "Access Swiss Federal Statistical Office (BFS/OFS/UST) data via STAT-TAB. "
        "Available: 682 datasets across 21 themes. No API key required. "
        "Workflow: (1) bfs_list_themes to see themes, (2) bfs_search_tables or "
        "bfs_list_tables_by_theme to find datasets, (3) bfs_get_table_metadata to "
        "understand variables and valid filter values, (4) bfs_get_data to retrieve "
        "actual statistics. Use bfs_education_stats for Schulamt-relevant shortcuts."
    ),
)


# ---------------------------------------------------------------------------
# Tool: List themes
# ---------------------------------------------------------------------------

@mcp.tool(
    name="bfs_list_themes",
    annotations={
        "title": "BFS Statistical Themes",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def bfs_list_themes(params: ListThemesInput) -> str:
    """List all 21 BFS statistical themes with their codes and dataset counts.

    Returns the complete taxonomy of Swiss federal statistics. Each theme has
    a 2-digit code used to filter datasets with bfs_list_tables_by_theme.

    Args:
        params (ListThemesInput):
            - lang (str): Language code ('de', 'fr', 'it', 'en')

    Returns:
        str: JSON with theme codes, names, and dataset counts per theme.
    """
    try:
        url = f"{BFS_API_BASE}/{params.lang}/"
        all_dbs = await _get(url)

        # Count tables per theme
        theme_counts: dict[str, int] = {code: 0 for code in BFS_THEMES}
        for db in all_dbs:
            code = _theme_code_from_dbid(db["dbid"])
            if code in theme_counts:
                theme_counts[code] += 1

        themes = [
            {
                "code": code,
                "name": name,
                "dataset_count": theme_counts.get(code, 0),
                "filter_hint": f"Use theme_code='{code}' in bfs_list_tables_by_theme",
            }
            for code, name in BFS_THEMES.items()
        ]

        return json.dumps(
            {
                "total_datasets": len(all_dbs),
                "themes": themes,
                "note": (
                    "Use bfs_list_tables_by_theme(theme_code='15') for Bildung, "
                    "bfs_search_tables(query='Lehrpersonen') for keyword search."
                ),
            },
            ensure_ascii=False,
            indent=2,
        )
    except httpx.HTTPStatusError as e:
        return _format_error(
            f"API-Fehler {e.response.status_code}",
            "BFS STAT-TAB API nicht erreichbar. Bitte später nochmals versuchen.",
        )
    except Exception as e:
        return _format_error(f"Unerwarteter Fehler: {type(e).__name__}: {e}")


# ---------------------------------------------------------------------------
# Tool: List tables by theme
# ---------------------------------------------------------------------------

@mcp.tool(
    name="bfs_list_tables_by_theme",
    annotations={
        "title": "BFS Tables by Theme",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def bfs_list_tables_by_theme(params: ListTablesByThemeInput) -> str:
    """List available statistical tables for a specific BFS theme.

    Returns table IDs and titles for a given theme code. Use the returned
    table_id values with bfs_get_table_metadata and bfs_get_data.

    Args:
        params (ListTablesByThemeInput):
            - theme_code (str): 2-digit theme code, e.g. '15' for Bildung
            - lang (str): Language code
            - limit (int): Max tables to return (default 20)

    Returns:
        str: JSON with list of {table_id, title, last_updated} for the theme.
    """
    try:
        url = f"{BFS_API_BASE}/{params.lang}/"
        all_dbs = await _get(url)

        # Filter by theme
        theme_dbs = [
            db for db in all_dbs
            if _theme_code_from_dbid(db["dbid"]) == params.theme_code
        ]

        if not theme_dbs:
            available = list(BFS_THEMES.keys())
            return _format_error(
                f"Kein Thema mit Code '{params.theme_code}' gefunden.",
                f"Verfügbare Codes: {available}. Verwende bfs_list_themes für die vollständige Liste.",
            )

        theme_name = BFS_THEMES.get(params.theme_code, params.theme_code)

        # Fetch titles for subset
        tables = []
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            for db in theme_dbs[: params.limit]:
                dbid = db["dbid"]
                try:
                    meta_url = _format_table_url(dbid, params.lang)
                    resp = await client.get(meta_url)
                    if resp.status_code == 200:
                        meta = resp.json()
                        tables.append(
                            {
                                "table_id": dbid,
                                "title": meta.get("title", dbid),
                                "last_updated": meta.get("updated", ""),
                                "n_variables": len(meta.get("variables", [])),
                                "featured": dbid in FEATURED_TABLES,
                            }
                        )
                    else:
                        tables.append({"table_id": dbid, "title": dbid})
                except Exception:
                    tables.append({"table_id": dbid, "title": dbid})

        return json.dumps(
            {
                "theme_code": params.theme_code,
                "theme_name": theme_name,
                "total_in_theme": len(theme_dbs),
                "returned": len(tables),
                "tables": tables,
                "next_step": (
                    "Verwende bfs_get_table_metadata(table_id='...') "
                    "um Variablen und Filter-Werte zu sehen."
                ),
            },
            ensure_ascii=False,
            indent=2,
        )
    except httpx.HTTPStatusError as e:
        return _format_error(f"API-Fehler {e.response.status_code}")
    except Exception as e:
        return _format_error(f"Fehler: {type(e).__name__}: {e}")


# ---------------------------------------------------------------------------
# Tool: Search tables
# ---------------------------------------------------------------------------

@mcp.tool(
    name="bfs_search_tables",
    annotations={
        "title": "Search BFS Tables",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": False,
    },
)
async def bfs_search_tables(params: SearchTablesInput) -> str:
    """Search for BFS statistical tables by keyword in their titles.

    Performs a full-text search across all 682+ BFS table titles.
    Results include table IDs needed for bfs_get_table_metadata and bfs_get_data.

    Note: First call builds a catalog (~682 API requests). Subsequent calls
    within 1 hour use the cached catalog and are instant.

    Args:
        params (SearchTablesInput):
            - query (str): Search keywords, e.g. 'Lehrkräfte', 'Schüler Kanton'
            - theme_code (Optional[str]): Filter by theme, e.g. '15'
            - lang (str): Language for table titles
            - limit (int): Max results (default 10)

    Returns:
        str: JSON with matching tables including IDs, titles, themes, and update dates.
    """
    try:
        catalog = await _ensure_catalog(params.lang)

        query_lower = params.query.lower()
        query_terms = query_lower.split()

        results = []
        for dbid, title in catalog.items():
            # Filter by theme if specified
            if params.theme_code:
                if _theme_code_from_dbid(dbid) != params.theme_code:
                    continue

            # Match all query terms in title
            title_lower = title.lower()
            if all(term in title_lower for term in query_terms):
                theme_code = _theme_code_from_dbid(dbid)
                results.append(
                    {
                        "table_id": dbid,
                        "title": title,
                        "theme_code": theme_code,
                        "theme_name": BFS_THEMES.get(theme_code, theme_code),
                        "featured": dbid in FEATURED_TABLES,
                    }
                )

        results = results[: params.limit]

        return json.dumps(
            {
                "query": params.query,
                "total_matches": len(results),
                "results": results,
                "next_step": (
                    "Verwende bfs_get_table_metadata(table_id='...') "
                    "um die Variablen einer Tabelle zu sehen."
                ),
            },
            ensure_ascii=False,
            indent=2,
        )
    except httpx.HTTPStatusError as e:
        return _format_error(f"API-Fehler {e.response.status_code}")
    except Exception as e:
        return _format_error(f"Fehler beim Aufbau des Katalogs: {type(e).__name__}: {e}")


# ---------------------------------------------------------------------------
# Tool: Get table metadata
# ---------------------------------------------------------------------------

@mcp.tool(
    name="bfs_get_table_metadata",
    annotations={
        "title": "BFS Table Metadata",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def bfs_get_table_metadata(params: GetTableMetadataInput) -> str:
    """Get metadata for a BFS table: title, variables, and available filter values.

    Essential step before calling bfs_get_data. Returns all dimension variables
    with their codes and value labels needed to construct data queries.

    Args:
        params (GetTableMetadataInput):
            - table_id (str): BFS table ID, e.g. 'px-x-1504000000_173'
            - lang (str): Language for labels

    Returns:
        str: JSON with table title, source, update date, and all variables with
             their codes and value options. Use variable codes in bfs_get_data filters.

    Example output structure:
        {
          "title": "Lehrkräfte nach Schuljahr, Kanton...",
          "variables": [
            {
              "code": "Schuljahr",
              "label": "Schuljahr",
              "n_values": 14,
              "values": [{"code": "0", "label": "2010/11"}, ...]
            }
          ]
        }
    """
    try:
        url = _format_table_url(params.table_id, params.lang)
        meta = await _get(url)

        variables = []
        for var in meta.get("variables", []):
            values = [
                {"code": code, "label": label}
                for code, label in zip(
                    var.get("values", []),
                    var.get("valueTexts", var.get("values", [])),
                )
            ]
            variables.append(
                {
                    "code": var.get("code", ""),
                    "label": var.get("text", ""),
                    "n_values": len(values),
                    "values": values[:30],  # show first 30 to keep response manageable
                    "more_values": max(0, len(values) - 30),
                }
            )

        theme_code = _theme_code_from_dbid(params.table_id)

        return json.dumps(
            {
                "table_id": params.table_id,
                "title": meta.get("title", ""),
                "source": meta.get("source", "BFS"),
                "last_updated": meta.get("updated", ""),
                "theme_code": theme_code,
                "theme_name": BFS_THEMES.get(theme_code, ""),
                "language": params.lang,
                "n_variables": len(variables),
                "variables": variables,
                "usage_hint": (
                    "Verwende 'code' der Variable und 'code' der gewünschten Werte "
                    "als Filter in bfs_get_data. Beispiel: "
                    f"filters=[{{\"code\": \"{variables[0]['code'] if variables else 'Variable'}\", "
                    f"\"values\": [\"{variables[0]['values'][0]['code'] if variables and variables[0]['values'] else '0'}\"]}}]"
                ),
            },
            ensure_ascii=False,
            indent=2,
        )
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            return _format_error(
                f"Tabelle '{params.table_id}' nicht gefunden.",
                "Verwende bfs_search_tables oder bfs_list_tables_by_theme um gültige IDs zu finden.",
            )
        return _format_error(f"API-Fehler {e.response.status_code}")
    except Exception as e:
        return _format_error(f"Fehler: {type(e).__name__}: {e}")


# ---------------------------------------------------------------------------
# Tool: Get data
# ---------------------------------------------------------------------------

@mcp.tool(
    name="bfs_get_data",
    annotations={
        "title": "Get BFS Statistical Data",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def bfs_get_data(params: GetDataInput) -> str:
    """Query statistical data from a BFS table with optional filters.

    Fetches actual data values from a STAT-TAB table. Always call
    bfs_get_table_metadata first to understand available variables and values.

    Args:
        params (GetDataInput):
            - table_id (str): BFS table ID
            - filters (Optional[list]): Dimension filters to narrow results.
              Each filter: {"code": "VariableCode", "values": ["val1", "val2"]}
              Without filters, all data is returned (may be very large).
            - lang (str): Language for labels
            - max_rows (int): Safety limit on returned rows (default 500)

    Returns:
        str: JSON with table title, dimension info, and data rows.
             Each row contains one value per dimension combination.

    Example:
        bfs_get_data(table_id='px-x-1504000000_173',
                     filters=[{"code": "Kanton", "values": ["1"]},
                              {"code": "Schuljahr", "values": ["13"]}])
    """
    try:
        url = _build_data_url(params.table_id, params.lang)

        # Build PxWeb query
        query: list[dict[str, Any]] = []
        if params.filters:
            for f in params.filters:
                query.append(
                    {
                        "code": f.code,
                        "selection": {"filter": "item", "values": f.values},
                    }
                )

        body = {"query": query, "response": {"format": "json-stat2"}}
        data = await _post(url, body)

        result = _format_jsonstat2_as_table(data, max_rows=params.max_rows)

        if result["total_rows"] > params.max_rows:
            result["warning"] = (
                f"Datenmenge auf {params.max_rows} Zeilen begrenzt "
                f"(total: {result['total_rows']}). "
                "Verwende Filter um die Datenmenge einzuschränken."
            )

        return json.dumps(result, ensure_ascii=False, indent=2)

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            return _format_error(
                f"Tabelle '{params.table_id}' nicht gefunden.",
                "Prüfe die table_id mit bfs_search_tables.",
            )
        if e.response.status_code == 400:
            return _format_error(
                "Ungültige Abfrage (HTTP 400).",
                (
                    "Prüfe ob die Filter-Codes und -Werte korrekt sind. "
                    "Verwende bfs_get_table_metadata um gültige Codes zu erhalten."
                ),
            )
        return _format_error(f"API-Fehler {e.response.status_code}: {e.response.text[:200]}")
    except Exception as e:
        return _format_error(f"Fehler: {type(e).__name__}: {e}")


# ---------------------------------------------------------------------------
# Tool: Education stats (Schulamt convenience)
# ---------------------------------------------------------------------------

EDUCATION_TOPIC_MAP: dict[str, dict[str, Any]] = {
    "teachers": {
        "table_id": "px-x-1504000000_173",
        "description": "Lehrkräfte nach Schuljahr, Kanton, Beschäftigungsgrad und Bildungsstufe",
        "canton_var": "Kanton",
        "canton_all_value": "0",
    },
    "students": {
        "table_id": "px-x-1502020100_101",
        "description": "Schülerinnen und Schüler nach Bildungsstufe und Kanton",
        "canton_var": "Kanton",
        "canton_all_value": "0",
    },
    "scenarios": {
        "table_id": "px-x-1509090000_101",
        "description": "Szenarien 2022-2031: Entwicklung Schülerzahlen Sekundarstufe II",
        "canton_var": "Kanton",
        "canton_all_value": "0",
    },
    "scholarships": {
        "table_id": "px-x-1506020000_114",
        "description": "Stipendien und Darlehen nach Kanton",
        "canton_var": "Kanton",
        "canton_all_value": "0",
    },
}

CANTON_NAME_TO_VALUE: dict[str, str] = {
    "Schweiz": "0",
    "Zürich": "1",
    "Bern / Berne": "2",
    "Luzern": "3",
    "Uri": "4",
    "Schwyz": "5",
    "Obwalden": "6",
    "Nidwalden": "7",
    "Glarus": "8",
    "Zug": "9",
    "Freiburg / Fribourg": "10",
    "Solothurn": "11",
    "Basel-Stadt": "12",
    "Basel-Landschaft": "13",
    "Schaffhausen": "14",
    "Appenzell Ausserrhoden": "15",
    "Appenzell Innerrhoden": "16",
    "St. Gallen": "17",
    "Graubünden / Grigioni / Grischun": "18",
    "Aargau": "19",
    "Thurgau": "20",
    "Ticino": "21",
    "Vaud": "22",
    "Valais / Wallis": "23",
    "Neuchâtel": "24",
    "Genève": "25",
    "Jura": "26",
}

# Population table uses cantonal abbreviations (BFS codes), not numeric indices
CANTON_POPULATION_CODE: dict[str, str] = {
    "Schweiz": "8100",
    "Zürich": "ZH",
    "Bern / Berne": "BE",
    "Luzern": "LU",
    "Uri": "UR",
    "Schwyz": "SZ",
    "Obwalden": "OW",
    "Nidwalden": "NW",
    "Glarus": "GL",
    "Zug": "ZG",
    "Fribourg / Freiburg": "FR",
    "Solothurn": "SO",
    "Basel-Stadt": "BS",
    "Basel-Landschaft": "BL",
    "Schaffhausen": "SH",
    "Appenzell Ausserrhoden": "AR",
    "Appenzell Innerrhoden": "AI",
    "St. Gallen": "SG",
    "Graubünden / Grigioni / Grischun": "GR",
    "Aargau": "AG",
    "Thurgau": "TG",
    "Ticino": "TI",
    "Vaud": "VD",
    "Valais / Wallis": "VS",
    "Neuchâtel": "NE",
    "Genève": "GE",
    "Jura": "JU",
}


@mcp.tool(
    name="bfs_education_stats",
    annotations={
        "title": "Swiss Education Statistics",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def bfs_education_stats(params: GetEducationStatsInput) -> str:
    """Retrieve Swiss education statistics — convenience tool for Schulamt context.

    Provides direct access to key education datasets without needing to know
    table IDs or variable codes. Covers teachers, students, enrollment scenarios,
    and scholarship data, optionally filtered by canton.

    Args:
        params (GetEducationStatsInput):
            - topic (str): One of: 'teachers', 'students', 'scenarios', 'scholarships'
            - canton (Optional[str]): Canton name, e.g. 'Zürich'. None = all cantons.
            - lang (str): Language code

    Returns:
        str: JSON with education statistics for the selected topic and canton.
             Includes table metadata and data rows.
    """
    topic_cfg = EDUCATION_TOPIC_MAP[params.topic]
    table_id: str = topic_cfg["table_id"]
    canton_var: str = topic_cfg["canton_var"]

    # Resolve canton to value code
    canton_value: str | None = None
    if params.canton:
        # Try exact match first, then partial match
        canton_value = CANTON_NAME_TO_VALUE.get(params.canton)
        if canton_value is None:
            for name, val in CANTON_NAME_TO_VALUE.items():
                if params.canton.lower() in name.lower():
                    canton_value = val
                    break
        if canton_value is None:
            return _format_error(
                f"Kanton '{params.canton}' nicht gefunden.",
                f"Gültige Kantone: {list(CANTON_NAME_TO_VALUE.keys())}",
            )

    try:
        url = _build_data_url(table_id, params.lang)

        query: list[dict[str, Any]] = []
        if canton_value is not None:
            query.append(
                {
                    "code": canton_var,
                    "selection": {"filter": "item", "values": [canton_value]},
                }
            )

        body = {"query": query, "response": {"format": "json-stat2"}}
        data = await _post(url, body)

        result = _format_jsonstat2_as_table(data, max_rows=500)
        result["topic"] = params.topic
        result["topic_description"] = topic_cfg["description"]
        result["table_id"] = table_id
        if params.canton:
            result["canton_filter"] = params.canton

        return json.dumps(result, ensure_ascii=False, indent=2)

    except httpx.HTTPStatusError as e:
        return _format_error(
            f"API-Fehler {e.response.status_code}",
            "Tabelle möglicherweise aktuell nicht verfügbar. Bitte später nochmals versuchen.",
        )
    except Exception as e:
        return _format_error(f"Fehler: {type(e).__name__}: {e}")


# ---------------------------------------------------------------------------
# Tool: Population data
# ---------------------------------------------------------------------------

@mcp.tool(
    name="bfs_population",
    annotations={
        "title": "Swiss Population Statistics",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def bfs_population(params: GetPopulationInput) -> str:
    """Retrieve Swiss population statistics by region, year, and breakdown.

    Accesses the core BFS population dataset (ständige Wohnbevölkerung)
    with flexible filtering by canton/municipality, year, age, and gender.
    Critical for school space planning and demographic projections.

    Args:
        params (GetPopulationInput):
            - region (str): 'Schweiz', or canton name like 'Zürich'
            - year (Optional[str]): Year filter, e.g. '2024'
            - breakdown (str): 'total', 'age', or 'gender'

    Returns:
        str: JSON with population figures for the selected region and breakdown.
    """
    TABLE_ID = "px-x-0102010000_101"

    # Map region to canton code (population table uses BFS abbreviations: ZH, BE, etc.)
    region_value = CANTON_POPULATION_CODE.get(params.region)
    if region_value is None:
        for name, val in CANTON_POPULATION_CODE.items():
            if params.region.lower() in name.lower():
                region_value = val
                break

    if region_value is None:
        return _format_error(
            f"Region '{params.region}' nicht gefunden.",
            "Verwende 'Schweiz' oder einen Kantonnamen wie 'Zürich', 'Bern / Berne'.",
        )

    canton_code = region_value

    try:
        url = _build_data_url(TABLE_ID, "de")

        # Build filters based on breakdown
        query: list[dict[str, Any]] = [
            {
                "code": "Kanton (-) / Bezirk (>>) / Gemeinde (......)",
                "selection": {"filter": "item", "values": [canton_code]},
            },
            {
                "code": "Bevölkerungstyp",
                "selection": {"filter": "item", "values": ["1"]},  # Ständige Wohnbevölkerung
            },
        ]

        # Nationality: total
        query.append(
            {
                "code": "Staatsangehörigkeit (Kategorie)",
                "selection": {"filter": "item", "values": ["-99999"]},  # Total
            }
        )

        if params.breakdown == "total":
            query.append(
                {"code": "Geschlecht", "selection": {"filter": "item", "values": ["-99999"]}}
            )
            query.append(
                {"code": "Alter", "selection": {"filter": "item", "values": ["-99999"]}}
            )
        elif params.breakdown == "gender":
            query.append(
                {"code": "Geschlecht", "selection": {"filter": "item", "values": ["1", "2"]}}
            )
            query.append(
                {"code": "Alter", "selection": {"filter": "item", "values": ["-99999"]}}
            )
        elif params.breakdown == "age":
            query.append(
                {"code": "Geschlecht", "selection": {"filter": "item", "values": ["-99999"]}}
            )
            # Age groups: 0-18 for school planning context
            age_values = [str(i) for i in range(19)]
            query.append(
                {"code": "Alter", "selection": {"filter": "item", "values": age_values}}
            )

        if params.year:
            query.append(
                {"code": "Jahr", "selection": {"filter": "item", "values": [params.year]}}
            )

        body = {"query": query, "response": {"format": "json-stat2"}}
        data = await _post(url, body)

        result = _format_jsonstat2_as_table(data, max_rows=200)
        result["region"] = params.region
        result["breakdown"] = params.breakdown
        result["table_id"] = TABLE_ID
        result["note"] = (
            "Ständige Wohnbevölkerung. "
            "Für Schulraumplanung empfiehlt sich breakdown='age' für Altersgruppen 0-18."
        )

        return json.dumps(result, ensure_ascii=False, indent=2)

    except httpx.HTTPStatusError as e:
        return _format_error(f"API-Fehler {e.response.status_code}")
    except Exception as e:
        return _format_error(f"Fehler: {type(e).__name__}: {e}")


# ---------------------------------------------------------------------------
# Tool: Compare cantons
# ---------------------------------------------------------------------------

@mcp.tool(
    name="bfs_compare_cantons",
    annotations={
        "title": "Compare Swiss Cantons",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def bfs_compare_cantons(params: CompareCantonsInput) -> str:
    """Compare a BFS statistical indicator across multiple Swiss cantons.

    Designed for KI-Fachgruppe demos and benchmarking. Fetches the same
    dataset for multiple cantons simultaneously, enabling direct comparison.

    Args:
        params (CompareCantonsInput):
            - table_id (str): BFS table ID to query
            - canton_values (list[str]): Canton value codes to compare.
              Use '0' for Switzerland total, '1' for Zürich, '2' for Bern, etc.
              Get codes via bfs_get_table_metadata on any canton-level table.
            - additional_filters (Optional[list]): Extra dimension filters
            - lang (str): Language code

    Returns:
        str: JSON with data for all selected cantons side by side.

    Example use case:
        Compare teacher-to-student ratios across ZH, BE, LU, CH total:
        canton_values=['0', '1', '2', '3']
    """
    try:
        url = _build_data_url(params.table_id, params.lang)

        # Build query with canton filter
        query: list[dict[str, Any]] = []

        # Find canton variable name from metadata first
        meta_url = _format_table_url(params.table_id, params.lang)
        meta = await _get(meta_url)

        canton_var_code = None
        for var in meta.get("variables", []):
            var_code = var.get("code", "").lower()
            if "kanton" in var_code:
                canton_var_code = var["code"]
                break

        if canton_var_code is None:
            return _format_error(
                "Keine Kanton-Variable in dieser Tabelle gefunden.",
                f"Verfügbare Variablen: {[v['code'] for v in meta.get('variables', [])]}",
            )

        query.append(
            {
                "code": canton_var_code,
                "selection": {"filter": "item", "values": params.canton_values},
            }
        )

        if params.additional_filters:
            for f in params.additional_filters:
                query.append(
                    {
                        "code": f.code,
                        "selection": {"filter": "item", "values": f.values},
                    }
                )

        body = {"query": query, "response": {"format": "json-stat2"}}
        data = await _post(url, body)

        result = _format_jsonstat2_as_table(data, max_rows=500)
        result["table_id"] = params.table_id
        result["cantons_compared"] = params.canton_values
        result["canton_variable"] = canton_var_code

        return json.dumps(result, ensure_ascii=False, indent=2)

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 400:
            return _format_error(
                "Ungültige Anfrage. Prüfe ob die Kanton-Werte für diese Tabelle gültig sind.",
                "Verwende bfs_get_table_metadata um gültige Werte-Codes zu erhalten.",
            )
        return _format_error(f"API-Fehler {e.response.status_code}")
    except Exception as e:
        return _format_error(f"Fehler: {type(e).__name__}: {e}")


# ---------------------------------------------------------------------------
# Tool: Featured datasets
# ---------------------------------------------------------------------------

@mcp.tool(
    name="bfs_featured_datasets",
    annotations={
        "title": "BFS Featured Datasets",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def bfs_featured_datasets(params: ListThemesInput) -> str:
    """Return a curated list of high-value BFS datasets for Schulamt and public administration.

    Provides a shortlist of the most relevant datasets for education planning,
    demographic analysis, and political context — ideal as a starting point.

    Args:
        params (ListThemesInput):
            - lang (str): Language code

    Returns:
        str: JSON with curated table IDs, titles, themes, and recommended use cases.
    """
    featured = [
        {
            "table_id": tid,
            "title": FEATURED_TABLES[tid],
            "theme_code": _theme_code_from_dbid(tid),
            "theme_name": BFS_THEMES.get(_theme_code_from_dbid(tid), ""),
            "schulamt_relevanz": _schulamt_relevance(tid),
        }
        for tid in FEATURED_TABLES
    ]

    return json.dumps(
        {
            "total": len(featured),
            "featured_datasets": featured,
            "quick_start": (
                "Verwende bfs_education_stats(topic='teachers') für Lehrkräfte-Statistiken, "
                "bfs_population(region='Zürich', breakdown='age') für Altersstruktur in Zürich, "
                "oder bfs_get_table_metadata(table_id='px-x-1504000000_173') "
                "für detaillierte Lehrkräfte-Daten."
            ),
        },
        ensure_ascii=False,
        indent=2,
    )


def _schulamt_relevance(table_id: str) -> str:
    relevance_map = {
        "px-x-1504000000_173": "⭐⭐⭐ Kerndaten Lehrpersonenmangel – nach Kanton & Bildungsstufe",
        "px-x-1504000000_172": "⭐⭐⭐ Lehrpersonen nach Staatsangehörigkeit – Diversity-Analyse",
        "px-x-0102010000_101": "⭐⭐⭐ Schulraumplanung – Bevölkerung nach Alter & Gemeinde",
        "px-x-1509090000_101": "⭐⭐⭐ Prognosen Schülerzahlen Sek II bis 2031",
        "px-x-1509090000_113": "⭐⭐ Prognosen Hochschulen – Lehrpersonen-Nachwuchs",
        "px-x-1502020100_101": "⭐⭐⭐ Schülerbestände nach Bildungsstufe – Kantonsvergleich",
        "px-x-1503040100_101": "⭐⭐ Abschlüsse Sek II – Bildungsoutput-Analyse",
        "px-x-1506020000_114": "⭐⭐ Stipendien – Bildungsfinanzierung nach Kanton",
        "px-x-1703030000_101": "⭐ Nationalratswahlen – politischer Kontext",
        "px-x-1703030000_100": "⭐ Volksabstimmungen – demokratische Legitimation",
        "px-x-0301000000_101": "⭐⭐ Arbeitsmarkt – Rahmenbedingungen Personalrekrutierung",
        "px-x-1302020000_101": "⭐⭐ Sozialhilfe – sozialer Kontext Volksschule",
    }
    return relevance_map.get(table_id, "Relevant für öffentliche Verwaltung")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    if "--http" in sys.argv:
        port_idx = sys.argv.index("--port") + 1 if "--port" in sys.argv else None
        port     = int(sys.argv[port_idx]) if port_idx else 8000
        mcp.run(transport="streamable-http", port=port)
    else:
        mcp.run()
