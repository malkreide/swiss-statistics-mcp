## Finding: OBS-002 — Kein strukturiertes Logging / keine Correlation-IDs

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Server** | `swiss-statistics-mcp` |
| **Check-Reference** | `OBS-002` |
| **Audit-Datum** | 2026-05-20 |

### Observed Behavior

Konsequenz aus OBS-001: keine Logs → keine Struktur, keine Request-IDs.

### Expected Behavior

JSON-Logs mit Feldern `ts`, `level`, `tool`, `request_id`, `duration_ms`, `status`, `error_type`. Request-ID aus MCP-Context (falls FastMCP eine liefert) oder per `uuid4()` selbst generiert.

### Remediation

```python
import uuid

@mcp.tool(...)
async def bfs_get_data(params: GetDataInput, ctx=None) -> str:
    rid = (ctx.request_id if ctx else None) or str(uuid.uuid4())[:8]
    logger.info(json.dumps({"rid": rid, "tool": "bfs_get_data", "phase": "start"}))
    ...
```

### Effort

**S** — Einmaliger Wrapper, dann ein Funktions-Argument pro Tool.

### Dependencies

Blockt auf OBS-001 / SEC-014.
