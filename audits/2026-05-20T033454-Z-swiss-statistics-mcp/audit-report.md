# MCP-Server Audit-Report — `swiss-statistics-mcp`

**Audit-Datum:** 
**Skill-Version:** 1.0.0
**Catalog-Version:** ?

---

## 1. Executive Summary

Server `swiss-statistics-mcp` wurde gegen 44 anwendbare Best-Practice-Checks geprüft. 28 bestanden, 16 Findings dokumentiert (0 critical, 8 high, 8 medium, 0 low). Production-Readiness: NICHT erreicht — blockierend: OBS-001, SDK-004, SEC-014, SEC-018.

**Production-Readiness:** NO

---

## 2. Profil-Snapshot

| Feld | Wert |
|---|---|
| Server-Name | `swiss-statistics-mcp` |
| Audit-Datum | ? |
| Skill-Version | 1.0.0 |
| Catalog-Version | ? |
| transport | `dual` |
| auth_model | `none` |
| data_class | `Public Open Data` |
| write_capable | `False` |
| deployment | `['local-stdio', 'Render']` |
| uses_sampling | `False` |
| tools_make_external_requests | `True` |
| stadt_zuerich_context | `False` |
| schulamt_context | `False` |
| data_source.is_swiss_open_data | `True` |

---

## 3. Applicability

### Status pro Kategorie

| Kategorie | Pass | Fail | Partial | Todo | N/A |
|---|---|---|---|---|---|
| ARCH | 9 | 0 | 2 | 0 | 1 |
| CH | 1 | 0 | 0 | 0 | 7 |
| HITL | 0 | 0 | 0 | 0 | 5 |
| OBS | 1 | 3 | 1 | 0 | 1 |
| OPS | 1 | 0 | 2 | 0 | 0 |
| SCALE | 2 | 1 | 2 | 0 | 1 |
| SDK | 3 | 1 | 0 | 0 | 1 |
| SEC | 11 | 2 | 2 | 0 | 8 |
| **Total** | **28** | **7** | **9** | **0** | **24** |

---

## 4. Findings-Übersicht

_Policy: `fail-or-partial`_

| ID | Category | Severity | Status |
|---|---|---|---|
| OBS-001 | OBS | high | fail |
| OBS-004 | OBS | high | partial |
| OPS-001 | OPS | high | partial |
| SDK-004 | SDK | high | fail |
| SEC-008 | SEC | high | partial |
| SEC-014 | SEC | high | fail |
| SEC-018 | SEC | high | fail |
| SEC-022 | SEC | high | partial |
| ARCH-005 | ARCH | medium | partial |
| ARCH-009 | ARCH | medium | partial |
| OBS-002 | OBS | medium | fail |
| OBS-003 | OBS | medium | fail |
| OPS-003 | OPS | medium | partial |
| SCALE-002 | SCALE | medium | fail |
| SCALE-003 | SCALE | medium | partial |
| SCALE-004 | SCALE | medium | partial |

**Gesamt:** 16 Findings

---

## 5. Detail-Findings

### ARCH-005

## Finding: ARCH-005 — Tools liefern JSON-Strings statt strukturierter Outputs

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Server** | `swiss-statistics-mcp` |
| **Check-Reference** | `ARCH-005` |
| **Audit-Datum** | 2026-05-20 |

### Observed Behavior

Alle 9 Tools haben Return-Typ `-> str` und nutzen `json.dumps(...)` (server.py:123, 503, 596, 679, 765, 861, 1044, 1167, 1258, 1309).

### Expected Behavior

FastMCP unterstützt Pydantic-Return-Modelle. Strukturierte Outputs erlauben dem Client (Claude Desktop), Felder zu rendern, Tabellen zu zeichnen und Folge-Calls korrekt zu typisieren.

### Remediation

Pro Tool:

