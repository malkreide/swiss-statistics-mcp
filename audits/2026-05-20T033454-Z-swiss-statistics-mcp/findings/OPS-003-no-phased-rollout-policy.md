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
