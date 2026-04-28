# Use Cases & Examples — swiss-statistics-mcp

Real-world queries by audience. Indicate per example whether an API key is required.

### 🏫 Bildung & Schule
Lehrpersonen, Schulbehörden, Fachreferent:innen

**Lehrkräftebestand analysieren**
*API-Key erforderlich: Nein*

«Wie viele Lehrpersonen unterrichteten im letzten Jahr an den Volksschulen im Kanton Bern?»

→ `bfs_education_stats(topic="teachers", canton="Bern / Berne")`

Warum nützlich: Erlaubt Schulbehörden eine schnelle Übersicht über den Lehrkörper in ihrem Kanton ohne mühsame Recherche in grossen Tabellen.

**Zukünftige Schülerzahlen abschätzen**
*API-Key erforderlich: Nein*

«Wie entwickeln sich gemäss Szenarien die Schülerzahlen der Sekundarstufe II im Kanton Zürich bis 2030?»

→ `bfs_education_stats(topic="scenarios", canton="Zürich")`

Warum nützlich: Unterstützt die kantonale Bildungsplanung bei der Vorbereitung von Infrastruktur und Lehrpersonal für die kommenden Jahre.

### 👨‍👩‍👧 Eltern & Schulgemeinde
Elternräte, interessierte Erziehungsberechtigte

**Stipendien und Darlehen vergleichen**
*API-Key erforderlich: Nein*

«Welche Kantone zahlen die meisten Stipendien und Darlehen aus? Vergleiche die Daten aller Kantone.»

→ `bfs_education_stats(topic="scholarships", canton=None)`

Warum nützlich: Bietet Elternräten Transparenz über die Ausbildungsbeiträge und hilft, die finanzielle Unterstützungssituation im interkantonalen Vergleich zu verstehen.

**Regionale Bevölkerungsentwicklung verstehen**
*API-Key erforderlich: Nein*

«Wie ist die Altersstruktur im Kanton Luzern aktuell verteilt?»

→ `bfs_population(region="Luzern", breakdown="age")`

Warum nützlich: Hilft Eltern und Gemeinden abzuschätzen, ob in Zukunft mit mehr schulpflichtigen Kindern in der Region zu rechnen ist.

### 🗳️ Bevölkerung & öffentliches Interesse
Allgemeine Öffentlichkeit, politisch und gesellschaftlich Interessierte

**Wahl- und Abstimmungsdaten finden**
*API-Key erforderlich: Nein*

«Zeige mir Tabellen mit Resultaten zu den Nationalratswahlen oder eidgenössischen Volksabstimmungen.»

→ `bfs_search_tables(query="Nationalratswahlen")`
→ `bfs_get_table_metadata(table_id="px-x-1703030000_101")`

Warum nützlich: Erlaubt es politisch Interessierten, auf einfache Weise die historischen und aktuellen Wahlergebnisse auf Kantonsebene aufzufinden.

**Sozialhilfequoten vergleichen**
*API-Key erforderlich: Nein*

«Wie hoch ist die Sozialhilfequote im Kanton Zürich im Vergleich zum Kanton Genf?»

→ `bfs_compare_cantons(table_id="px-x-1302020000_101", canton_values=["1", "25"])`

Warum nützlich: Fördert die Transparenz und ermöglicht der Bevölkerung einen datenbasierten Vergleich gesellschaftlicher Kennzahlen.

### 🤖 KI-Interessierte & Entwickler:innen
MCP-Enthusiast:innen, Forscher:innen, Prompt Engineers, öffentliche Verwaltung

**Programmatische Katalog-Navigation**
*API-Key erforderlich: Nein*

«Liste mir alle Tabellen aus dem Bereich 'Gesundheit' (Code 14) auf.»

→ `bfs_list_tables_by_theme(theme_code="14")`

Warum nützlich: Erleichtert Entwicklern den strukturierten Zugriff auf spezifische Datenbereiche zur automatisierten Weiterverarbeitung.

**Demokratie & Statistik kombinieren (Multi-Server)**
*API-Key erforderlich: Nein*

«Suche nach den neusten Abstimmungen zur Bildungspolitik und zeige mir dazu die passenden demografischen Daten.»

→ `democracy_search_affairs(query="Bildung")` (aus [swiss-democracy-mcp](https://github.com/malkreide/swiss-democracy-mcp))
→ `bfs_population(region="Schweiz", breakdown="age")`

Warum nützlich: Demonstriert die Leistungsfähigkeit vernetzter MCP-Server, indem politische Vorstösse direkt mit den zugrundeliegenden demografischen Fakten verknüpft werden.

---

### 🔧 Technische Referenz: Tool-Auswahl nach Anwendungsfall

| Ich möchte… | Tool(s) | Auth nötig? |
|-------------|---------|-------------|
| **eine Übersicht über statistische Themen erhalten** | `bfs_list_themes` | Nein |
| **nach Datensätzen zu einem bestimmten Begriff suchen** | `bfs_search_tables` | Nein |
| **herausfinden, welche Filter eine Tabelle anbietet** | `bfs_get_table_metadata` | Nein |
| **die eigentlichen statistischen Daten abrufen** | `bfs_get_data` | Nein |
| **schnell auf Bildungsdaten zugreifen** | `bfs_education_stats` | Nein |
| **demografische Daten nach Region abfragen** | `bfs_population` | Nein |
| **zwei oder mehr Kantone direkt vergleichen** | `bfs_compare_cantons` | Nein |
