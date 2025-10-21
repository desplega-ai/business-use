# Release Setup Guide

Quick guide to set up releases for business-use packages.

## 1. PyPI Setup (Python SDK) - Trusted Publishing ✨

**No secrets needed!** The workflow uses PyPI's trusted publishing feature.

### Steps:

1. **Create PyPI account** (if you don't have one):
   - Go to https://pypi.org/account/register/

2. **Add trusted publishers to PyPI** (you need to add TWO separate publishers):

   **First Publisher - business-use-core:**
   - Go to https://pypi.org/manage/account/publishing/
   - Click "Add a new pending publisher"
   - Fill in:
     - **PyPI Project Name**: `business-use-core`
     - **Owner**: `desplega-ai` (your GitHub org/username)
     - **Repository name**: `business-use`
     - **Workflow name**: `release-core.yaml`
     - **Environment name**: (leave empty)
   - Click "Add"

   **Second Publisher - business-use:**
   - Click "Add a new pending publisher" again
   - Fill in:
     - **PyPI Project Name**: `business-use`
     - **Owner**: `desplega-ai` (your GitHub org/username)
     - **Repository name**: `business-use`
     - **Workflow name**: `release-sdk-py.yaml`
     - **Environment name**: (leave empty)
   - Click "Add"

3. **Done!** The first time you run each workflow, it will automatically create the PyPI project.

### What is Trusted Publishing?

It's a secure way to publish without storing API tokens. GitHub Actions proves its identity to PyPI using OIDC tokens. More info: https://docs.pypi.org/trusted-publishers/

---

## 2. npm Setup (JavaScript SDK) - API Token

### Steps:

1. **Create npm account** (if you don't have one):
   - Go to https://www.npmjs.com/signup

2. **Generate automation token**:
   - Go to https://www.npmjs.com/settings/YOUR_USERNAME/tokens
   - Click "Generate New Token" → "Automation"
   - Copy the token (starts with `npm_...`)

3. **Add token to GitHub**:
   - Go to your GitHub repository: https://github.com/desplega-ai/business-use
   - Go to Settings → Secrets and variables → Actions
   - Click "New repository secret"
   - Name: `NPM_TOKEN`
   - Value: Paste your npm token
   - Click "Add secret"

4. **Done!** The workflow can now publish to npm.

---

## 3. Local Release Setup

If you want to release locally (not required for CI):

### For PyPI (local):

```bash
# Install twine
pip install twine

# Option 1: Use trusted publishing (requires browser)
# Just run: twine upload dist/*
# It will open a browser for authentication

# Option 2: Use API token
# Create ~/.pypirc file:
cat > ~/.pypirc << EOF
[pypi]
username = __token__
password = pypi-YOUR_TOKEN_HERE
EOF
chmod 600 ~/.pypirc
```

### For npm (local):

```bash
# Login to npm (interactive)
npm login

# That's it! Credentials are stored in ~/.npmrc
```

---

## 4. Verification

Test that everything is set up correctly:

### For GitHub Actions:

1. Go to Actions tab
2. Run one of the release workflows:
   - **Release Core CLI** - for `business-use-core`
   - **Release Python SDK** - for `business-use` (Python)
   - **Release JavaScript SDK** - for `business-use` (JavaScript)
3. Choose version: `patch`
4. Watch for any errors

### For local:

```bash
# Core CLI
cd core
./scripts/release.sh patch

# Python SDK
cd sdk-py
./scripts/release.sh patch

# JavaScript SDK
cd sdk-js
./scripts/release.sh patch
```

---

## Troubleshooting

### PyPI: "No pending publisher found"
- Make sure you added the pending publisher in PyPI settings
- Double-check repository name matches exactly: `desplega-ai/business-use`
- Workflow names must match:
  - For `business-use-core`: `release-core.yaml`
  - For `business-use` (SDK): `release-sdk-py.yaml`
- PyPI project names must match:
  - Core: `business-use-core`
  - SDK: `business-use`

### npm: "401 Unauthorized"
- Verify `NPM_TOKEN` secret exists in GitHub
- Check token hasn't expired: https://www.npmjs.com/settings/tokens
- Make sure token has "Automation" type (not "Read-only")

### GitHub Actions: Permission denied
- Check that workflow has these permissions:
  ```yaml
  permissions:
    contents: write
    id-token: write
  ```

---

## Summary Checklist

Before your first release:

- [ ] PyPI account created
- [ ] PyPI trusted publisher configured for `business-use-core`
- [ ] PyPI trusted publisher configured for `business-use` (Python SDK)
- [ ] npm account created
- [ ] npm automation token generated
- [ ] `NPM_TOKEN` secret added to GitHub repository
- [ ] Test workflow runs successful for all packages

After setup, you can release anytime via:
- **GitHub Actions UI**: Use the dedicated workflow for each package
  - Release Core CLI
  - Release Python SDK
  - Release JavaScript SDK
- **Locally**: `./scripts/release.sh [patch|minor|major]` in each package directory