```python
class GetDataResult(BaseModel):
    table_id: str
    rows: list[dict[str, Any]]
    total_rows: int
    truncated: bool
    note: str | None = None

@mcp.tool(...)
async def bfs_get_data(params: GetDataInput) -> GetDataResult:
    ...
    return GetDataResult(table_id=..., rows=..., total_rows=..., truncated=...)
```

### Effort

**L** — Breaking-Change für alle 9 Tools, Tests müssen umgeschrieben werden, Major-Version-Bump (0.x → 0.y bricht semver-untouchable nicht, aber Konsumenten müssen wissen).

Empfehlung: nach Release 0.2.0 als Vorbereitung auf 1.0.


### ARCH-009

## Finding: ARCH-009 — Truncation-Signal nur als deutscher Prosa-Text

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Server** | `swiss-statistics-mcp` |
| **Check-Reference** | `ARCH-009` |
| **Audit-Datum** | 2026-05-20 |

### Observed Behavior

`server.py:854-856`:

```python
if result["total_rows"] > params.max_rows:
    result["note"] = (
        f"Datenmenge auf {params.max_rows} Zeilen begrenzt ..."
    )
```

Der LLM muss den deutschen Text parsen, um zu wissen, dass die Daten unvollständig sind.

### Expected Behavior

```python
result["truncated"] = result["total_rows"] > params.max_rows
result["rows_returned"] = len(result["rows"])
result["rows_total"] = result["total_rows"]
if result["truncated"]:
    result["note"] = "Datenmenge begrenzt — siehe truncated=true"
```

### Effort

**S** — Single-file Edit, gemeinsam mit ARCH-005 (strukturierte Outputs) sauberer.


### OBS-001

## Finding: OBS-001 — Logging-Infrastruktur fehlt

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | open |
| **Server** | `swiss-statistics-mcp` |
| **Check-Reference** | `OBS-001` |
| **Audit-Datum** | 2026-05-20 |

### Observed Behavior

Keine `logging`-Import-Anweisung, kein `logger`-Setup, keine `print()`-Statements im gesamten `src/`.

### Expected Behavior

Mindestens stdlib-`logging` mit konfigurierbarem Level (`MCP_LOG_LEVEL`-Env-Var), Default INFO, JSON-Format für Cloud-Deployment.

### Remediation

Siehe SEC-014 für vollständigen Code-Vorschlag.

### Effort

**S** — Aufgesetzt zusammen mit SEC-014.

### Dependencies / Blockers

Doppel-Fix mit **SEC-014** und **OBS-002/003** sinnvoll.


### OBS-002

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


### OBS-003

## Finding: OBS-003 — Keine Metriken (Latency, Error-Rate, Throughput)

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Server** | `swiss-statistics-mcp` |
| **Check-Reference** | `OBS-003` |
| **Audit-Datum** | 2026-05-20 |

### Observed Behavior

Keine Prometheus-, OpenTelemetry- oder StatsD-Integration. Bei Cloud-Deployment fehlt p95/p99-Visibility.

### Expected Behavior

Für Public-Open-Data-Server mit moderatem Risiko reicht **Log-Derivation**: Wenn jeder Tool-Call eine JSON-Log-Line mit `duration_ms` schreibt (siehe OBS-001), kann Render's Log-Dashboard die Metriken aggregieren.

Für höhere Reife: `prometheus_client`-Integration mit `/metrics`-Endpoint hinter Auth.

### Remediation

Minimal-Variante: Saubere `duration_ms`-Felder im Log (kommt mit OBS-001-Fix).

### Effort

**S** (log-derived) — **M** (prometheus_client mit /metrics)

### Dependencies

Blockt auf OBS-001.


### OBS-004

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


### OPS-001

## Finding: OPS-001 — CI ohne Security-Scanner

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | open |
| **Server** | `swiss-statistics-mcp` |
| **Check-Reference** | `OPS-001` |
| **Audit-Datum** | 2026-05-20 |

### Observed Behavior

`.github/workflows/ci.yml` führt pytest + ruff auf Python 3.11/3.12/3.13. **Kein** bandit, pip-audit, semgrep, dependabot, gitleaks.

