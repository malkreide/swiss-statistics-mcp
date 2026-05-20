## Finding: OBS-004 — Catch-All `except Exception` ohne Stack-Trace

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | open |
| **Server** | `swiss-statistics-mcp` |
| **Check-Reference** | `OBS-004` |
| **Audit-Datum** | 2026-05-20 |

### Observed Behavior

8 generische `except Exception as e:`-Blöcke, kein `logger.exception()`, kein Trace.

Zusätzlich `server.py:154-160`:

```python
try:
    meta = await client.get(meta_url).json()
    ...
except Exception:
    tables.append({"table_id": dbid, "title": dbid})
```

Schluckt **stillschweigend** alle Fehler beim Metadata-Fetch und fällt auf den dbid-Defaultwert zurück. Bug-Maskierung.

### Expected Behavior

```python
except Exception:
    logger.warning("metadata fetch failed for %s", dbid, exc_info=True)
    tables.append({"table_id": dbid, "title": dbid})
```

### Risk Description

- Stille Bug-Maskierung: BFS-API ändert Metadata-Schema → alle Tabellen erscheinen ohne Titel, niemand merkt es
- Falscher Cache-State landet unbemerkt im `_catalog_cache`

### Remediation

Logger einbauen (siehe OBS-001), dann pro `except`-Block `logger.exception` bzw. `logger.warning` mit `exc_info=True` ergänzen.

### Effort

**S** — Sed über 9 Stellen.

### Dependencies

Blockt auf OBS-001.
