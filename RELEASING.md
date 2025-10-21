# Releasing Packages

This document describes how to release the business-use packages to PyPI and npm:
- **Core CLI** (`business-use-core`) - PyPI
- **Python SDK** (`business-use`) - PyPI
- **JavaScript SDK** (`business-use`) - npm

## Prerequisites

### For Python Packages (Core + SDK-PY)

1. **PyPI Account**: Create an account at https://pypi.org
2. **Trusted Publishing (Recommended)**: Configure GitHub Actions trusted publishing for both packages:

   **For business-use-core:**
   - Go to your PyPI account settings
   - Add a new "pending publisher" for GitHub Actions
   - Repository: `desplega-ai/business-use`
   - Workflow: `release.yaml`
   - Environment name: (leave blank)
   - PyPI Project Name: `business-use-core`

   **For business-use (Python SDK):**
   - Add another "pending publisher"
   - Repository: `desplega-ai/business-use`
   - Workflow: `release.yaml`
   - Environment name: (leave blank)
   - PyPI Project Name: `business-use`

   OR

3. **API Token (Alternative)**: Generate an API token and add it as `PYPI_TOKEN` secret in GitHub repository settings

### For JavaScript SDK (npm)

1. **npm Account**: Create an account at https://npmjs.com
2. **Authentication Token**:
   - Run `npm login` locally to authenticate
   - Generate an automation token at https://www.npmjs.com/settings/tokens
   - Add the token as `NPM_TOKEN` secret in GitHub repository settings

## Release Methods

There are three ways to release packages:
1. **Tag-based release** (Recommended) - Push a git tag to trigger automatic CI release
2. **Manual GitHub Actions** - Trigger workflow manually from GitHub UI
3. **Local release** - Run release script locally

---

## Method 1: Tag-Based Release (Recommended)

The easiest way to release is to create and push a git tag. This automatically triggers the CI workflow.

### Core CLI

```bash
cd core

# Update version manually in pyproject.toml
vim pyproject.toml  # Change version = "0.1.0" to "0.1.1"

# Commit the version change
git add pyproject.toml
git commit -m "chore(core): bump version to 0.1.1"

# Create and push tag
git tag core-v0.1.1
git push origin main --tags
```

The GitHub Actions workflow will automatically:
- Detect the tag push
- Build and test the package
- Publish to PyPI
- No additional commit needed (version already updated)

### Python SDK

```bash
cd sdk-py

# Update version in both files
vim pyproject.toml  # Change version = "0.1.0" to "0.1.1"
vim src/business_use/__init__.py  # Change __version__ = "0.1.0" to "0.1.1"

# Commit the version changes
git add pyproject.toml src/business_use/__init__.py
git commit -m "chore(sdk-py): bump version to 0.1.1"

# Create and push tag
git tag sdk-py-v0.1.1
git push origin main --tags
```

### JavaScript SDK

```bash
cd sdk-js

# Update version using pnpm
pnpm version 0.1.1 --no-git-tag-version

# Update version in src/index.ts
vim src/index.ts  # Change export const version = '0.1.0' to '0.1.1'

# Commit the version changes
git add package.json src/index.ts
git commit -m "chore(sdk-js): bump version to 0.1.1"

# Create and push tag
git tag sdk-js-v0.1.1
git push origin main --tags
```

**Tag naming convention:**
- Core: `core-v{version}` (e.g., `core-v0.1.1`)
- Python SDK: `sdk-py-v{version}` (e.g., `sdk-py-v0.1.1`)
- JavaScript SDK: `sdk-js-v{version}` (e.g., `sdk-js-v0.1.1`)

---

## Method 2: Manual GitHub Actions

You can also trigger releases manually from the GitHub UI. This method automatically bumps the version for you.

### Triggering a Release

Each package has its own dedicated workflow:

#### **Release Core CLI**
1. Go to your repository on GitHub: https://github.com/desplega-ai/business-use
2. Click on **Actions** tab
3. Select **Release Core CLI** workflow
4. Click **Run workflow**
5. Choose version bump: `patch`, `minor`, or `major`
6. Click **Run workflow**

