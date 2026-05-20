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
