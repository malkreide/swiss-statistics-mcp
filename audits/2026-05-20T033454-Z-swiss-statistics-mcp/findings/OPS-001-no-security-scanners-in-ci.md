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
