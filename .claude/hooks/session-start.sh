#!/usr/bin/env bash
#
# SessionStart-Hook: meldet, wie viele Commits der ausgecheckte Stand hinter
# origin/<default-branch> liegt. Siehe .claude/hooks/README.md fuer den Grund.
#
# Oberste Regel: Dieser Hook blockiert die Session NIEMALS. Kein Netz, kein
# Remote, detached HEAD, flatterndes DNS, fehlendes git -- jeder dieser Faelle
# geht still durch. Darum:
#   - kein `set -e` (ein fehlschlagendes Kommando wuerde den Hook mit einem
#     Exit-Code != 0 beenden und die Session anhalten),
#   - jeder Pfad endet in `exit 0`,
#   - jeder Netzaufruf laeuft unter einem harten Timeout,
#   - Git darf nicht interaktiv nach Zugangsdaten fragen.

set -u

# --- Nie interaktiv werden -------------------------------------------------
# Ohne diese Variablen kann git auf einen Credential- oder Host-Key-Prompt
# warten. Ein wartender Prompt ist genau das Haengen, das hier verboten ist.
export GIT_TERMINAL_PROMPT=0
export GIT_ASKPASS=true
export SSH_ASKPASS=true
export SSH_ASKPASS_REQUIRE=never
export GCM_INTERACTIVE=never
export GIT_SSH_COMMAND="${GIT_SSH_COMMAND:-ssh -oBatchMode=yes -oConnectTimeout=5}"

DEFAULT_BRANCH_TIMEOUT=5
FETCH_TIMEOUT=8

# --- Timeout-Helfer --------------------------------------------------------
# coreutils-`timeout` ist nicht ueberall da (macOS liefert es nicht mit).
# Fehlt es, wird der Aufruf im Hintergrund gestartet und selbst abgeraeumt --
# ein fehlendes Binary darf den Schutz nicht stillschweigend aufheben.
TIMEOUT_BIN=""
if command -v timeout >/dev/null 2>&1; then
  TIMEOUT_BIN="timeout"
elif command -v gtimeout >/dev/null 2>&1; then
  TIMEOUT_BIN="gtimeout"
fi

run_limited() {
  # usage: run_limited <sekunden> <kommando...>; stdout des Kommandos -> stdout
  local secs="$1"
  shift

  if [ -n "$TIMEOUT_BIN" ]; then
    "$TIMEOUT_BIN" -k 1 "$secs" "$@"
    return $?
  fi

  local tmp rc pid waited
  tmp="$(mktemp 2>/dev/null)" || return 1
  "$@" >"$tmp" 2>/dev/null &
  pid=$!
  waited=0
  while kill -0 "$pid" 2>/dev/null; do
    if [ "$waited" -ge "$secs" ]; then
      kill -TERM "$pid" 2>/dev/null
      sleep 1
      kill -KILL "$pid" 2>/dev/null
      wait "$pid" 2>/dev/null
      rm -f "$tmp"
      return 124
    fi
    sleep 1
    waited=$((waited + 1))
  done
  wait "$pid"
  rc=$?
  cat "$tmp" 2>/dev/null
  rm -f "$tmp"
  return "$rc"
}

# --- Nur beim echten Sessionstart melden -----------------------------------
# Claude Code liefert das Hook-Payload als JSON auf stdin. Nach `clear` oder
# `compact` waere die Meldung blosse Wiederholung. Laesst sich das Feld nicht
# lesen, wird gemeldet -- lieber einmal zu viel als der Hinweis, der fehlt.
payload=""
if [ ! -t 0 ]; then
  payload="$(cat 2>/dev/null)"
fi
case "$payload" in
  *'"source"'*'"compact"'* | *'"source"'*'"clear"'*) exit 0 ;;
esac

command -v git >/dev/null 2>&1 || exit 0

repo_dir="${CLAUDE_PROJECT_DIR:-.}"
cd "$repo_dir" 2>/dev/null || exit 0

# Kein Repo, oder ein Repo ohne Commit (unborn HEAD): nichts zu vergleichen.
git rev-parse --git-dir >/dev/null 2>&1 || exit 0
git rev-parse --verify -q HEAD >/dev/null 2>&1 || exit 0
git remote get-url origin >/dev/null 2>&1 || exit 0

