# Testing

OpenYuGi has an automated `pytest` suite under `tests/`. This guide covers how
to run it and the verification approach used when developing the edition,
owned-printing-image, rarity, and deployment features.

## Running the suite

From the repository root, in an environment with the project dependencies
installed:

```bash
python -m pytest tests/
```

Some tests use `async def` and require `pytest-asyncio`:

```bash
python -m pip install pytest pytest-asyncio
python -m pytest tests/
```

### Running inside the Docker image

The project has a heavy dependency stack (torch, OpenCV, EasyOCR, DocTR,
Ultralytics). The simplest way to get a complete, consistent environment is to
run the suite inside the built image, mounting the working tree:

```bash
docker build -t openyugi:latest .
docker run --rm --user 0:0 --entrypoint sh -v "$PWD":/work -w /work openyugi:latest -c '
  pip install pytest pytest-asyncio >/dev/null 2>&1
  mkdir -p /app/data/scans
  python -m pytest tests/ -q
'
```

Notes:
- Run as `--user 0:0` for the test invocation so `pip install pytest` can write
  into the image's virtualenv (the app itself runs as uid 1000).
- `mkdir -p /app/data/scans` is needed because importing `main` registers a
  static-files route for that directory.

## Test isolation rules

Per the contributor guidelines, tests must:
- Write any user data to a **temporary directory**, never the real `data/`.
- Mock `nicegui`, `cv2`/OpenCV, `requests`, and other heavy or networked
  integrations where the test does not specifically exercise them.

Several tests set `OPENYUGI_CONFIG_FILE` to a temp path so `ConfigManager`
reads/writes an isolated config.

## Verification approach for recent features

The edition, owned-printing-image, and rarity work was verified with a mix of
unit tests and bounded live checks:

### Data model and editor (edition)
- `tests/test_edition_support.py` covers the `CollectionEntry` migration in both
  directions (old `first_edition` → `edition`, and `edition` → `first_edition`),
  the default (`Unlimited Edition`), and `CollectionEditor` entry identity —
  asserting that 1st / Unlimited / Limited of the same card are **distinct**
  stacks while identical editions **merge**. A JSON round-trip confirms the
  value survives save/load.

### Yugipedia printing-image resolver
- `tests/test_yugipedia_service.py` mocks `requests.get` with representative
  MediaWiki `search` + `imageinfo` responses and asserts the resolver:
  - matches the owned **rarity** code in the file name (e.g. `-UtR-`),
  - prefers the requested **edition** (`1E`/`UE`/`LE`) and resolves
    Limited-only promos,
  - applies **region fallback** (`EN → NA → EU`),
  - **excludes novelty variants** (`GC` Giant Card, `VG` Video Game) in favor of
    standard files, and
  - reports the resolved edition via `return_meta=True`.
- These behaviors were additionally spot-checked against the **live** Yugipedia
  API inside the container for a handful of real cards (e.g. Stardust Dragon
  `TDGS-EN040`, Cyber Esper `CDIP-EN045`, Salamandra `SDD-EN003`, and
  Giant-Card cases) to confirm the mocked responses matched reality.

### Image cache and batch
- `tests/test_printing_image_manager.py` checks the per-printing cache key is
  sanitized and that rarity and edition produce distinct keys/paths/URLs.
- `tests/test_printing_image_service.py` mocks persistence and the resolver to
  verify the batch collects distinct `(set_code, language, rarity, edition)`
  printings and reports accurate downloaded/skipped/failed counts.

### Rarity mappings
- `tests/test_yugipedia_service.py` asserts the corrected abbreviation →
  full-name mapping (including the previously wrong `UScR`/`GR`).
- `tests/test_rarity_constants.py` asserts `RARITY_ABBREVIATIONS` and that every
  primary rarity is present in `RARITY_RANKING` (so it is filterable and sorts
  deterministically) with no duplicates.

### Regression safety
The edition change was made **additively** — `first_edition` is retained as a
synced compatibility mirror rather than removed — specifically so the existing
suite keeps passing. The full suite was run after each change; the edition,
printing-image, rarity, and Docker work landed with the pre-existing tests
green.

### Known environment-only test failures
A group of UI/integration tests import a shared `tests.mock_imports` helper (or
import `main`, which registers static routes). In an ad-hoc runner without the
project's rootdir/path setup these fail at **collection** time with
`ModuleNotFoundError: No module named 'tests.mock_imports'` or a missing
`data/scans` directory. These are harness/path issues unrelated to feature
changes; run `pytest` from the repository root (so `tests/` is importable) and
ensure `data/scans` exists to avoid them.
