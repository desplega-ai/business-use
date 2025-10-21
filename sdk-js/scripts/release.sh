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

echo -e "${GREEN}Starting release process for sdk-js...${NC}"

# Get current version
CURRENT_VERSION=$(node -p "require('./package.json').version")
echo -e "${YELLOW}Current version: $CURRENT_VERSION${NC}"

# Bump version using pnpm
echo -e "${GREEN}Bumping version...${NC}"
pnpm version $VERSION_TYPE --no-git-tag-version

# Get new version
NEW_VERSION=$(node -p "require('./package.json').version")
echo -e "${YELLOW}New version: $NEW_VERSION${NC}"

# Confirm release
read -p "Do you want to release version $NEW_VERSION? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${RED}Release cancelled${NC}"
    # Revert version bump
    git checkout package.json
    exit 1
fi

# Update version in src/index.ts
echo -e "${GREEN}Updating version in src/index.ts...${NC}"
sed -i.bak "s/export const version = '.*'/export const version = '$NEW_VERSION'/" src/index.ts
rm src/index.ts.bak

# Run checks
echo -e "${GREEN}Running format and lint checks...${NC}"
pnpm run format:check
pnpm run lint
pnpm run typecheck

# Build package
echo -e "${GREEN}Building package...${NC}"
pnpm run build

# Run tests
echo -e "${GREEN}Running tests...${NC}"
pnpm run test:run

# Publish to npm
echo -e "${GREEN}Publishing to npm...${NC}"
echo -e "${YELLOW}Note: Make sure you have npm credentials configured${NC}"
echo -e "${YELLOW}Run 'npm login' if you haven't already${NC}"
pnpm publish --access public --no-git-checks

# Create git tag
echo -e "${GREEN}Creating git tag...${NC}"
git add package.json src/index.ts
git commit -m "chore(sdk-js): release v$NEW_VERSION"
git tag "sdk-js-v$NEW_VERSION"

echo -e "${GREEN}Release complete!${NC}"
echo -e "${YELLOW}Don't forget to push the changes:${NC}"
echo "  git push origin main --tags"
