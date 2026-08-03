# Releasing

Releases are automated by [`.github/workflows/release.yml`](.github/workflows/release.yml),
which is the **only** workflow that publishes anything. Pushing a version tag
(`vX.Y.Z`) builds the package, publishes it to PyPI via **Trusted Publishing**
(OIDC — no stored API token), creates the matching GitHub Release with
auto-generated notes, and publishes the server to the MCP Registry.

The workflow triggers on the **tag push**, not on `release: published`. That is
deliberate: the GitHub Release is created by the workflow itself using the
`GITHUB_TOKEN`, and releases created that way do not trigger further workflow
runs — a publish job listening for `release: published` would simply never fire
on a tag-driven release.

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

   All four fields are matched exactly against the OIDC token's claims. The
   workflow name is the **file name** of the workflow, not its `name:` — it must
   read `release.yml`.
4. (Recommended) In the GitHub repo, create an **Environment** named `pypi`
   under *Settings → Environments* and add any protection rules you want
   (e.g. required reviewer) — the `pypi-publish` job runs in this environment.
   Note that a required reviewer holds the job (and the `publish-mcp` job behind
   it) until someone approves it; the run stays in *waiting* until then.

Until this is configured, the `pypi-publish` job will fail, but the
`github-release` job still runs (it is independent), so the GitHub Release is
created regardless. After configuring, you can re-run the failed job.

### Troubleshooting: `invalid-publisher`

```
Trusted publishing exchange failure:
* `invalid-publisher`: valid token, but no corresponding publisher
```

The OIDC token was issued fine — PyPI just has no publisher matching its
claims. It is a configuration mismatch on the PyPI side, never a code problem.
Compare the claims the action prints against the publisher on
*Manage → Publishing*, field by field:

| Claim in the log | Must equal the PyPI publisher field |
| --- | --- |
| `workflow_ref` (the `.github/workflows/<file>` part) | **Workflow name** |
| `environment` | **Environment** |
| `repository` (owner half) | **Owner** |
| `repository` (name half) | **Repository** |

The usual culprit is a renamed or split workflow file: the publisher still names
the old file. PyPI publishers cannot be edited — delete the stale one and add a
new one with the corrected fields.

## Cutting a release

1. Update `CHANGELOG.md` (move `[Unreleased]` items under the new version).
2. Bump `version` in `pyproject.toml`.
3. Merge those changes to `main`.
4. Tag and push:

   ```bash
   git tag v0.6.0
   git push origin v0.6.0
   ```

5. Watch the **Release** workflow: it builds, publishes to PyPI, creates the
   GitHub Release, and publishes to the MCP Registry. Verify
   `pip install swiss-statistics-mcp==0.6.0` once it finishes.

Do **not** create the GitHub Release by hand in the web UI — that creates the
tag as a side effect and produces a second, duplicate `Release` run.