#### **Release Python SDK**
1. Go to **Actions** tab
2. Select **Release Python SDK** workflow
3. Click **Run workflow**
4. Choose version bump: `patch`, `minor`, or `major`
5. Click **Run workflow**

#### **Release JavaScript SDK**
1. Go to **Actions** tab
2. Select **Release JavaScript SDK** workflow
3. Click **Run workflow**
4. Choose version bump: `patch`, `minor`, or `major`
5. Click **Run workflow**

Each workflow will:
- Automatically bump the version
- Run all checks (format, lint, type check, tests where applicable)
- Build the package
- Publish to PyPI or npm
- Create git commit and tag
- Push changes back to the repository

---

## Method 3: Local Release

### Core CLI

```bash
cd core

# Install dependencies
uv sync

# Run the release script
./scripts/release.sh [patch|minor|major]

# Example: Release a patch version (0.1.0 -> 0.1.1)
./scripts/release.sh patch

# Example: Release a minor version (0.1.0 -> 0.2.0)
./scripts/release.sh minor

# Example: Release a major version (0.1.0 -> 1.0.0)
./scripts/release.sh major
```

The script will:
1. Show current and new version
2. Ask for confirmation
3. Update version in `pyproject.toml`
4. Run format, lint, and type checks (Ruff, MyPy)
5. Build the package
6. Check package validity with Twine
7. Publish to PyPI as `business-use-core`
8. Create a git commit and tag (`core-v0.1.1`)
9. Remind you to push changes

**After release:**
```bash
# Push the changes and tags
git push origin main --tags
```

### Python SDK

```bash
cd sdk-py

# Install dependencies
uv sync

# Run the release script
./scripts/release.sh [patch|minor|major]

# Example: Release a patch version (0.1.0 -> 0.1.1)
./scripts/release.sh patch

# Example: Release a minor version (0.1.0 -> 0.2.0)
./scripts/release.sh minor

# Example: Release a major version (0.1.0 -> 1.0.0)
./scripts/release.sh major
```

The script will:
1. Show current and new version
2. Ask for confirmation
3. Update version in `pyproject.toml` and `src/business_use/__init__.py`
4. Run format and lint checks (Ruff, MyPy)
5. Build the package
6. Check package validity with Twine
7. Publish to PyPI (requires authentication)
8. Create a git commit and tag
9. Remind you to push changes

**After release:**
```bash
# Push the changes and tags
git push origin main --tags
```

### JavaScript SDK

```bash
cd sdk-js

# Install dependencies
pnpm install

# Run the release script
./scripts/release.sh [patch|minor|major]

# Example: Release a patch version (0.1.0 -> 0.1.1)
./scripts/release.sh patch

# Example: Release a minor version (0.1.0 -> 0.2.0)
./scripts/release.sh minor

# Example: Release a major version (0.1.0 -> 1.0.0)
./scripts/release.sh major
```

The script will:
1. Show current version
2. Bump version using pnpm
3. Ask for confirmation
4. Update version in `src/index.ts`
5. Run format, lint, and type checks
6. Build the package
7. Run tests
8. Publish to npm (requires authentication)
9. Create a git commit and tag
10. Remind you to push changes

**After release:**
```bash
# Push the changes and tags
git push origin main --tags
```

### Monitoring Releases (All Methods)

After triggering a release (via tag, manual workflow, or local script):

1. Watch the workflow run in the Actions tab (for CI-based releases)
2. Check for any errors in the logs
3. Verify the package appears on PyPI/npm:
   - Core CLI: https://pypi.org/project/business-use-core/
   - Python SDK: https://pypi.org/project/business-use/
   - JavaScript SDK: https://www.npmjs.com/package/business-use
4. Confirm the git tag was created

---

## Version Bumping Strategy

