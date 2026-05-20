## Finding: SEC-018 — Kein Rate-Limit, kein Retry/Backoff, kein Concurrency-Cap

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | open |
| **Server** | `swiss-statistics-mcp` |
| **Check-Reference** | `SEC-018` |
| **Audit-Datum** | 2026-05-20 |

### Observed Behavior

```bash
$ grep -rnE "rate.?limit|throttle|backoff|tenacity|retry" src/
# → 0 matches
```

`bfs_compare_cantons` (server.py:1189) ruft die BFS-API sequenziell pro Kanton auf, mit bis zu 26 Calls pro Tool-Invocation. Keine Concurrency-Begrenzung, kein Per-Client-Budget, kein Retry bei transienten 5xx.

### Expected Behavior

- Pro `httpx.AsyncClient`-Aufruf: 1-2 Retries mit exponentiellem Backoff für 502/503/504/Timeout
- Tool-interne Budget-Cap (z.B. max. 30 Requests pro Tool-Invocation)
- Bei Fan-Out (compare_cantons): `asyncio.Semaphore(5)` + `asyncio.gather` statt sequenzielle Loop

### Risk Description

- Buggy oder hostile Client kann durch wiederholtes `bfs_compare_cantons(cantons=[<alle 26>])` die BFS-API-Quote des Render-Deployments verbrennen
- Einzelner BFS-Hiccup (504) bricht Tool-Response, obwohl 1 Retry den Fehler maskiert hätte
- Reputation gegenüber BFS: Render-IP könnte temporär blockiert werden

### Remediation

Dependency:
```diff
 dependencies = [
     "mcp[cli]>=1.0.0",
     "httpx>=0.27.0",
     "pydantic>=2.0.0",
+    "tenacity>=8.0.0",
 ]
```

`server.py` — Retry-Wrapper:
```python
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.HTTPStatusError)),
    reraise=True,
)
async def _get(url: str) -> Any:
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.json()
```

`bfs_compare_cantons` — Fan-Out limitieren:
```python
sem = asyncio.Semaphore(5)

async def fetch_one(canton):
    async with sem:
        return await _get(...)

results = await asyncio.gather(*(fetch_one(c) for c in cantons))
```

### Effort

**M** — Tenacity-Wrapper auf `_get`/`_post`, Semaphore in `bfs_compare_cantons`, Tests anpassen.

### Verification After Fix

- `pytest tests/test_server.py -k retry` deckt 503-Retry-Pfad ab
- `grep -c "Semaphore\|tenacity" src/swiss_statistics_mcp/server.py` ≥ 2
