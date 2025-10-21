# Release Guide

This document describes how to release each component of the Business-Use monorepo.

## Table of Contents

1. [Core Backend](#core-backend)
2. [Python SDK](#python-sdk)
3. [JavaScript SDK](#javascript-sdk)
4. [UI](#ui)

---

## Core Backend

The core backend is released as a Python package and can be used via `uvx` for zero-install CLI usage.

### Prerequisites

- Python 3.12+
- `uv` installed
- PyPI account with appropriate permissions
- Git tags for versioning

### Release Steps

#### 1. Update Version

Edit `core/pyproject.toml`:

```toml
[project]
name = "business-use-core"
version = "0.2.0"  # Update this
```

#### 2. Update Changelog

Add release notes to `core/CHANGELOG.md` (create if doesn't exist):

```markdown
## [0.2.0] - 2025-01-22

### Added
- New feature X
- New CLI command Y

### Fixed
- Bug fix Z

### Changed
- Breaking change W
```

#### 3. Run Tests

```bash
cd core
uv sync
uv run pytest
uv run ruff check src/
uv run mypy src/
```

#### 4. Build Package

```bash
cd core
uv build
```

This creates files in `dist/`:
- `business_use_core-0.2.0.tar.gz` (source distribution)
- `business_use_core-0.2.0-py3-none-any.whl` (wheel)

#### 5. Test Installation Locally

```bash
# Test with pip
pip install dist/business_use_core-0.2.0-py3-none-any.whl

# Test with uvx (important!)
uvx --from dist/business_use_core-0.2.0-py3-none-any.whl business-use-core --help
```

#### 6. Publish to PyPI

```bash
cd core

# Publish to TestPyPI first (recommended)
uv publish --publish-url https://test.pypi.org/legacy/

# Test installation from TestPyPI
uvx --index-url https://test.pypi.org/simple/ business-use-core --version

# If everything looks good, publish to PyPI
uv publish
```

#### 7. Create Git Tag

```bash
git tag -a core-v0.2.0 -m "Release core v0.2.0"
git push origin core-v0.2.0
```

#### 8. Verify uvx Installation

```bash
# Users can now run without installation:
uvx business-use-core --version
uvx business-use-core serve
uvx business-use-core eval-run run_123 checkout
```

### Troubleshooting

**Issue: `uvx` can't find the package**
- Ensure `[project.scripts]` is defined in `pyproject.toml`:
  ```toml
  [project.scripts]
  business-use-core = "src.cli:main"
  ```

**Issue: Import errors when running**
- Check `[tool.hatch.build.targets.wheel]` includes `src`:
  ```toml
  [tool.hatch.build.targets.wheel]
  packages = ["src"]
  ```

---

## Python SDK

The Python SDK is released as a separate package (`business-use`) for user applications.

### Prerequisites

- Python 3.11+
- `uv` installed
- PyPI account with appropriate permissions

### Release Steps

#### 1. Update Version

Edit `sdk-py/pyproject.toml`:

```toml
[project]
name = "business-use"
version = "0.2.0"  # Update this
```

#### 2. Update Changelog

Add release notes to `sdk-py/CHANGELOG.md`:

```markdown
## [0.2.0] - 2025-01-22

### Added
- New `conditions` parameter for timeout constraints

### Fixed
- Fixed serialization of nested lambdas

### Breaking Changes
- Renamed `act()` and `assert_()` to unified `ensure()`
```

#### 3. Run Tests

```bash
cd sdk-py
uv sync
uv run pytest -v
uv run ruff check src/ tests/
uv run mypy src/
```

#### 4. Test with Example

```bash
cd sdk-py
uv run python example.py
```

Ensure the example runs without errors and events are sent to the backend.

#### 5. Build Package

```bash
cd sdk-py
uv build
```

#### 6. Test Installation

```bash
# Create a test virtual environment
python -m venv test-env
source test-env/bin/activate

# Install from wheel
pip install dist/business_use-0.2.0-py3-none-any.whl

# Test import
python -c "from business_use import initialize, ensure; print('OK')"

deactivate
rm -rf test-env
```

#### 7. Publish to PyPI

```bash
cd sdk-py

# Test on TestPyPI first
uv publish --publish-url https://test.pypi.org/legacy/

# Verify installation
pip install --index-url https://test.pypi.org/simple/ business-use==0.2.0

# Publish to PyPI
uv publish
```

#### 8. Create Git Tag

```bash
git tag -a sdk-py-v0.2.0 -m "Release Python SDK v0.2.0"
git push origin sdk-py-v0.2.0
```

#### 9. Verify Installation

```bash
# Users can now install:
pip install business-use

# Or with uv:
uv add business-use
```

---

## JavaScript SDK

The JavaScript/TypeScript SDK is released to npm.

### Prerequisites

- Node.js 18+
- pnpm installed
- npm account with appropriate permissions

### Release Steps

#### 1. Update Version

Edit `sdk-js/package.json`:

```json
{
  "name": "business-use",
  "version": "0.2.0"
}
```

#### 2. Update Changelog

Add release notes to `sdk-js/CHANGELOG.md`:

```markdown
## [0.2.0] - 2025-01-22

### Added
- Full type safety with generic parameters

### Fixed
- Fixed async function detection

### Breaking Changes
- Renamed `act()` and `assert()` to unified `ensure()`
```

#### 3. Run Tests

```bash
cd sdk-js
pnpm install
pnpm typecheck
pnpm lint
pnpm test:run
```

#### 4. Build Package

```bash
cd sdk-js
pnpm build
```

This creates:
- `dist/index.js` (ESM)
- `dist/index.cjs` (CommonJS)
- `dist/index.d.ts` (TypeScript definitions)

#### 5. Test Package Locally

```bash
cd sdk-js

# Pack the package
pnpm pack

# This creates business-use-0.2.0.tgz

# Test installation in a temporary project
mkdir /tmp/test-sdk-js && cd /tmp/test-sdk-js
npm init -y
npm install /path/to/business-use/sdk-js/business-use-0.2.0.tgz

# Test import
node -e "const { initialize, ensure } = require('business-use'); console.log('OK')"

# Cleanup
cd -
rm -rf /tmp/test-sdk-js
```

#### 6. Publish to npm

```bash
cd sdk-js

# Login to npm (if not already)
npm login

# Publish (dry run first)
npm publish --dry-run

# Publish to npm
npm publish
```

**Note**: If this is the first release, you may need to make the package public:
```bash
npm publish --access public
```

#### 7. Create Git Tag

```bash
git tag -a sdk-js-v0.2.0 -m "Release JavaScript SDK v0.2.0"
git push origin sdk-js-v0.2.0
```

#### 8. Verify Installation

```bash
# Users can now install:
pnpm add business-use
# or: npm install business-use
# or: yarn add business-use
```

---

## UI

The UI is typically not published as a package, but deployed as a web application.

### Release Steps

#### 1. Update Version

Edit `ui/package.json`:

```json
{
  "name": "business-use-ui",
  "version": "0.2.0"
}
```

#### 2. Run Checks

```bash
cd ui
pnpm install
pnpm typecheck
pnpm lint
pnpm build
```

#### 3. Test Production Build

```bash
cd ui
pnpm build
pnpm preview

# Open http://localhost:4173
# Verify all functionality works
```

#### 4. Deploy

The UI can be deployed to various platforms:

**Vercel:**
```bash
cd ui
vercel --prod
```

**Netlify:**
```bash
cd ui
netlify deploy --prod --dir=dist
```

**Docker:**
```bash
cd ui
docker build -t business-use-ui:0.2.0 .
docker run -p 5173:5173 business-use-ui:0.2.0
```

**Static Hosting (S3, CloudFlare Pages, etc.):**
```bash
cd ui
pnpm build
# Upload contents of dist/ to your static host
```

#### 5. Create Git Tag

```bash
git tag -a ui-v0.2.0 -m "Release UI v0.2.0"
git push origin ui-v0.2.0
```

---

## Full Release Workflow

When releasing all components together:

### 1. Update All Versions

Update version numbers in:
- `core/pyproject.toml`
- `sdk-py/pyproject.toml`
- `sdk-js/package.json`
- `ui/package.json`

### 2. Update Root README

Update any version badges or installation instructions in the root `README.md`.

### 3. Run All Tests

```bash
# Core
cd core && uv run pytest && cd ..

# Python SDK
cd sdk-py && uv run pytest && cd ..

# JavaScript SDK
cd sdk-js && pnpm test:run && cd ..

# UI
cd ui && pnpm typecheck && pnpm build && cd ..
```

### 4. Release in Order

Release in this order to avoid dependency issues:

1. **Core Backend** (other components depend on this)
2. **Python SDK**
3. **JavaScript SDK**
4. **UI**

### 5. Create GitHub Release

After all components are released:

1. Go to https://github.com/desplega-ai/business-use/releases
2. Click "Draft a new release"
3. Create tag: `v0.2.0`
4. Title: `v0.2.0`
5. Description:
   ```markdown
   ## Release v0.2.0

   ### Core Backend
   - Feature X
   - Bug fix Y

   ### Python SDK
   - Feature A
   - Bug fix B

   ### JavaScript SDK
   - Feature M
   - Bug fix N

   ### UI
   - Feature P
   - Bug fix Q

   ### Installation

   **Core:**
   ```bash
   uvx business-use-core serve
   ```

   **Python SDK:**
   ```bash
   pip install business-use==0.2.0
   ```

   **JavaScript SDK:**
   ```bash
   npm install business-use@0.2.0
   ```
   ```
6. Publish release

### 6. Verify Everything

```bash
# Core
uvx business-use-core --version

# Python SDK
pip install business-use==0.2.0

# JavaScript SDK
npm install business-use@0.2.0
```

---

## Versioning Strategy

We follow [Semantic Versioning](https://semver.org/):

- **MAJOR** (1.0.0): Breaking changes
- **MINOR** (0.1.0): New features, backward compatible
- **PATCH** (0.0.1): Bug fixes, backward compatible

### Examples

- `0.1.0` → `0.2.0`: Added new `conditions` parameter (backward compatible)
- `0.2.0` → `1.0.0`: Renamed `act()` to `ensure()` (breaking change)
- `1.0.0` → `1.0.1`: Fixed bug in serialization (bug fix)

---

## Rollback Procedure

If a release has critical issues:

### PyPI (Core & Python SDK)

**PyPI doesn't allow deleting releases**, but you can:

1. **Yank the release**:
   ```bash
   # This hides it from pip install, but still available if explicitly requested
   uv publish --yank business-use-core==0.2.0
   ```

2. **Release a patch**:
   ```bash
   # Fix the issue and release 0.2.1
   # Update version to 0.2.1
   uv publish
   ```

### npm (JavaScript SDK)

1. **Deprecate the release**:
   ```bash
   npm deprecate business-use@0.2.0 "Critical bug, please use 0.2.1"
   ```

2. **Release a patch**:
   ```bash
   # Fix the issue and release 0.2.1
   npm publish
   ```

---

## Checklist

Before any release, ensure:

- [ ] Version numbers updated in all relevant files
- [ ] Changelog updated with release notes
- [ ] All tests pass
- [ ] Examples run successfully
- [ ] Documentation updated (if needed)
- [ ] Breaking changes clearly documented
- [ ] Tested installation from published package
- [ ] Git tags created
- [ ] GitHub release created

---

## Questions?

If you have questions about the release process, please:

1. Check existing GitHub releases for examples
2. Open an issue: https://github.com/desplega-ai/business-use/issues
3. Contact maintainers: contact@desplega.ai
