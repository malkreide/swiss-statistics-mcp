#!/usr/bin/env python3
"""Tests fuer .claude/hooks/session-start.sh — die Klon-Aktualitaetspruefung.

Der Hook hat eine Anforderung, die ueber allen anderen steht: Er blockiert die
Session nie. Ein Hook, der bei Netzproblemen die Arbeit anhaelt, wird nach dem
zweiten Mal abgeschaltet und schuetzt danach gar nichts. Diese Eigenschaft
laesst sich nicht durch Lesen belegen — sie braucht die Faelle selbst: kein
Remote, unerreichbares Remote, haengendes `fetch`, detached HEAD.

Jede Zusicherung hat eine Gegenprobe:

- `test_meldung_nennt_master_nicht_main` faellt, sobald jemand `main` fest
  verdrahtet. Genau diese Annahme hat schon einmal einen Branch 15 Commits alt
  werden lassen.
- `test_haengendes_fetch_blockiert_nicht` faellt, sobald das Timeout
  verschwindet: das gefaelschte `git` schlaeft 30 s, der Hook hat 8.
- `test_aktueller_stand_schweigt` faellt, sobald der Hook auch bei 0 redet.

Nur Standardbibliothek, kein Netz: das "Remote" ist ein bare-Repo im
Temp-Verzeichnis.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / ".claude" / "hooks" / "session-start.sh"

GIT_IDENT = {
    "GIT_AUTHOR_NAME": "Test",
    "GIT_AUTHOR_EMAIL": "test@example.invalid",
    "GIT_COMMITTER_NAME": "Test",
    "GIT_COMMITTER_EMAIL": "test@example.invalid",
}


def git(*args: str, cwd: Path) -> str:
    env = {**os.environ, **GIT_IDENT}
    out = subprocess.run(
        ["git", *args], cwd=cwd, env=env, capture_output=True, text=True, check=True
    )
    return out.stdout.strip()


def commit(repo: Path, name: str) -> None:
    (repo / name).write_text(name, encoding="utf-8")
    git("add", name, cwd=repo)
    git("commit", "-m", name, cwd=repo)


class HookHarness(unittest.TestCase):
    """Baut ein bare-"Remote", einen Autoren-Klon und einen Konsumenten-Klon."""

    default_branch = "main"

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)

        self.origin = self.tmp / "origin.git"
        self.origin.mkdir()
        git("init", "--bare", "-q", cwd=self.origin)
        # Nicht `--initial-branch` (setzt neueres git voraus): HEAD direkt setzen.
        git("symbolic-ref", "HEAD", f"refs/heads/{self.default_branch}", cwd=self.origin)

        self.author = self.tmp / "author"
        git("clone", "-q", str(self.origin), str(self.author), cwd=self.tmp)
        git("checkout", "-q", "-b", self.default_branch, cwd=self.author)
        commit(self.author, "erster")
        git("push", "-q", "-u", "origin", self.default_branch, cwd=self.author)

        self.clone = self.tmp / "klon"
        git("clone", "-q", str(self.origin), str(self.clone), cwd=self.tmp)

    def advance_origin(self, count: int) -> None:
        """Schiebt `count` Commits ins Remote, an denen der Klon vorbeilaeuft."""
        for i in range(count):
            commit(self.author, f"neu-{i}")
        git("push", "-q", "origin", self.default_branch, cwd=self.author)

    def run_hook(
        self,
        repo: Path | None = None,
        source: str = "startup",
        extra_path: Path | None = None,
    ) -> subprocess.CompletedProcess[str]:
        repo = repo or self.clone
        env = {**os.environ, **GIT_IDENT, "CLAUDE_PROJECT_DIR": str(repo)}
        if extra_path is not None:
            env["PATH"] = f"{extra_path}{os.pathsep}{env['PATH']}"
        payload = json.dumps({"hook_event_name": "SessionStart", "source": source})
        return subprocess.run(
            ["bash", str(HOOK)],
            input=payload,
            cwd=str(self.tmp),
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )


class TestMeldung(HookHarness):
    def test_rueckstand_wird_gemeldet(self) -> None:
        self.advance_origin(3)
        res = self.run_hook()
        self.assertEqual(res.returncode, 0)
        self.assertIn("3 Commits", res.stdout)
        self.assertIn("veraltet", res.stdout)

    def test_ein_commit_im_singular(self) -> None:
        """Gegenprobe zu einem hartcodierten "Commits"."""
        self.advance_origin(1)
        res = self.run_hook()
        self.assertIn("1 Commit hinter", res.stdout)
        self.assertNotIn("1 Commits", res.stdout)

    def test_auf_dem_default_branch_wird_gepullt(self) -> None:
        self.advance_origin(2)
        res = self.run_hook()
        self.assertIn(f"git pull --ff-only origin {self.default_branch}", res.stdout)
        self.assertNotIn("git fetch origin", res.stdout)

    def test_auf_einem_feature_branch_nur_fetch(self) -> None:
        """`pull` bewegt IMMER den ausgecheckten Branch, nicht den getippten.

        Wer auf einem Feature-Branch `git pull --ff-only origin main` ausfuehrt,
        zieht den Feature-Branch auf main vor und hat danach fremde Commits
        darauf. Am 20.8.2026 genau so passiert. Auf einem Feature-Branch darf
        der Hook darum nur `fetch` vorschlagen — das bewegt HEAD nicht.

        Gegenprobe: Mit einem unbedingten `pull`-Vorschlag faellt dieser Test.
        """
        self.advance_origin(2)
        git("checkout", "-q", "-b", "thema", cwd=self.clone)
        res = self.run_hook()
        self.assertIn(f"git fetch origin {self.default_branch}", res.stdout)
        self.assertNotIn("git pull", res.stdout)
        self.assertIn("thema", res.stdout)

    def test_detached_head_bekommt_auch_nur_fetch(self) -> None:
        """Auf einen detached HEAD laesst sich ohnehin nicht sinnvoll pullen."""
        self.advance_origin(2)
        git("checkout", "-q", "--detach", "HEAD", cwd=self.clone)
        res = self.run_hook()
        self.assertIn(f"git fetch origin {self.default_branch}", res.stdout)
        self.assertNotIn("git pull", res.stdout)
        self.assertIn("detached", res.stdout)

    def test_aktueller_stand_schweigt(self) -> None:
        res = self.run_hook()
        self.assertEqual(res.returncode, 0)
        self.assertEqual(res.stdout.strip(), "")

    def test_vorschlag_laeuft_auch_in_powershell(self) -> None:
        """Der vorgeschlagene Befehl darf kein `&&` enthalten.

        Windows PowerShell 5.1 kennt `&&` nicht und bricht mit «Das Token "&&"
        ist in dieser Version kein gueltiges Anweisungstrennzeichen» ab — der
        Vorschlag scheitert also ausgerechnet auf der Maschine, der er helfen
        soll. Gemeldet am 20.8.2026 aus einer PowerShell-Sitzung.

        Gegenprobe: Mit `git fetch ... && git merge ...` faellt dieser Test.
        """
        self.advance_origin(2)
        res = self.run_hook()
        self.assertNotIn("&&", res.stdout)

        # Gegenprobe auch fuer den Feature-Branch-Zweig: dort steht ein anderer
        # Befehl, `&&` darf auch dort nicht auftauchen.
        git("checkout", "-q", "-b", "thema", cwd=self.clone)
        self.assertNotIn("&&", self.run_hook().stdout)

    def test_grund_steht_in_der_meldung(self) -> None:
        """Die Meldung erklaert, warum sie da ist — sonst wird sie weggeklickt."""
        self.advance_origin(2)
        res = self.run_hook()
        self.assertIn("rote CI", res.stdout)

    def test_nach_compact_schweigt_er(self) -> None:
        self.advance_origin(2)
        self.assertEqual(self.run_hook(source="compact").stdout.strip(), "")
        self.assertEqual(self.run_hook(source="clear").stdout.strip(), "")
        # Gegenprobe: bei `resume` meldet er sehr wohl.
        self.assertIn("2 Commits", self.run_hook(source="resume").stdout)


class TestDefaultBranchMaster(HookHarness):
    """Drei Server im Portfolio heissen ihren Default-Branch `master`."""

    default_branch = "master"

    def test_meldung_nennt_master_nicht_main(self) -> None:
        self.advance_origin(2)
        res = self.run_hook()
        self.assertEqual(res.returncode, 0)
        self.assertIn("origin/master", res.stdout)
        self.assertNotIn("origin/main", res.stdout)

    def test_ohne_lokale_notiz_wird_das_remote_gefragt(self) -> None:
        """Ohne refs/remotes/origin/HEAD bleibt nur `git ls-remote --symref`."""
        self.advance_origin(2)
        git("update-ref", "-d", "refs/remotes/origin/HEAD", cwd=self.clone)
        res = self.run_hook()
        self.assertIn("origin/master", res.stdout)


class TestBlockiertNie(HookHarness):
    """Jeder dieser Faelle geht still durch: Exit 0, keine Ausgabe."""

    def assert_still(self, res: subprocess.CompletedProcess[str]) -> None:
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(res.stdout.strip(), "")

    def test_kein_remote(self) -> None:
        self.advance_origin(2)
        git("remote", "remove", "origin", cwd=self.clone)
        self.assert_still(self.run_hook())

    def test_unerreichbares_remote(self) -> None:
        self.advance_origin(2)
        git("remote", "set-url", "origin", str(self.tmp / "gibt-es-nicht.git"), cwd=self.clone)
        git("update-ref", "-d", "refs/remotes/origin/HEAD", cwd=self.clone)
        self.assert_still(self.run_hook())

    def test_kein_git_repo(self) -> None:
        plain = self.tmp / "kein-repo"
        plain.mkdir()
        self.assert_still(self.run_hook(repo=plain))

    def test_repo_ohne_commit(self) -> None:
        leer = self.tmp / "leer"
        leer.mkdir()
        git("init", "-q", cwd=leer)
        git("remote", "add", "origin", str(self.origin), cwd=leer)
        self.assert_still(self.run_hook(repo=leer))

    def test_verzeichnis_existiert_nicht(self) -> None:
        self.assert_still(self.run_hook(repo=self.tmp / "weg"))

    def test_detached_head_meldet_trotzdem(self) -> None:
        """Detached HEAD ist kein Fehlerfall — `HEAD..FETCH_HEAD` gilt weiter."""
        self.advance_origin(2)
        git("checkout", "-q", "--detach", "HEAD", cwd=self.clone)
        res = self.run_hook()
        self.assertEqual(res.returncode, 0)
        self.assertIn("2 Commits", res.stdout)

    def test_scheiterndes_git_kommando_blockiert_nicht(self) -> None:
        """Verhaltens-Gegenprobe zu `set -e`.

        Das gefaelschte `git` laesst alles durch und laesst nur `rev-list`
        scheitern — der eine Aufruf, dessen Ergebnis nicht per `|| exit 0`
        abgesichert ist, weil es in einer Zuweisung landet. Mit `set -e` bricht
        der Hook dort mit Exit-Code != 0 ab und blockiert die Session; ohne
        `set -e` faengt das `case` den leeren Wert und der Hook endet still.
        """
        echtes_git = shutil.which("git")
        self.assertIsNotNone(echtes_git)

        self.advance_origin(2)
        bin_dir = self.tmp / "bin-revlist"
        bin_dir.mkdir()
        fake = bin_dir / "git"
        fake.write_text(
            "#!/bin/sh\n"
            'for a in "$@"; do\n'
            '  if [ "$a" = "rev-list" ]; then exit 1; fi\n'
            "done\n"
            f'exec {echtes_git} "$@"\n',
            encoding="utf-8",
        )
        fake.chmod(0o755)

        self.assert_still(self.run_hook(extra_path=bin_dir))

    def test_haengendes_fetch_blockiert_nicht(self) -> None:
        """Das gefaelschte `git` schlaeft 30 s beim `fetch`. Der Hook hat 8.

        Gegenprobe zum Timeout: Ohne `run_limited` liefe dieser Test in den
        60-s-Deckel von `subprocess.run` und faellt.
        """
        if shutil.which("timeout") is None and shutil.which("gtimeout") is None:
            self.skipTest("weder timeout noch gtimeout vorhanden")
        echtes_git = shutil.which("git")
        self.assertIsNotNone(echtes_git)

        self.advance_origin(2)
        bin_dir = self.tmp / "bin"
        bin_dir.mkdir()
        fake = bin_dir / "git"
        fake.write_text(
            "#!/bin/sh\n"
            'for a in "$@"; do\n'
            '  if [ "$a" = "fetch" ]; then sleep 30; exit 0; fi\n'
            "done\n"
            f'exec {echtes_git} "$@"\n',
            encoding="utf-8",
        )
        fake.chmod(0o755)

        start = time.monotonic()
        res = self.run_hook(extra_path=bin_dir)
        dauer = time.monotonic() - start

        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(res.stdout.strip(), "")
        self.assertLess(dauer, 20, f"Hook lief {dauer:.1f}s — das Timeout greift nicht")


class TestRegistrierung(unittest.TestCase):
    """Ein Hook, der nicht in settings.json steht, laeuft nie."""

    def test_hook_ist_ausfuehrbar(self) -> None:
        self.assertTrue(os.access(HOOK, os.X_OK), "session-start.sh ist nicht ausfuehrbar")

    def test_settings_registrieren_den_hook(self) -> None:
        settings = json.loads(
            (HOOK.parents[1] / "settings.json").read_text(encoding="utf-8"),
        )
        eintraege = settings["hooks"]["SessionStart"]
        befehle = [h["command"] for gruppe in eintraege for h in gruppe["hooks"]]
        self.assertIn("$CLAUDE_PROJECT_DIR/.claude/hooks/session-start.sh", befehle)

    def test_kein_set_e(self) -> None:
        """`set -e` wuerde den Hook bei jedem fehlschlagenden Kommando abbrechen
        — mit Exit-Code != 0, und das blockiert die Session."""
        quelle = HOOK.read_text(encoding="utf-8")
        for verbotene_zeile in ("set -e", "set -euo", "set -eu"):
            self.assertNotIn(f"\n{verbotene_zeile}", quelle)


if __name__ == "__main__":
    unittest.main()
