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
