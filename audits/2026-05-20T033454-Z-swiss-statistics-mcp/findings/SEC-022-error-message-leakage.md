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
