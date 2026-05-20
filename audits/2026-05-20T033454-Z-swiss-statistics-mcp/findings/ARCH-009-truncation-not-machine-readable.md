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
