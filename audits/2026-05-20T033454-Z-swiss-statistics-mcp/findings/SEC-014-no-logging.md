## Finding: SEC-014 — Audit Trail / Logging fehlt komplett

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | open |
| **Server** | `swiss-statistics-mcp` |
| **Check-Reference** | `SEC-014` |
| **Audit-Datum** | 2026-05-20 |

### Observed Behavior

```bash
$ grep -n "import logging\|logger\.\|logging\." src/swiss_statistics_mcp/server.py
# → 0 matches
$ grep -nE "^\s*print\(" src/swiss_statistics_mcp/server.py
# → 0 matches
```

Im Cloud-Deployment (Render.com) emittiert der Server keinerlei eigene Logs. Tool-Aufrufe, Inputs, Latenzen, Fehler — alles unsichtbar.

### Expected Behavior

- Mindestens INFO-Log pro Tool-Call mit: Tool-Name, Input-Hash (nicht Klartext, falls je PII), Duration, Status, Response-Size
- WARN/ERROR-Log mit vollem Stack-Trace bei `except Exception as e`
- Strukturiertes Format (JSON) für maschinelle Auswertung in Cloud-Log-Aggregatoren

### Risk Description

- Bei Incident («Server gibt falsche Daten zurück») keine Forensik möglich
- DoS-Angriffe oder Quota-Burn durch fremde Clients (siehe SDK-004) bleiben unbemerkt
- Keine Möglichkeit, BFS-API-Ausfälle von Bugs im Server zu unterscheiden

### Remediation

`src/swiss_statistics_mcp/server.py` (oben):

```python
import logging
import json
import time

logger = logging.getLogger("swiss_statistics_mcp")
logging.basicConfig(
    level=logging.INFO,
    format='{"ts":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","msg":%(message)s}',
)


def _log_tool_call(tool: str, params: dict, status: str, duration_ms: int, error: str | None = None):
    logger.info(json.dumps({
        "tool": tool,
        "params_keys": sorted(params.keys()),  # keine Werte → kein PII-Risiko
        "status": status,
        "duration_ms": duration_ms,
        "error": error,
    }))
```

Pro Tool-Funktion:

```python
@mcp.tool(...)
async def bfs_get_data(params: GetDataInput) -> str:
    t0 = time.monotonic()
    try:
        ...
        _log_tool_call("bfs_get_data", params.model_dump(exclude_none=True),
                       "ok", int((time.monotonic() - t0) * 1000))
        return result
    except Exception as e:
        logger.exception("bfs_get_data failed")
        _log_tool_call("bfs_get_data", params.model_dump(exclude_none=True),
                       "error", int((time.monotonic() - t0) * 1000), str(e))
        raise
```

### Effort

**M** — Logger-Setup einmal, dann Wrapper-Decorator oder pro Tool t0/log einbauen (9 Tools).

### Verification After Fix

- Lokaler `python -m swiss_statistics_mcp.server` zeigt JSON-Log-Line pro Tool-Call
- `grep -c 'logger\.' src/swiss_statistics_mcp/server.py` ≥ 9
