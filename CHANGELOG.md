# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- **Capped `mcp` at `<2`.** `mcp` 2.0.0, published 2026-07-28, removed
  `mcp.server.fastmcp` — the module this server imports. With the previous
  unbounded `>=1.28.1` every fresh resolve picked 2.0.0 and failed at import
  with `ModuleNotFoundError`, in CI and for anyone running `pip install` alike.
  Verified in both directions: 2.0.0 fails, `<2` resolves to 1.29.0 and imports
  cleanly. Migrating to the 2.x API (`mcp.server.mcpserver`) stays a separate,
  deliberate piece of work.

## [0.6.0] - 2026-07-25

### Changed (BREAKING)
- **Consolidated `bfs_list_themes` + `bfs_list_tables_by_theme` into a single
  `bfs_browse_catalog(theme_code=None, lang="de", limit=20)`** → `BrowseCatalogResult`.
  This brings the server back to **15 tools** (from 16), under the portfolio's
  15-tool guideline.
    - Omit `theme_code` → **themes mode**: all 21 statistical themes with codes
      and per-theme dataset counts (`mode="themes"`, `themes`, `total_datasets`).
    - Provide `theme_code` → **tables mode**: the datasets in that theme
      (`mode="tables"`, `tables`, `theme_name`, `total_in_theme`, `returned`),
      with the same bounded parallel metadata fan-out as before.
  - **Migration:** `bfs_list_themes(lang=..)` → `bfs_browse_catalog(lang=..)`;
    `bfs_list_tables_by_theme(theme_code=.., lang=.., limit=..)` →
    `bfs_browse_catalog(theme_code=.., lang=.., limit=..)`. The result envelope
    is a superset of the two old models, keyed by `mode`.
  - Removed models `ListThemesResult` and `ListTablesByThemeResult` (replaced by
    `BrowseCatalogResult`) and `ListTablesByThemeInput` (replaced by
    `BrowseCatalogInput`). Alpha (0.x) allows breaking tool changes between minor
    versions.
- Internal hints, the server workflow instructions, README (EN + DE), and
  EXAMPLES updated to reference `bfs_browse_catalog`.

## [0.5.0] - 2026-07-25

### Added
- **`bfs_price_index(index, since_year=None)`** → `PriceIndexResult` — Swiss
  price indices that are **not** carried by STAT-TAB, sourced via
  opendata.swiss (CKAN) metadata + the BFS DAM asset API:
    - `baupreisindex`: the construction price index, returned as the parsed
      national semi-annual series (Schweiz, Baugewerbe Total) with its base
      period. The XLSX asset is selected from CKAN metadata by verifying the
      response `content-type` (PDFs skipped) and parsed with `openpyxl`.
    - `impi`: the residential property price index — BFS publishes it only as
      PDF/HTML, so the tool returns the official `source_links` plus an explicit
      limitation instead of parsed values.
- Results carry the `source` + `provenance` envelope and are cached for 24h
  (`MCP_PRICE_INDEX_TTL`). New dependency: `openpyxl>=3.1.0`.
- Reusable UA-aware HTTP helpers `_get_json_ua` / `_get_bytes_ua` that always
  send a custom `swiss-statistics-mcp/<version>` User-Agent.
- README (EN + DE): new **Price-index sources** table, a data-source row for the
  DAM/CKAN channel, an example query, and Known-Limitations entries.

### Known findings
- **CKAN 403-without-User-Agent:** `ckan.opendata.swiss` rejects default
  User-Agents with HTTP 403. Every CKAN/DAM call sends a custom User-Agent; a
  regression test asserts the header is present.
- **IMPI is not machine-readable.** The IMPI dataset on opendata.swiss exposes
  only PDF/HTML resources (no XLSX/CSV), and there is no STAT-TAB cube for it —
  so `index="impi"` is source-links-only by necessity, not choice.
- **DAM assets mix formats and change ids.** A single dataset carries PDF and
  XLSX assets under opaque numeric ids that change on republish; the tool
  resolves the XLSX live from CKAN metadata and validates it by content-type
  rather than hard-coding an asset id.
- **Tool count is now 16** (over the 15 guideline). The two catalog-navigation
  tools (`bfs_list_themes` + `bfs_list_tables_by_theme`) are the natural
  consolidation candidate if the surface needs to shrink.

## [0.4.0] - 2026-07-25

### Added
- **Construction & real-estate tools** (STAT-TAB theme 09, Bau- und Wohnungswesen):
    - `bfs_construction_activity(municipality_bfs, since_year=2015)` →
      `ConstructionActivityResult` — yearly new buildings
      (`px-x-0904030000_106`) and new dwellings broken down by number of rooms
      (`px-x-0904030000_105`) for a commune. Cross-validation hint points to
      `swiss-housing-mcp` for register states / the construction pipeline
      (deliberate redundancy).
    - `bfs_construction_investment(level, code, since_year=2015)` →
      `ConstructionInvestmentResult` — building investment and Arbeitsvorrat
      (the monetary leading indicator) from `px-x-0904010000_205`, by
      grossregion / kanton / gemeinde.
