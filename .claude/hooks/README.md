# `.claude/hooks`

## `session-start.sh` — Klon-Aktualitätsprüfung

Meldet beim Sessionstart, wie viele Commits der ausgecheckte Stand hinter
`origin/<default-branch>` liegt. Liegt er nicht zurück, sagt der Hook nichts.

### Grund

Ein veralteter Klon hat am 3.8.2026 zweimal eine rote CI erzeugt, deren Ursache
nicht im Diff stand — die fehlenden Commits waren jeweils genau die, die das
Gate einführten, an dem der Branch scheiterte. Wer den Diff liest, sucht in den
falschen Dateien: dort steht nichts Falsches. Die Prüfung kostet eine Sekunde
und ersetzt eine Fehlersuche am falschen Ort.

### Der Hook blockiert nie

Das ist die oberste Anforderung, nicht ein Detail der Umsetzung. Ein Hook, der
bei Netzproblemen die Arbeit anhält, wird nach dem zweiten Mal abgeschaltet —
und schützt danach gar nichts. Also gehen alle diese Fälle **still** durch,
mit Exit-Code 0 und ohne Ausgabe:

| Fall | Verhalten |
| --- | --- |
| Kein Netz, DNS flattert, Remote weg | Timeout, stiller Abbruch |
| Kein `origin`-Remote / kein Git-Repo | stiller Abbruch |
| `git` nicht im `PATH` | stiller Abbruch |
| Detached HEAD | funktioniert normal (`HEAD..FETCH_HEAD`) |
| Repo ohne Commit (unborn HEAD) | stiller Abbruch |
| Default-Branch nicht ermittelbar | stiller Abbruch, **kein** Fallback auf `main` |
| Stand ist aktuell (0 Commits zurück) | keine Ausgabe |

Umgesetzt durch: kein `set -e` (ein einzelnes fehlschlagendes Kommando würde
den Hook sonst mit Exit-Code != 0 beenden), `exit 0` auf jedem Pfad, und
`GIT_TERMINAL_PROMPT=0` plus `GIT_ASKPASS`/`SSH_ASKPASS`, damit git nicht auf
eine Passwort- oder Host-Key-Eingabe wartet — ein wartender Prompt wäre genau
das Hängen, das hier verboten ist.

### Timeouts

Zwei Netzaufrufe, beide hart begrenzt: Default-Branch-Auflösung 5 s, `fetch`
8 s. Darüber liegt zusätzlich `"timeout": 20` in `.claude/settings.json` als
Netz von Claude Code selbst.

`timeout(1)` aus den coreutils ist nicht überall vorhanden — macOS liefert es
nicht mit. Fehlt es (und auch `gtimeout`), startet der Hook den Aufruf im
Hintergrund und räumt ihn selbst ab. Ein fehlendes Binary darf den Schutz nicht
stillschweigend aufheben.

### Default-Branch wird ermittelt, nicht angenommen

`main` ist eine Annahme, keine Tatsache: drei Server im Portfolio
(`openlex-mcp`, `swiss-courts-mcp`, `swisstopo-mcp`) heissen ihren
Default-Branch `master`. Ein fest verdrahtetes `origin/main` scheitert dort mit
«couldn't find remote ref main» — und genau diese Annahme hat schon einmal einen
Branch 15 Commits alt werden lassen.

Reihenfolge: erst `refs/remotes/origin/HEAD` (lokal, kostet kein Netz), sonst
`git ls-remote --symref origin HEAD`. Bleibt beides ohne Antwort, schweigt der
Hook — ein Fallback auf `main` wäre wieder dieselbe Annahme.

### Der vorgeschlagene Befehl hängt davon ab, wo HEAD steht

`git pull` bewegt **immer den ausgecheckten Branch**, nicht den, dessen Namen
man tippt. Wer auf einem Feature-Branch `git pull --ff-only origin main`
ausführt, zieht damit den Feature-Branch auf `main` vor und hat danach fremde
Commits darauf — am 20.8.2026 genau so passiert, der Stop-Hook meldete
anschliessend einen «ungepushten Commit», der in Wahrheit GitHubs Merge-Commit
war. Der Hook unterscheidet deshalb:

| HEAD steht auf | Vorschlag |
| --- | --- |
| dem Default-Branch | `git pull --ff-only origin <branch>` |
| einem anderen Branch | `git fetch origin <branch>` — bewegt HEAD nicht |
| detached | `git fetch origin <branch>` — dito |

Im zweiten und dritten Fall bleibt das Übernehmen in den eigenen Branch ein
eigener, bewusster Schritt (merge oder rebase, je nach Konvention des Repos).
Der Hook entscheidet das nicht für einen: Auf einem fremden Branch wäre ein
Rebase ein Eingriff in dessen Historie.

### Kein `&&` in den Vorschlägen

Beide Vorschläge sind ein einzelner Befehl, nicht zwei mit `&&`. Windows PowerShell 5.1 kennt `&&` nicht und bricht mit «Das Token
"&&" ist in dieser Version kein gültiges Anweisungstrennzeichen» ab; der
Vorschlag scheitert dort also ausgerechnet in dem Moment, in dem er helfen soll
(gemeldet am 20.8.2026 aus einer PowerShell-Sitzung). `git pull --ff-only` tut
dasselbe und läuft in PowerShell, cmd, bash und zsh gleichermassen. Mit `;` zu
verketten wäre kein Ersatz: das führt den zweiten Befehl auch dann aus, wenn der
`fetch` scheitert.

### Wann er läuft

Bei jedem Sessionstart und bei `resume`. Nach `clear` und `compact` schweigt er
(das Feld `source` aus dem Hook-Payload auf stdin) — dort wäre die Meldung blosse
Wiederholung.

### Selbst ausführen

```bash
CLAUDE_PROJECT_DIR="$PWD" .claude/hooks/session-start.sh </dev/null
```

Tests: `tests/test_session_start_hook.py` (Marker: keiner, läuft im
`not live`-Gate mit, ohne Netz — die Gegenproben bauen echte Git-Repos in
einem Temp-Verzeichnis).