### Expected Behavior

Minimum:
- `pip-audit` für CVE-Scan auf Dependencies (free, OSS, schnell)
- `bandit -r src/` für Python-Security-Anti-Patterns
- Dependabot oder Renovate für automatische Dependency-Updates

### Remediation

`.github/workflows/ci.yml` ergänzen:

```yaml
      - name: Security scan (bandit)
        run: |
          pip install bandit
          bandit -r src/ -ll

      - name: Dependency CVE scan (pip-audit)
        run: |
          pip install pip-audit
          pip-audit --strict
```

`pyproject.toml` `[project.optional-dependencies]`:

```diff
 dev = [
     "pytest>=8.0.0",
     "pytest-asyncio>=0.23.0",
     "pytest-cov>=5.0.0",
     "respx>=0.21.0",
     "ruff>=0.4.0",
+    "bandit>=1.7.0",
+    "pip-audit>=2.7.0",
 ]
```

### Effort

**S** — Zwei CI-Steps, eine Dependency-Group, ggf. Fixes für False-Positives.

### Risk Description

Ohne CVE-Scan landet eine bekannte Vulnerability in `httpx`/`pydantic`/`mcp` unbemerkt in Production. Bei einem Public-Cloud-Deployment (Render.com) ist das relevant.


### OPS-003

## Finding: OPS-003 — Kein dokumentierter Rollout-/Versionspfad

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Server** | `swiss-statistics-mcp` |
| **Check-Reference** | `OPS-003` |
| **Audit-Datum** | 2026-05-20 |

### Observed Behavior

- `pyproject.toml`: `version = "0.1.0"`, Classifier `Development Status :: 3 - Alpha`
- README empfiehlt Render.com-Deployment ohne «Alpha»-/«Experimentell»-Warnung
- Kein dokumentierter Plan für Breaking-Changes / Tool-Naming / Schema-Evolution

### Expected Behavior

- README-Sektion «Maturity» die Alpha-Status erwähnt
- Versions-Policy: SemVer-Garantien (vor 1.0: minor = breaking erlaubt)
- CHANGELOG hat strukturierte Sektionen (Added/Changed/Removed/Security)

### Remediation

README.md, Abschnitt direkt unter Overview:

```markdown
## Maturity

This server is **Alpha** (0.x). Tool names and output schemas may change
between minor versions until 1.0. Cloud deployments should pin to a
specific git tag.
```

