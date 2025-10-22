# Release Scripts

## release.sh

Automated release script for bumping versions, creating git tags, and pushing to remote.

### Usage

```bash
./scripts/release.sh <package> <bump_type>
```

**Arguments:**
- `package` - Which package to release: `core`, `sdk-py`, `sdk-js`, or `all`
- `bump_type` - Version bump: `patch`, `minor`, or `major`

### Examples

```bash
# Release core with a patch bump (e.g., 0.1.3 → 0.1.4)
./scripts/release.sh core patch

# Release Python SDK with a minor bump (e.g., 0.1.3 → 0.2.0)
./scripts/release.sh sdk-py minor

# Release JavaScript SDK with a major bump (e.g., 0.1.3 → 1.0.0)
./scripts/release.sh sdk-js major

# Release all packages with a patch bump
./scripts/release.sh all patch
```

### What It Does

1. **Validates environment:**
   - Checks you're in a git repository
   - Ensures working directory is clean
   - Validates bump type

2. **Bumps versions:**
   - Updates `pyproject.toml` for Python packages
   - Updates `package.json` for JavaScript packages
   - Follows semantic versioning (major.minor.patch)

3. **Creates git commits:**
   - Format: `chore(<package>): release v<version>`
   - One commit per package

4. **Creates git tags:**
   - Format: `<package>-v<version>`
   - Examples: `core-v0.1.4`, `sdk-py-v0.2.0`, `sdk-js-v1.0.0`

5. **Pushes to remote:**
   - Pushes commits to current branch
   - Pushes all new tags

6. **Triggers CI/CD:**
   - GitHub Actions workflows automatically triggered by tags
   - Runs tests, builds packages, publishes to registries

### Version Bumping

- **patch** (`0.1.3 → 0.1.4`): Bug fixes, backwards compatible
- **minor** (`0.1.3 → 0.2.0`): New features, backwards compatible
- **major** (`0.1.3 → 1.0.0`): Breaking changes

### Prerequisites

- Clean working directory (no uncommitted changes)
- Push access to remote repository
- Proper Git configuration (user.name, user.email)

### Troubleshooting

**"Working directory is not clean"**
```bash
# Commit or stash your changes first
git status
git add .
git commit -m "your changes"
# OR
git stash
```

**"Not in a git repository"**
```bash
# Run from the repository root
cd /path/to/business-use
./scripts/release.sh core patch
```

**Push failed**
```bash
# Check your remote configuration
git remote -v

# Ensure you have push access
git push --dry-run
```

### Manual Release (Alternative)

If you prefer manual control:

```bash
# 1. Manually update version in files
# core/pyproject.toml or sdk-js/package.json

# 2. Commit changes
git add .
git commit -m "chore(core): release v0.1.4"

# 3. Create tag
git tag core-v0.1.4

# 4. Push
git push origin main --tags
```

### CI/CD Workflows

After pushing tags, GitHub Actions will:

- **core-v\***: `.github/workflows/release-core.yaml`
  - Run format, lint, type checks
  - Build Python package
  - Publish to PyPI

- **sdk-py-v\***: `.github/workflows/release-sdk-py.yaml`
  - Run tests and checks
  - Build Python package
  - Publish to PyPI

- **sdk-js-v\***: `.github/workflows/release-sdk-js.yaml`
  - Run tests and checks
  - Build TypeScript package
  - Publish to npm

Monitor workflows at: https://github.com/desplega-ai/business-use/actions