- Both results carry the `source` + `provenance` envelope (`live_api`) matching
  the reference layer. `bfs_construction_investment` reports its `unit`
  (`1000 CHF`).
- Reusable json-stat2 helpers `_iter_jsonstat2` / `_jsonstat2_label` that
  preserve value *codes* (not just labels) for robust code-based filtering.
- README (EN + DE): new **Construction sources** cube-ID table, construction
  example queries, and an **On the horizon** note for the planned `price_index`
  tool (IMPI / Baupreisindex via the DAM asset API).

### Known findings
- **PxWeb Gemeinde codes are not consistent across cubes.** In
  `px-x-0904030000_106`/`_107` the value code IS the zero-padded BFS number
  (`0261`); in `px-x-0904030000_105` it is an opaque sequential id (`160`) and
  the BFS number appears only in the label (`......0261 Zürich`). The geo
  resolver matches the label-embedded BFS number against each cube's own live
  dimension values — matching on the value code would silently pick the wrong
  commune.
- **The Gemeinde-level building series was restructured at 2012/2013.** The
  cubes named in the original scope (`px-x-0904030000_101`/`_104`) end in 2012;
  the current series (`_105`/`_106`/`_107`, 2013–) has a
  `Grossregion (<<) / Kanton (-) / Gemeinde (......)` dimension. Since the
  default `since_year` is 2015, the tools query the current cubes and accept
  `since_year >= 2013`.
- **IMPI / Baupreisindex are not in STAT-TAB** — they are DAM assets
  (`dam-api.bfs.admin.ch`) discovered via opendata.swiss (CKAN), which returns
  **HTTP 403** to default User-Agents and mixes PDF/XLSX asset formats. Deferred
  to a follow-up release (`price_index`) as the most fragile part of the surface.

## [0.3.0] - 2026-07-19

### Added
- **Reference layer** — four new tools that make the official BFS commune
  number the portfolio-wide join key:
    - `lookup_commune(name_or_bfs_number, valid_at_date)` → `LookupCommuneResult`
    - `resolve_historical_commune(bfs_number, from_date, to_date)` →
      `ResolveHistoricalCommuneResult` — maps a historical BFS number onto
      today's number(s) with the mutation path, for re-keying old statistics
      across fusions.
    - `list_communes(canton, valid_at_date)` → `ListCommunesResult`
    - `search_historical_series(topic, period)` → `SearchHistoricalSeriesResult`
- Two new upstream sources:
    - **BFS AGVCH commune register** via its REST service
      (`snapshot` / `correspondances` / `mutations`) — Architecture A
      (live-API-only) with a 24 h cache; reuses the shared retry policy.
    - **Historical Statistics of Switzerland (HSSO)** — Architecture C
      (dump-only); `search_historical_series` returns the stable XLSX URL.
- Reference-layer responses carry `source` + `provenance` (`live_api` |
  `cached`); HSSO responses additionally carry `licence_note` with the
  mandatory CC BY-NC-SA 3.0 NonCommercial notice.
- README **Join Keys** section documenting BFS commune number, EGID and
  canton abbreviation as portfolio-wide keys, plus an Architecture decision
  note and the fusion re-keying anchor query.

### Known findings
- The live AGVCH `snapshot` CSV header uses `Inscription,Radiation,Rec_Type_fr`,
  **not** the `Einschreibung,Streichung` names printed in `rest_api_de.pdf` —
  parse against the live header, not the doc.
- `HistoricalCode` is **not globally unique** across levels in a snapshot
  (e.g. `10078` is both ZH's *Bezirk Horgen* and VS's commune *Vionnaz*), so a
  commune's `Parent` link is disambiguated by tier when deriving its canton. A
  naive dict keyed on `HistoricalCode` silently mis-attributes cantons.
- HSSO exposes no per-table period filter; `search_historical_series`'s
  `period` argument is an informational hint only.

## [0.2.0] - 2026-05-20

### Changed (BREAKING)
- All 9 tools now return typed Pydantic models instead of JSON strings.
  FastMCP serializes these as structured content, so clients can read
  fields directly and follow-up calls can be typed against the output
  schema. Client code that previously called `json.loads(result)` should
  now access `result.field` (or `result.model_dump()` for a dict view).
  Affected tools and their result types:
    - `bfs_list_themes` → `ListThemesResult`
    - `bfs_list_tables_by_theme` → `ListTablesByThemeResult`
    - `bfs_search_tables` → `SearchTablesResult`
    - `bfs_get_table_metadata` → `TableMetadataResult`
    - `bfs_get_data` → `DataTableResult`
    - `bfs_education_stats` → `DataTableResult`
    - `bfs_population` → `DataTableResult`
    - `bfs_compare_cantons` → `DataTableResult`
    - `bfs_featured_datasets` → `FeaturedDatasetsResult`
  Addresses audit finding ARCH-005.

