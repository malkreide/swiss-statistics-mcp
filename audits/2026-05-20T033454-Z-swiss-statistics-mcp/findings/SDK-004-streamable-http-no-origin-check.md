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
