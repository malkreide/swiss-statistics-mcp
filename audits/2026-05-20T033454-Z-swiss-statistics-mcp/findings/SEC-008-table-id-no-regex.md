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
