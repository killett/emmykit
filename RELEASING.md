# Releasing emmykit

Pushing a `v*` tag to GitHub is what publishes to PyPI.
`.github/workflows/release.yml` builds the package, checks it, and uploads it.
Nothing is uploaded from a laptop, and no API token is needed.

## One-time setup (done 2026-10-19, recorded so it can be redone)

PyPI publishes through **Trusted Publishing** (OIDC). There is no token in the
repository, in GitHub secrets, or on any machine.

- **PyPI:** <https://pypi.org/manage/project/emmykit/settings/publishing/> has a
  GitHub publisher with these settings:

  | Field | Value |
  | --- | --- |
  | Owner | `killett` |
  | Repository name | `emmykit` |
  | Workflow name | `release.yml` |
  | Environment name | `pypi` |

- **GitHub:** the repository has an environment named `pypi` (Settings →
  Environments). The publish job declares `environment: pypi` and
  `permissions: id-token: write`; without both, PyPI rejects the upload.

Renaming the workflow file or the environment breaks publishing until the PyPI
entry is changed to match.

## Cutting a release

1. Make sure everything for the release is on `main`, and the full suite passes:
   `pixi run -q python -m pytest`.
2. Bump `__version__` in `src/emmykit/_version.py`. It is the only place the
   number lives; hatchling reads it at build time. Rename the CHANGELOG's
   `[Unreleased]` items to `## [X.Y.Z] - YYYY-MM-DD`, leaving an empty
   `## [Unreleased]` above them. Commit both as `chore(release): X.Y.Z`.
3. Tag it with an annotated tag: `git tag -a vX.Y.Z -m "emmykit X.Y.Z"`.
4. Optionally check the build first: `pixi run -q python -m build`, then
   `uvx twine check --strict dist/*`. A local tag is cheap to delete and redo.
5. Push `main`, then the tag: `git push origin main vX.Y.Z`. **The tag push is
   the irreversible step.**
6. Watch the run with `gh run watch`. The build job:
   - checks that the tag equals `__version__`;
   - checks that the wheel is pure Python;
   - imports the wheel with no extras installed;
   - runs `twine check --strict`.

   The publish job runs only after all of that passes.
7. Check the release from outside with `scripts/smoke_pypi.sh --pypi --version
   X.Y.Z`, and again with `--bare`. Wait a minute first, because PyPI's index is
   cached and can lag.

## PyPI is immutable

A filename uploaded to PyPI can never be reused, not even after a yank or a
delete.

- **Nothing uploaded yet** (the build failed, or the publish job failed before
  transferring a file): delete the tag with `git tag -d vX.Y.Z` and
  `git push origin :refs/tags/vX.Y.Z`, fix the problem, and tag the same
  version again.
- **Something uploaded:** that version number is spent. Fix the problem and
  release the next patch version.
