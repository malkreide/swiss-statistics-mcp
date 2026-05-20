# swiss-statistics-mcp v0.2.0 — Production-Ready Hardening

This release closes out all 16 findings from the [mcp-audit-skill v1.0.0](https://github.com/malkreide/mcp-audit-skill) audit. The server is now production-ready per the audit gate (44 / 44 applicable checks pass, 0 blocking findings).

> ⚠️ **BREAKING CHANGE.** Tools now return typed Pydantic models instead of JSON strings. Clients that previously called `json.loads(result)` should access `result.field` directly (or `result.model_dump()` for a dict view). See [Output schema](#output-schema) below.

---

## ⚠️ Breaking changes

### Tool returns are typed Pydantic models, not JSON strings *(ARCH-005)*

Every tool now returns its own result type. FastMCP serializes these as structured content, so clients can read fields directly and follow-up calls can be typed against the output schema.

| Tool | Old return | New return |
|---|---|---|
| `bfs_list_themes` | `str` (JSON) | `ListThemesResult` |
| `bfs_list_tables_by_theme` | `str` (JSON) | `ListTablesByThemeResult` |
| `bfs_search_tables` | `str` (JSON) | `SearchTablesResult` |
| `bfs_get_table_metadata` | `str` (JSON) | `TableMetadataResult` |
| `bfs_get_data` | `str` (JSON) | `DataTableResult` |
| `bfs_education_stats` | `str` (JSON) | `DataTableResult` |
| `bfs_population` | `str` (JSON) | `DataTableResult` |
| `bfs_compare_cantons` | `str` (JSON) | `DataTableResult` |
| `bfs_featured_datasets` | `str` (JSON) | `FeaturedDatasetsResult` |

```python
# Before (0.1.x)
result = await bfs_get_data(...)        # str
data = json.loads(result)
print(data["rows_total"])

# After (0.2.0)
result = await bfs_get_data(...)        # DataTableResult
print(result.rows_total)
print(result.truncated)                 # NEW: machine-readable
```

Every result carries top-level `error: str | None` and `hint: str | None` for explicit error discrimination — `result.error is None` means success.

---

## 🔒 Security

- **Streamable-HTTP binds to `127.0.0.1` by default** instead of all interfaces. Set `MCP_HOST=0.0.0.0` or pass `--host 0.0.0.0` to expose on a container port. README documents the access-control requirements for cloud deployments. *(SDK-004)*
- **Tool error responses no longer leak internal exception text.** Catch-all blocks log the full traceback server-side via `_LOGGER.exception()` and return a sanitized German message with a remediation hint to the client. Previously the client received `f"Fehler: {type(e).__name__}: {e}"`, which could leak internal file paths, library internals, and upstream payload fragments. *(SEC-022)*
- **`table_id` input fields enforce regex `^px-[a-z]-\d{8,12}_\d{1,4}$`** instead of only `min_length=5`. Defense-in-depth: malformed identifiers are rejected at the Pydantic boundary before any URL interpolation, cache lookup, or log statement. *(SEC-008)*
- **CI runs `bandit -r src/ -ll` (static security) and `pip-audit` (CVE gate)** as a dedicated `security` job on every push and PR. *(OPS-001)*

## 👀 Observability

- **Structured JSON logging on stderr.** Every tool call emits one `tool_start` and one `tool_end` event with `rid` correlation id, `params_keys` (keys only, no values), `status`, `duration_ms`, and `error_type` on failure. Configurable via `MCP_LOG_LEVEL` env var (default `INFO`). *(OBS-001, OBS-002, OBS-003, SEC-014)*
- **Catch-all exceptions now produce full server-side stack traces** via `_LOGGER.exception()`. The two previously-silent fallback loops (catalog and table-list metadata) now emit `_LOGGER.warning(..., exc_info=True)` so BFS schema regressions surface in logs instead of being masked. *(OBS-004)*

## 🔁 Reliability

- **Transient BFS-API errors are retried** up to 3 times with exponential backoff (0.5s → 4s): `httpx.TimeoutException`, `ConnectError`, `ReadError`, `WriteError`, plus HTTP 429/500/502/503/504. 4xx errors surface immediately. Tunable via `MCP_RETRY_MAX_ATTEMPTS`, `MCP_RETRY_WAIT_INITIAL`, `MCP_RETRY_WAIT_MAX` env vars. New dependency: `tenacity>=8.0.0`. *(SEC-018, SCALE-002)*
- **Table-metadata cache** per `(table_id, lang)` with 1h TTL, used by `bfs_get_table_metadata`, `bfs_list_tables_by_theme`, and `bfs_compare_cantons` — repeat queries return instantly. *(SCALE-003)*
- **`bfs_list_tables_by_theme` fans out metadata fetches in parallel** bounded by `FANOUT_CONCURRENCY = 5`. For `limit=20` this cuts wall-clock from ~20s sequential to ~4s while staying friendly to the upstream API. *(SCALE-004)*

## 📦 Output schema

- **Machine-readable truncation** on data-returning tools: `truncated: bool`, `rows_total: int`, `rows_returned: int` are first-class fields instead of buried in a German `warning` prose string. The German message survives as the `note` field for human display. *(ARCH-009)*

## 📚 Documentation

- New **«Maturity» / «Reifegrad»** section in README (EN + DE) flags Alpha 0.x status and recommends pinning cloud deployments to git tags rather than `main`. *(OPS-003)*
- New **«Observability»** section documents log fields and env vars.
- New **«Resilience»** section documents retry, cache, and concurrency caps.
- New **«Output Schema»** section documents the migration from JSON strings to typed Pydantic models.

## 🐛 Fixes

- HTTP entrypoint previously passed `port=` to `mcp.run()`, which raises `TypeError` in current MCP SDK (≥ 1.27). Port is now set via `mcp.settings.port` before `run()`. The HTTP transport mode was effectively broken before this fix.

---

## Audit verification

- **Skill:** [mcp-audit-skill v1.0.0](https://github.com/malkreide/mcp-audit-skill)
- **Catalog hash:** `091f446b27965044ce658a1d5f4b2cabe2b0ab5661dcc1a53b6be8f1f2e093c0`
- **Run-ID:** `2026-05-20T044515-Z-swiss-statistics-mcp`
- **Checks evaluated:** 68 (44 applicable, 24 n/a)
- **Status:** 44 pass · 0 fail · 0 partial · 0 todo
- **Findings:** 0
- **Production-ready:** ✅ yes

See `audits/2026-05-20T044515-Z-swiss-statistics-mcp/` for full evidence.

---

## Upgrade notes

This is a breaking release. If your code consumes tool outputs:

1. Remove `json.loads(...)` around tool returns.
2. Replace `data["rows_total"]` with `result.rows_total` (or `result.model_dump()` for a dict view).
3. Check `result.error is None` to detect success instead of `if "error" in data`.
4. For data tools, prefer the new `result.truncated` boolean over parsing the German `note` text.

If you deploy to Render or similar:

1. Add `MCP_HOST=0.0.0.0` as an environment variable (the default is now `127.0.0.1` for safety).
2. Consider putting the service behind Cloudflare Access, Render «Private Service», or a reverse proxy with auth — the server has no authentication.
3. Tail stderr in your platform's log viewer for structured per-call JSON events.

## Acknowledgements

This release was produced by following the remediation plan from [audit PR #1](https://github.com/malkreide/swiss-statistics-mcp/pull/1) across PRs #2–#8, then verified by the re-audit in [PR #9](https://github.com/malkreide/swiss-statistics-mcp/pull/9).
