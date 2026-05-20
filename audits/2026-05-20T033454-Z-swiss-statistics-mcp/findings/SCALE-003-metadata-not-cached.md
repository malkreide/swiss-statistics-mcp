## Finding: SCALE-003 — Tabellen-Metadata wird pro Call neu geholt

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Server** | `swiss-statistics-mcp` |
| **Check-Reference** | `SCALE-003` |
| **Audit-Datum** | 2026-05-20 |

### Observed Behavior

Catalog-Index wird gecacht (`_catalog_cache`, TTL = CATALOG_CACHE_TTL). Aber `bfs_get_table_metadata` und der Metadata-Lookup in `bfs_list_tables_by_theme` (server.py:574-593) fetcht pro Aufruf neu, obwohl Metadaten typischerweise tage- bis monatestabil sind.

### Expected Behavior

`@functools.lru_cache(maxsize=512)` mit TTL-Wrapper auf einer pure-Funktion `_fetch_metadata(table_id, lang)` — oder ein zweites dict-Cache analog zum Catalog-Cache.

### Risk Description

- Bei `bfs_list_tables_by_theme` mit limit=20 entstehen 21 Round-Trips zur BFS-API für quasi statische Daten
- Latency-Multiplikator gegenüber LLM-Konversation: gefühlt langsam

### Remediation

```python
_metadata_cache: dict[tuple[str, str], tuple[float, dict]] = {}
METADATA_TTL = 3600

async def _fetch_metadata_cached(dbid: str, lang: str) -> dict:
    key = (dbid, lang)
    now = time.time()
    if key in _metadata_cache and now - _metadata_cache[key][0] < METADATA_TTL:
        return _metadata_cache[key][1]
    meta = await _get(_format_table_url(dbid, lang))
    _metadata_cache[key] = (now, meta)
    return meta
```

### Effort

**S** — Helper-Funktion und Aufrufer umschreiben.