CHANGELOG.md auf [Keep a Changelog](https://keepachangelog.com)-Schema migrieren.

### Effort

**S** — Dokumentations-Änderungen.


### SCALE-002

## Finding: SCALE-002 — Kein Retry / Backoff bei transienten Upstream-Fehlern

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Server** | `swiss-statistics-mcp` |
| **Check-Reference** | `SCALE-002` |
| **Audit-Datum** | 2026-05-20 |

### Observed Behavior

Jeder `httpx`-Call ist Single-Shot. 503/504/Timeout bricht den Tool-Call sofort. Siehe auch SEC-018.

### Remediation

Tenacity-basierter Retry-Decorator auf `_get`/`_post` — Code-Diff bereits in SEC-018 dokumentiert.

### Effort

**S** — gemeinsam mit SEC-018.

### Dependencies

Doppel-Fix mit SEC-018.


### SCALE-003

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


### SCALE-004

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


### SDK-004

## Finding: SDK-004 — Streamable-HTTP-Transport ohne Origin-/Auth-Check

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | open |
| **Server** | `swiss-statistics-mcp` |
| **Check-Reference** | `SDK-004` |
| **Audit-Datum** | 2026-05-20 |

### Observed Behavior

`src/swiss_statistics_mcp/server.py:1352` startet den Streamable-HTTP-Transport ohne Host-Binding, ohne Origin-Validierung und ohne Authentifizierung:

```python
if "--http" in sys.argv:
    port_idx = sys.argv.index("--port") + 1 if "--port" in sys.argv else None
    port     = int(sys.argv[port_idx]) if port_idx else 8000
    mcp.run(transport="streamable-http", port=port)
```

`README.md:141-149` empfiehlt explizit ein öffentliches Render.com-Deployment:

```
Render.com (recommended):
  In claude.ai under Settings → MCP Servers, add: https://your-app.onrender.com/sse
```

### Expected Behavior

Bei Streamable-HTTP auf einer öffentlich erreichbaren URL ist mindestens eines erforderlich:

- Default-Bind auf `127.0.0.1` (lokal-only), explizites Opt-in für `0.0.0.0`
- Origin-Allowlist gegen DNS-Rebinding (`Access-Control-Allow-Origin` restriktiv)
- Optionaler Bearer-Token (Env-Var) für Cloud-Deployments, mindestens als Empfehlung im README

### Risk Description

- Jede Web-Origin kann den deployten Server als Open-Proxy für die BFS-API missbrauchen (Rate-Limit-Verbrauch zu Lasten der eigenen Deployment-IP, Reputation-Risiko gegenüber BFS)
- DNS-Rebinding-Angriffe gegen Browser-Clients sind möglich, weil keine Origin geprüft wird
- Render.com-Logs/Quota werden durch fremde Tool-Calls verzehrt, ohne dass dies im Log auffällt (siehe OBS-001)

### Remediation

```diff
 if __name__ == "__main__":
     import sys

     if "--http" in sys.argv:
+        import os
         port_idx = sys.argv.index("--port") + 1 if "--port" in sys.argv else None
         port     = int(sys.argv[port_idx]) if port_idx else 8000
-        mcp.run(transport="streamable-http", port=port)
+        host = os.environ.get("MCP_HOST", "127.0.0.1")  # Default: localhost-only
+        # Optional: BEARER_TOKEN aus Env, in einem FastMCP-Middleware-Hook prüfen
+        mcp.run(transport="streamable-http", host=host, port=port)
     else:
         mcp.run()
```

README-Sektion ergänzen:
- «Cloud Deployment exposes the server without authentication. Set `MCP_HOST=0.0.0.0` only if you accept that anyone with the URL can drive the tools.»
- Hinweis auf Render's «Private Service» oder vorgeschalteten Reverse-Proxy mit Basic-Auth/Cloudflare-Access.

### Effort

**S** — Default-Host-Binding ändern, README-Warnung ergänzen, optional Env-Var-Bearer-Check als Middleware.

### Verification After Fix

- `grep -n 'host=' src/swiss_statistics_mcp/server.py` → zeigt 127.0.0.1-Default
- README-Sektion «Cloud Deployment» enthält explizite Security-Warnung


### SEC-008

## Finding: SEC-008 — `table_id` ohne Regex-Allowlist (Defense in Depth)

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | open |
| **Server** | `swiss-statistics-mcp` |
| **Check-Reference** | `SEC-008` |
| **Audit-Datum** | 2026-05-20 |

### Observed Behavior

`server.py:235-241, 265-268, 348` — `table_id` hat nur `min_length=5`:

```python
table_id: str = Field(
    ...,
    min_length=5,
    description="BFS table ID, e.g. 'px-x-1504000000_173'",
)
```

`table_id` wird in URL-Pfade interpoliert:

```python
return f"{BFS_API_BASE}/{lang}/{dbid}/{dbid}.px"
```

### Expected Behavior

Da BFS-IDs einem klaren Schema folgen (`px-x-\d+_\d+`), gehört das als Pattern in das Field:

```python
table_id: str = Field(
    ...,
    pattern=r"^px-[a-z]-\d{10}_\d{2,4}$",
    description="BFS table ID, e.g. 'px-x-1504000000_173'",
)
```

### Risk Description

- httpx encodet zwar Path-Segmente, aber Defense in Depth verlangt, ungültige IDs vor dem Outbound-Call abzulehnen
- Ein `table_id` wie `..%2F..%2Fadmin` wird durch httpx wahrscheinlich harmlos, aber: Cache-Key (`_catalog_cache`) und Error-Messages könnten verwirrt werden

### Remediation

```diff
 table_id: str = Field(
     ...,
-    min_length=5,
+    pattern=r"^px-[a-z]-\d{10}_\d{2,4}$",
     description="BFS table ID, e.g. 'px-x-1504000000_173'",
 )
```

Gleiches Pattern an allen drei Stellen (GetTableMetadataInput, GetDataInput, CompareCantonsInput).

### Effort

**S** — Drei Field-Definitionen, ein Test pro Tool, dass invalide IDs zurückgewiesen werden.

### Verification After Fix

```bash
pytest tests/test_server.py::TestInputValidation -v
```


### SEC-014

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


### SEC-018

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


### SEC-022

## Finding: SEC-022 — Roh-Exception-Messages an Client durchgereicht

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | open |
| **Server** | `swiss-statistics-mcp` |
| **Check-Reference** | `SEC-022` |
| **Audit-Datum** | 2026-05-20 |

### Observed Behavior

8 Stellen in `server.py` (Zeilen 520, 613, 694, 793, 878, 1046, 1170, 1260) folgen dem Pattern:

```python
except Exception as e:
    return _format_error(f"Unerwarteter Fehler: {type(e).__name__}: {e}")
```

`{e}` enthält bei `httpx`/`json`/`pydantic`-Fehlern oft Dateipfade, URL-Fragmente, Payload-Auszüge und Library-Stacks.

### Expected Behavior

```python
except Exception as e:
    logger.exception("bfs_get_data unexpected error")  # voller Trace in Logs
    return _format_error(
        "Interner Fehler bei der Verarbeitung der Anfrage.",
        hint="Bitte mit kleinerer Datenmenge erneut versuchen.",
    )  # generische Message an Client
```

### Risk Description

- Library-Versionen, interne Pfade, Cache-Keys können an LLM/User leaken
- Ein Tester kann gezielt Fehler provozieren, um die Implementierung zu mappen (Information-Disclosure)

### Remediation

Pro Catch-All-Block: Trace ins Log (sobald OBS-001 gefixt), generische Message zurück. Konkret in `_format_error`:

```python
def _format_error(msg: str, hint: str = "") -> str:
    return json.dumps({"error": msg, "hint": hint}, ensure_ascii=False)
```

Aufruferseitig die `{e}`-Interpolation entfernen:

```diff
-except Exception as e:
-    return _format_error(f"Unerwarteter Fehler: {type(e).__name__}: {e}")
+except Exception:
+    logger.exception("bfs_get_data unexpected error")
+    return _format_error("Interner Fehler. Bitte erneut versuchen.")
```

### Effort

**S** — Sed/Edit über 8 Stellen, sobald Logging steht.

### Dependencies

Sinnvoll zusammen mit OBS-001/SEC-014.


---

## 6. Remediation-Plan

### Empfohlene Reihenfolge

1. **OBS-001** (high, fail)
2. **OBS-004** (high, partial)
3. **OPS-001** (high, partial)
4. **SDK-004** (high, fail)
5. **SEC-008** (high, partial)
6. **SEC-014** (high, fail)
7. **SEC-018** (high, fail)
8. **SEC-022** (high, partial)
9. **ARCH-005** (medium, partial)
10. **ARCH-009** (medium, partial)
11. **OBS-002** (medium, fail)
12. **OBS-003** (medium, fail)
13. **OPS-003** (medium, partial)
14. **SCALE-002** (medium, fail)
15. **SCALE-003** (medium, partial)
16. **SCALE-004** (medium, partial)

---

## 7. Audit-Metadata

| Feld | Wert |
|---|---|
| skill_version | `1.0.0` |
| policy | `fail-or-partial` |


_Generated by tools/build_report.py — do not edit by hand._