### Added
- Machine-readable truncation signal on data-returning tools:
  `truncated: bool`, `rows_total: int`, `rows_returned: int` are now
  first-class fields instead of being buried in a German `warning` prose
  string. The German message survives as the `note` field for human
  display. Addresses audit finding ARCH-009.
- Explicit error discrimination: every result type carries optional
  top-level `error: str | None` and `hint: str | None` fields. Clients
  check `result.error is None` to know the call succeeded; the data
  fields are None on error.

### Removed
- `_format_error()` helper — replaced by per-result-type error
  construction. The unified shape lives in each result class now.

### Security
- `table_id` input fields now enforce the BFS-canonical regex
  `^px-[a-z]-\d{8,12}_\d{1,4}$` instead of only a `min_length=5` check.
  Defense-in-depth: malformed identifiers are rejected at the Pydantic
  boundary before any URL interpolation, cache lookup, or log statement.
  Addresses audit finding SEC-008.
- CI now runs `bandit -r src/ -ll` (static security scan) and
  `pip-audit` (dependency CVE scan) as a dedicated `security` job
  on every push and PR. Addresses audit finding OPS-001.

### Documentation
- New README "Maturity" section (DE + EN) flags Alpha status and
  recommends pinning cloud deployments to git tags rather than `main`.
  Addresses audit finding OPS-003.

### Added
- Retry on transient BFS-API errors (`5xx`, `429`, network failures): up to
  3 attempts with exponential backoff (0.5s → 4s). 4xx errors surface
  immediately. Tunable via `MCP_RETRY_MAX_ATTEMPTS`, `MCP_RETRY_WAIT_INITIAL`,
  `MCP_RETRY_WAIT_MAX` env vars. New dependency: `tenacity>=8.0.0`.
  Addresses audit findings SEC-018, SCALE-002.
- In-memory metadata cache per `(table_id, lang)` with 1h TTL. Used by
  `bfs_get_table_metadata`, `bfs_list_tables_by_theme`, and
  `bfs_compare_cantons` — repeat queries return instantly. Addresses
  audit finding SCALE-003.
- `bfs_list_tables_by_theme` now fans out metadata fetches in parallel
  bounded by `FANOUT_CONCURRENCY = 5`. For `limit=20` this cuts wall-clock
  from ~20s sequential to ~4s while staying friendly to the upstream API.
  Addresses audit finding SCALE-004.

### Added
- Structured JSON logging on stderr: one `tool_start` and one `tool_end` event
  per tool call, with `rid` correlation id, `params_keys`, `status`,
  `duration_ms`, and `error_type` on failure. Level configurable via
  `MCP_LOG_LEVEL` (default `INFO`). Addresses audit findings OBS-001,
  OBS-002, OBS-003, SEC-014.

### Security
- Streamable-HTTP transport now binds to `127.0.0.1` by default instead of all
  interfaces. Set `MCP_HOST=0.0.0.0` or pass `--host 0.0.0.0` to expose on a
  container port; README documents the access-control requirements for cloud
  deployments. Addresses audit finding SDK-004.
- Tool error responses no longer interpolate raw exception messages. Generic
  catch-all blocks now log the full traceback server-side via
  `_LOGGER.exception()` and return a sanitized German error message with a
  remediation hint to the client. Previously the client received
  `f"Fehler: {type(e).__name__}: {e}"`, which could leak internal file paths,
  library versions, upstream payload excerpts, and request fragments.
  Addresses audit finding SEC-022.

### Changed
- The two silent fallback loops in catalog and table-list construction
  (server.py:256, 691) now emit `_LOGGER.warning(..., exc_info=True)` so
  BFS metadata-schema changes surface in logs instead of being masked.
  Addresses audit finding OBS-004.

### Fixed
- HTTP entrypoint passed `port=` to `mcp.run()`, which raises `TypeError` in
  current MCP SDK. Port is now set via `mcp.settings.port` before `run()`.

## [0.1.0] - 2026-03-29

### Added
- Initial release with 9 MCP tools for BFS STAT-TAB PxWeb API access
- Full catalog of 682 datasets across 21 themes
- Convenience tools: `bfs_education_stats`, `bfs_population`, `bfs_compare_cantons`
- Catalog search with TTL-based caching (1h)
- JSON-STAT2 response parsing with human-readable table output
- Dual transport: stdio (Claude Desktop) and Streamable HTTP (cloud)
- 39 unit/integration tests + 4 live smoke tests
- Bilingual documentation (English/German)
- GitHub Actions CI (Python 3.11, 3.12, 3.13)