# --- Default-Branch ermitteln, nicht annehmen ------------------------------
# "main" ist eine Annahme, keine Tatsache: drei Server im Portfolio heissen
# ihren Default-Branch `master`. Ein fest verdrahtetes origin/main scheitert
# dort mit "couldn't find remote ref main" -- und der Klon bleibt veraltet.
# Erst die lokale Notiz (kostet kein Netz), dann der Remote.
default_branch="$(git symbolic-ref --quiet --short refs/remotes/origin/HEAD 2>/dev/null)"
default_branch="${default_branch#origin/}"

if [ -z "$default_branch" ]; then
  ls_remote="$(run_limited "$DEFAULT_BRANCH_TIMEOUT" git ls-remote --symref origin HEAD 2>/dev/null)"
  default_branch="$(printf '%s\n' "$ls_remote" |
    sed -n 's|^ref: refs/heads/\([^[:space:]]*\)[[:space:]].*|\1|p' | head -n 1)"
fi

# Leer heisst: Remote nicht erreichbar oder keine Auskunft. Still durchgehen.
# Kein Fallback auf "main" -- das waere wieder die Annahme von oben.
[ -n "$default_branch" ] || exit 0

# --- Fetch unter hartem Timeout --------------------------------------------
run_limited "$FETCH_TIMEOUT" git fetch --quiet origin "$default_branch" >/dev/null 2>&1 || exit 0

upstream="$(git rev-parse --verify -q FETCH_HEAD 2>/dev/null)"
[ -n "$upstream" ] || exit 0

behind="$(git rev-list --count "HEAD..$upstream" 2>/dev/null)"
case "$behind" in
  '' | *[!0-9]*) exit 0 ;;
  0) exit 0 ;;
esac

# --- Ausgabe nur, wenn wirklich Commits fehlen -----------------------------
if [ "$behind" -eq 1 ]; then
  commits="1 Commit"
else
  commits="$behind Commits"
fi

printf '%s\n' "⚠️  Klon veraltet: HEAD liegt $commits hinter origin/$default_branch."

# Der Vorschlag haengt davon ab, wo HEAD steht -- ein `pull` bewegt IMMER den
# ausgecheckten Branch, nicht den, dessen Namen man tippt. Wer auf einem
# Feature-Branch `git pull --ff-only origin main` ausfuehrt, zieht den
# Feature-Branch auf main vor und hat danach fremde Commits darauf. Genau das
# ist am 20.8.2026 in dieser Sitzung passiert.
#
# Kein `&&` in den Befehlen: Windows PowerShell 5.1 kennt es nicht ("Das Token
# "&&" ist in dieser Version kein gueltiges Anweisungstrennzeichen"), und der
# Vorschlag scheitert dann ausgerechnet in dem Moment, in dem er helfen soll.
current_branch="$(git symbolic-ref --quiet --short HEAD 2>/dev/null)"

if [ "$current_branch" = "$default_branch" ]; then
  printf '%s\n' "   Vor der Arbeit aktualisieren:"
  printf '%s\n' "     git pull --ff-only origin $default_branch"
else
  if [ -n "$current_branch" ]; then
    printf '%s\n' "   HEAD steht auf '$current_branch', nicht auf '$default_branch'."
  else
    printf '%s\n' "   HEAD ist detached, steht also nicht auf '$default_branch'."
  fi
  printf '%s\n' "   Nur die Referenz holen, ohne HEAD zu bewegen:"
  printf '%s\n' "     git fetch origin $default_branch"
  printf '%s\n' "   Den neuen Stand in den eigenen Branch zu uebernehmen ist ein eigener,"
  printf '%s\n' "   bewusster Schritt (merge oder rebase, je nach Konvention des Repos)."
fi

printf '%s\n' "   Grund: Ein veralteter Klon erzeugt eine rote CI, deren Ursache nicht im"
printf '%s\n' "   Diff steht -- die fehlenden Commits sind dann genau die, die das Gate"
printf '%s\n' "   eingefuehrt haben, an dem der Branch scheitert (2x am 3.8.2026)."

exit 0
