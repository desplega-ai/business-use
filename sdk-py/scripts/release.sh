#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if version type is provided
if [ -z "$1" ]; then
    echo -e "${RED}Error: Version bump type required (patch, minor, or major)${NC}"
    echo "Usage: ./scripts/release.sh [patch|minor|major]"
    exit 1
fi

VERSION_TYPE=$1

# Validate version type
if [[ ! "$VERSION_TYPE" =~ ^(patch|minor|major)$ ]]; then
    echo -e "${RED}Error: Invalid version type. Must be patch, minor, or major${NC}"
    exit 1
fi

echo -e "${GREEN}Starting release process for sdk-py...${NC}"

# Get current version
CURRENT_VERSION=$(grep '^version = ' pyproject.toml | sed 's/version = "\(.*\)"/\1/')
echo -e "${YELLOW}Current version: $CURRENT_VERSION${NC}"

# Parse version
IFS='.' read -r major minor patch <<< "$CURRENT_VERSION"

# Calculate new version
case "$VERSION_TYPE" in
    major)
        NEW_VERSION="$((major + 1)).0.0"
        ;;
    minor)
        NEW_VERSION="${major}.$((minor + 1)).0"
        ;;
    patch)
        NEW_VERSION="${major}.${minor}.$((patch + 1))"
        ;;
esac

echo -e "${YELLOW}New version: $NEW_VERSION${NC}"

# Confirm release
read -p "Do you want to release version $NEW_VERSION? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${RED}Release cancelled${NC}"
    exit 1
fi

# Update version in files
echo -e "${GREEN}Updating version in files...${NC}"
sed -i.bak "s/version = \".*\"/version = \"$NEW_VERSION\"/" pyproject.toml
sed -i.bak "s/__version__ = \".*\"/__version__ = \"$NEW_VERSION\"/" src/business_use/__init__.py
rm pyproject.toml.bak src/business_use/__init__.py.bak

# Run checks
echo -e "${GREEN}Running format and lint checks...${NC}"
uv run ruff format --check src/
uv run ruff check src/
uv run mypy src/

# Build package
echo -e "${GREEN}Building package...${NC}"
uv pip install --system build twine
python -m build

# Check package
echo -e "${GREEN}Checking package...${NC}"
twine check dist/*

# Publish to PyPI
echo -e "${GREEN}Publishing to PyPI...${NC}"
echo -e "${YELLOW}Note: Make sure you have PyPI credentials configured${NC}"
twine upload dist/*

# Create git tag
echo -e "${GREEN}Creating git tag...${NC}"
git add pyproject.toml src/business_use/__init__.py
git commit -m "chore(sdk-py): release v$NEW_VERSION"
git tag "sdk-py-v$NEW_VERSION"

echo -e "${GREEN}Release complete!${NC}"
echo -e "${YELLOW}Don't forget to push the changes:${NC}"
echo "  git push origin main --tags"
