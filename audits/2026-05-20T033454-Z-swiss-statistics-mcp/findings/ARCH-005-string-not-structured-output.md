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
