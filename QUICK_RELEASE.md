# Quick Release Guide

## Easiest Way: Tag-Based Release 🚀

Just update the version, commit, tag, and push. CI handles the rest!

### Core CLI

```bash
# 1. Update version
vim core/pyproject.toml  # Change version = "0.1.0" to "0.1.1"

# 2. Commit and tag
git add core/pyproject.toml
git commit -m "chore(core): bump version to 0.1.1"
git tag core-v0.1.1

# 3. Push (triggers automatic release)
git push origin main --tags
```

### Python SDK

```bash
# 1. Update versions
vim sdk-py/pyproject.toml  # version = "0.1.1"
vim sdk-py/src/business_use/__init__.py  # __version__ = "0.1.1"

# 2. Commit and tag
git add sdk-py/pyproject.toml sdk-py/src/business_use/__init__.py
git commit -m "chore(sdk-py): bump version to 0.1.1"
git tag sdk-py-v0.1.1

# 3. Push (triggers automatic release)
git push origin main --tags
```

### JavaScript SDK

```bash
# 1. Update versions
cd sdk-js
pnpm version 0.1.1 --no-git-tag-version
vim src/index.ts  # export const version = '0.1.1'

# 2. Commit and tag
git add package.json src/index.ts
git commit -m "chore(sdk-js): bump version to 0.1.1"
git tag sdk-js-v0.1.1

# 3. Push (triggers automatic release)
git push origin main --tags
```

## What Happens Next?

Once you push the tag:
1. ✅ GitHub Actions workflow triggers automatically
2. ✅ Runs all tests and checks
3. ✅ Builds the package
4. ✅ Publishes to PyPI or npm
5. ✅ Done! Check the Actions tab for progress

## Tag Naming

- Core: `core-v0.1.1`
- Python SDK: `sdk-py-v0.1.1`
- JavaScript SDK: `sdk-js-v0.1.1`

## Alternative: Manual Workflow Trigger

Go to **Actions** → Select workflow → **Run workflow** → Choose version bump type

## Need More Details?

See [RELEASING.md](./RELEASING.md) for complete documentation.