We follow [Semantic Versioning](https://semver.org/):

- **Patch** (0.1.0 → 0.1.1): Bug fixes, documentation updates
- **Minor** (0.1.0 → 0.2.0): New features, backward-compatible changes
- **Major** (0.1.0 → 1.0.0): Breaking changes, API redesigns

### When to bump versions:

| Change Type | Version Bump | Example |
|------------|--------------|---------|
| Bug fix | Patch | Fix batching issue |
| New optional parameter | Minor | Add `timeout_ms` option |
| New function/feature | Minor | Add new `ensure()` function |
| Breaking API change | Major | Remove `act()` and `assert()` |
| Documentation only | Patch | Update README examples |

---

## Troubleshooting

### PyPI: Authentication Failed

**Problem**: `twine upload` fails with authentication error

**Solutions**:
1. **Using trusted publishing (GitHub Actions)**: Ensure the workflow has `id-token: write` permission
2. **Using API token (local)**:
   ```bash
   # Create/update ~/.pypirc
   [pypi]
   username = __token__
   password = pypi-...your-token...
   ```

### npm: Authentication Failed

**Problem**: `pnpm publish` fails with authentication error

**Solutions**:
1. **Local release**: Run `npm login` to authenticate
2. **GitHub Actions**: Verify `NPM_TOKEN` secret is correctly set
3. Check token hasn't expired at https://www.npmjs.com/settings/tokens

### Build Checks Failing

**Problem**: Format, lint, or type check fails

**Solutions**:
```bash
# For Python SDK
cd sdk-py
uv run ruff format src/        # Auto-fix formatting
uv run ruff check src/ --fix   # Auto-fix linting issues
uv run mypy src/               # Check type errors manually

# For JavaScript SDK
cd sdk-js
pnpm run format               # Auto-fix formatting
pnpm run lint:fix            # Auto-fix linting issues
pnpm run typecheck           # Check type errors manually
```

### Git Tag Already Exists

**Problem**: Tag `sdk-py-v0.1.1` already exists

**Solutions**:
```bash
# Delete local tag
git tag -d sdk-py-v0.1.1

# Delete remote tag
git push origin :refs/tags/sdk-py-v0.1.1

# Re-run release script
```

### Package Already Published

**Problem**: Version `0.1.1` already exists on PyPI/npm

**Solutions**:
- You cannot overwrite published versions
- Bump to the next version instead
- If you need to republish, you must use a new version number

---

## Post-Release Checklist

After a successful release:

- [ ] Verify package appears on [PyPI](https://pypi.org/project/business-use/) or [npm](https://www.npmjs.com/package/business-use)
- [ ] Test installation: `pip install business-use` or `npm install business-use`
- [ ] Update examples to use published version (if desired)
- [ ] Announce release in relevant channels
- [ ] Update CHANGELOG (if you maintain one)
- [ ] Close related GitHub issues/PRs

---

## Tips

1. **Always test locally first**: Run the local release script in dry-run mode to catch issues early
2. **Release during low-traffic times**: Avoid releasing during peak hours
3. **Monitor after release**: Check package registry and test installation immediately
4. **Keep main branch clean**: Ensure all tests pass before releasing
5. **Coordinate releases**: If releasing both SDKs, ensure they're compatible

---

## Emergency Rollback

If a release has critical issues:

### For PyPI
- You cannot delete/unpublish versions
- Release a new patch version with the fix ASAP
- Add a warning in the GitHub README

### For npm
- You can unpublish within 72 hours: `npm unpublish business-use@0.1.1`
- After 72 hours, release a new patch version instead
- Deprecate the broken version: `npm deprecate business-use@0.1.1 "Critical bug, use 0.1.2 instead"`

---

## Questions?

If you encounter issues not covered here, check:
- [PyPI Publishing Guide](https://packaging.python.org/tutorials/packaging-projects/)
- [npm Publishing Guide](https://docs.npmjs.com/cli/v9/commands/npm-publish)
- GitHub Actions logs for detailed error messages
