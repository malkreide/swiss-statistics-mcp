# Releasing

Releases are automated by [`.github/workflows/release.yml`](.github/workflows/release.yml).
Pushing a version tag (`vX.Y.Z`) builds the package, publishes it to PyPI via
**Trusted Publishing** (OIDC — no stored API token), and creates the matching
GitHub Release with auto-generated notes.

## Versioning

`pyproject.toml`'s `version` is the **single source of truth**. The package's
`__version__` reads it back from the installed metadata
(`importlib.metadata.version`), so it never drifts. To change the version, edit
`pyproject.toml` only.

The project is Alpha (0.x): breaking tool changes may ship in a minor bump.

## One-time setup: PyPI Trusted Publisher

Trusted Publishing lets GitHub Actions publish to PyPI over OIDC without any
stored token. Configure it once (requires a PyPI account with rights to the
project name):

1. Sign in at <https://pypi.org>.
2. If the project does not exist yet, add a **pending** publisher under
   *Account → Publishing*; otherwise open the project's
   *Manage → Publishing* page.
3. Add a **GitHub Actions** publisher with:
   - **Owner:** `malkreide`
   - **Repository:** `swiss-statistics-mcp`
   - **Workflow name:** `release.yml`
   - **Environment:** `pypi`
4. (Recommended) In the GitHub repo, create an **Environment** named `pypi`
   under *Settings → Environments* and add any protection rules you want
   (e.g. required reviewer) — the `pypi-publish` job runs in this environment.

Until this is configured, the `pypi-publish` job will fail, but the
`github-release` job still runs (it is independent), so the GitHub Release is
created regardless. After configuring, you can re-run the failed job.

## Cutting a release

1. Update `CHANGELOG.md` (move `[Unreleased]` items under the new version).
2. Bump `version` in `pyproject.toml`.
3. Merge those changes to `main`.
4. Tag and push:

   ```bash
   git tag v0.6.0
   git push origin v0.6.0
   ```

5. Watch the **Release** workflow: it builds, publishes to PyPI, and creates the
   GitHub Release. Verify `pip install swiss-statistics-mcp==0.6.0` once it
   finishes.
