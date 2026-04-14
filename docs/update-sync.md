# Update and Sync Mechanism

[← Back to README](../README.md) · [Docs index](README.md) · [Reference index](../reference/index.md)

---

**Last Updated:** 2026-04-14

How installation, release checking, reinstall/update, and release publishing work.
For end-user setup, see [install.md](install.md).

## Overview

The repo now has two public install entry points:

1. `gemini-skill-install` — the bootstrap installer package used by `uvx` / `pipx`
2. `setup/install.py` — the source-checkout / release-tarball launcher

Both paths feed the same shared install payload into `core.cli.install_main`.

## Install Payload

The single source of truth for installed files lives in
`core/cli/installer/payload.py`.

Installed into `~/.claude/skills/gemini/`:

```text
SKILL.md
VERSION
core/
adapters/
reference/
registry/
scripts/
setup/update.py
setup/requirements.txt
.checksums.json
.venv/
```

Not installed:

- `docs/`
- `tests/`
- `.git/`
- `.github/`
- `README.md`
- `setup/install.py`

## Install Flow

### Bootstrap installer path

When you run:

```bash
uvx --from git+https://github.com/reshinto/gemini-skill gemini-skill-install
```

or:

```bash
pipx run --spec git+https://github.com/reshinto/gemini-skill.git gemini-skill-install
```

the package:

1. Materializes the bundled payload into a temporary directory.
2. Calls the same `core.cli.install_main.main(...)` used by `setup/install.py`.
3. Installs or refreshes `~/.claude/skills/gemini`.

### Source checkout / tarball path

When you run:

```bash
python3 setup/install.py
```

the launcher:

1. Verifies the current interpreter is a stable CPython 3.9+ build.
2. Re-execs under `python3.N` if your current `python3` is prerelease, free-threaded, or otherwise incompatible for the SDK venv.
3. Delegates into the same `core.cli.install_main.main(...)`.

## Release Checking

The installed update launcher is intentionally small:

```bash
python3 ~/.claude/skills/gemini/setup/update.py
```

Current behavior:

1. Reads the installed `VERSION`
2. Queries GitHub Releases for the latest tag
3. Prints whether you are already up to date

It **does not yet download or apply an update in place**.

## Applying an Update

To move to a newer release, rerun the installer from a newer source.

### GitHub bootstrap path

```bash
uvx --from git+https://github.com/reshinto/gemini-skill gemini-skill-install
```

### Published PyPI path

```bash
uvx gemini-skill-install
```

If the bootstrap tool was installed with `pipx`:

```bash
pipx upgrade gemini-skill-install
gemini-skill-install
```

### Clone or release tarball path

```bash
python3 setup/install.py
```

Overwrite installs preserve the existing `.venv` directory and reuse the pinned
SDK install when the expected version is already present.

## Integrity and Drift Detection

The installer writes `~/.claude/skills/gemini/.checksums.json` immediately after
copying the runtime payload. `scripts/health_check.py` uses that manifest to
detect drift:

- missing manifest: legacy install or manual copy
- checksum mismatches: installed files were edited after install
- SDK drift: installed `google-genai` version differs from the pinned version in `setup/requirements.txt`

Release artifacts also include a top-level `checksums.txt`:

- the GitHub release tarball hash
- the wheel hash
- the sdist hash

## Model Registry Updates

Model registry changes ship in a new gemini-skill release. To pick up new model
IDs or updated defaults:

1. install the newer release
2. verify with `/gemini models`

`setup/update.py` does not fetch or rewrite `registry/models.json` on its own.

## Rollback

If a release regresses, reinstall from an older source:

### Older git tag or commit

```bash
git checkout <older-tag-or-commit>
python3 setup/install.py
```

### Older GitHub release artifact

Extract the older tarball and rerun `python3 setup/install.py`.

### Older PyPI package version

Once published to PyPI, install an older bootstrap tool version and rerun it:

```bash
pipx install --force 'gemini-skill-install==<older-version>'
gemini-skill-install
```

## Release Automation

Tagged releases (`v*`) run `.github/workflows/release.yml`.

The workflow now:

1. verifies that `VERSION` matches the tag
2. builds the release tarball
3. builds the Python wheel and sdist for `gemini-skill-install`
4. writes `checksums.txt`
5. creates the GitHub Release
6. publishes `gemini-skill-install` to PyPI via Trusted Publishing

### One-time PyPI setup

Before automatic PyPI publication works, maintainers must configure:

1. a GitHub environment named `pypi`
2. a PyPI Trusted Publisher for:
   - owner: `reshinto`
   - repo: `gemini-skill`
   - workflow: `release.yml`
   - environment: `pypi`
   - project: `gemini-skill-install`

## Cutting a Release

1. Bump [VERSION](../VERSION) on `main`
2. Commit and push that change
3. Run:

   ```bash
   bash scripts/tag_release.sh
   ```

   Or non-interactively:

   ```bash
   bash scripts/tag_release.sh --yes
   ```

4. The script reads `VERSION`, creates `v<VERSION>`, and pushes it to `origin`
5. GitHub Actions runs the release workflow
6. Verify the GitHub Release and the PyPI project page

## SDK Pin Bumps

When bumping `google-genai`:

1. Edit `setup/requirements.txt`
2. Re-run `python3 setup/install.py`
3. Run the live integration matrix under both backends
4. Run the bootstrap installer packaging tests and `python -m build`
5. Merge only after both the runtime install path and bootstrap package path are green

## Development Notes

If you change install payload contents, update these together:

- `core/cli/installer/payload.py`
- packaging build logic in `setup.py`
- release artifact contents in `.github/workflows/release.yml`
- end-user docs in `README.md` and `docs/install.md`
