## Finding: SCALE-004 — `bfs_compare_cantons` fan-out sequenziell statt parallel

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Server** | `swiss-statistics-mcp` |
| **Check-Reference** | `SCALE-004` |
| **Audit-Datum** | 2026-05-20 |

### Observed Behavior

`bfs_compare_cantons` (server.py:1189) iteriert die `cantons`-Liste sequenziell und sammelt Ergebnisse mit serieller `await`-Loop. Keine `asyncio.gather`-Stelle in `src/`.

### Risk Description

Bei 6 Kantonen × 1s Latency = 6s Tool-Latency. Mit Concurrency 5 wären es ~1.2s. LLM-Konversationen brechen oft bei >5s.

### Remediation

```python
sem = asyncio.Semaphore(5)

async def fetch_canton(c):
    async with sem:
        ...

results = await asyncio.gather(*(fetch_canton(c) for c in params.cantons))
```

### Effort

**S** — Lokal in einer Funktion. Tests anpassen.

### Dependencies

Solle nach SEC-018 (Retry/Limit) gemacht werden, damit Semaphore-Cap und Retry-Pattern konsistent sind.
