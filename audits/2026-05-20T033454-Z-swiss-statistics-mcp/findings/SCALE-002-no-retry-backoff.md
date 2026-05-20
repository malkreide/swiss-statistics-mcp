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
