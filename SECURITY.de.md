# Sicherheitsrichtlinie & Sicherheitslage

[🇬🇧 English Version](SECURITY.md)

`swiss-statistics-mcp` wurde gegen den internen MCP-Best-Practice-Audit-Katalog
gehärtet. Dieses Dokument fasst die Sicherheitslage zusammen und dokumentiert die
**akzeptierten Risiken** für Kontrollen, die bewusst auf der Portfolio-/Gateway-Ebene
statt innerhalb dieses einzelnen Servers behandelt werden.

## Schwachstelle melden

Bitte eröffnen Sie ein privates Security Advisory im GitHub-Repository oder
kontaktieren Sie die in `README.md` genannte verantwortliche Person. Erstellen Sie
für ausnutzbare Schwachstellen **keine** öffentlichen Issues.

## Zusammenfassung der Sicherheitslage

Dies ist ein **rein lesender**, **PII-freier** MCP-Server für **öffentliche Open
Data**. Alle 9 Tools führen ausschliesslich HTTP-GET-Anfragen gegen die
BFS-STAT-TAB-PxWeb-API (`www.pxweb.bfs.admin.ch`) durch. Bereits umgesetzte
Härtungsmassnahmen:

| Bereich | Kontrolle |
|---|---|
| Egress | Ausschliesslich HTTPS zu einem einzigen fixen BFS-Endpunkt (`https://www.pxweb.bfs.admin.ch/api/v1`); keine benutzergesteuerten URLs (SEC-004/021) |
| TLS | Zertifikatsprüfung standardmässig aktiv (httpx-Default); nie deaktiviert (SEC-005) |
| Binding | Netzwerk-Transporte binden standardmässig an `127.0.0.1`; `0.0.0.0` erfordert ein explizites Opt-in via `MCP_HOST` / `--host` (SEC-016 / SDK-004) |
| Input | Pydantic-v2-Strict-Validierung (`extra="forbid"`), `table_id`-Regex `^px-[a-z]-\d{8,12}_\d{1,4}$`, Sprach-Whitelist `^(de\|fr\|it\|en)$` (SEC-008/018) |
| Tools | Jedes Tool setzt `readOnlyHint: True`; es existieren keine Schreib-, Mutations- oder Lösch-Pfade (ARCH) |
| Secrets | Keine erforderlich — der Server nutzt keinen API-Key und keine Anmeldedaten; nichts Geheimes wird gespeichert oder geloggt (ARCH-005/SEC-013) |
| Fehler | Upstream-Fehlerantworten werden nur nach stderr geloggt; das Modell erhält eine generische, nicht durchsickernde Meldung (OBS-002/SEC-022) |
| Stdout | Reserviert für den JSON-RPC-Stream; sämtliches Logging fest auf stderr (OBS-004) |
| Resilienz | Begrenzte Retries mit exponential backoff, ein 30s-Timeout pro Anfrage sowie ein Metadaten-Cache, um den Upstream nicht zu überlasten (SCALE-002/003) |

Der jüngste Audit-Lauf (`2026-05-20T044515-Z-swiss-statistics-mcp`) meldet
**production-ready**: 44 pass · 0 fail · 0 partial · 24 n/a. Den vollständigen
Bericht finden Sie unter `audits/`, die Härtungshistorie in `CHANGELOG.md`.

## Akzeptierte Risiken (Kontrollen auf Portfolio-Ebene)

Die folgenden Audit-Prüfungen sind **bewusst nicht** innerhalb dieses Servers
implementiert. Es handelt sich um portfolioweite Belange, die am besten auf einer
MCP-Gateway-/Host-Ebene durchgesetzt werden; das Restrisiko ist hier gering, da der
Server rein lesend ist und nur einen einzigen vertrauenswürdigen Open-Data-Anbieter
erreicht.

### SEC-014 — Tool-Allow-Listing über ein MCP-Gateway

**Status:** akzeptiertes Risiko (Portfolio-Ebene).
Eine Allow-List pro Tool gehört zum MCP-Host/-Gateway, das mehrere Server aggregiert,
nicht zu einem einzelnen Server, der ein festes, rein lesendes Tool-Set exponiert.
Sobald ein zentrales Gateway für das Portfolio eingeführt wird, sollte das
Tool-Allow-Listing dort konfiguriert werden. Bis dahin ist das Risiko begrenzt: Jedes
Tool ist rein lesend und auf den einzigen oben genannten fixen BFS-Endpunkt beschränkt.

### SEC-015 — Pre-Flight-Erkennung von Tool-Poisoning

**Status:** akzeptiertes Risiko (Portfolio-Ebene) — mit lokaler Schutzmassnahme.
Tool-Poisoning (bösartige Tool-Beschreibungen / Rug-Pulls) ist ein Lieferketten- und
Host-seitiges Problem. Die Tool-Definitionen dieses Servers sind versionskontrolliert,
werden in-repo entwickelt und per PR geprüft; es gibt keine dynamische oder entfernte
Tool-Registrierung. Die serverübergreifende Poisoning-Erkennung bleibt eine Gateway-/
Host-Verantwortung, die auf Portfolio-Ebene verfolgt wird.

## Re-Evaluierungs-Auslöser

Diese Akzeptanzen sollten neu bewertet werden, falls der Server jemals:

- **Schreib**-Funktionalität erhält oder beginnt, **PII** zu verarbeiten, oder
- ein **Authentifizierungs**-Modell erhält (dann gebundene, TTL-behaftete,
  serverseitig invalidierbare Session-IDs implementieren und vor dem Merge neu auditieren), oder
- Tools **dynamisch** / aus entfernten Quellen registriert, oder
- hinter einem gemeinsamen MCP-Gateway aggregiert wird (dann das Tool-Allow-Listing
  und die Tool-Poisoning-Erkennung des Gateways aktivieren).
