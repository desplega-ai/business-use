#!/usr/bin/env bash
#
# Release script for business-use monorepo
#
# Usage:
#   ./scripts/release.sh <package> <bump_type>
#
# Arguments:
#   package    - Which package to release: core, sdk-py, sdk-js, or all
#   bump_type  - Version bump: patch, minor, or major
#
# Examples:
#   ./scripts/release.sh core patch
#   ./scripts/release.sh sdk-py minor
#   ./scripts/release.sh all patch
#

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
info() {
    echo -e "${BLUE}ℹ ${NC}$1"
}

success() {
    echo -e "${GREEN}✓${NC} $1"
}

warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

error() {
    echo -e "${RED}✗${NC} $1"
}

# Function to get current version from a file
get_version() {
    local file=$1
    local pattern=$2

    if [[ $file == *.toml ]]; then
        grep '^version = ' "$file" | sed 's/version = "\(.*\)"/\1/'
    elif [[ $file == *.json ]]; then
        grep '"version":' "$file" | sed 's/.*"version": "\(.*\)".*/\1/' | head -1
    fi
}

# Function to bump version
bump_version() {
    local current=$1
    local bump_type=$2

    IFS='.' read -r major minor patch <<< "$current"

    case "$bump_type" in
        major)
            echo "$((major + 1)).0.0"
            ;;
        minor)
            echo "${major}.$((minor + 1)).0"
            ;;
        patch)
            echo "${major}.${minor}.$((patch + 1))"
            ;;
        *)
            error "Invalid bump type: $bump_type"
            exit 1
            ;;
    esac
}

# Function to update version in pyproject.toml
update_pyproject_version() {
    local file=$1
    local new_version=$2

    # macOS compatible sed (works on both Linux and macOS)
    if [[ "$OSTYPE" == "darwin"* ]]; then
        sed -i '' "0,/^version = /s/^version = \".*\"/version = \"$new_version\"/" "$file"
    else
        sed -i "0,/^version = /s/^version = \".*\"/version = \"$new_version\"/" "$file"
    fi
}

# Function to update version in package.json
update_package_version() {
    local file=$1
    local new_version=$2

    # macOS compatible sed
    if [[ "$OSTYPE" == "darwin"* ]]; then
        sed -i '' "0,/\"version\":/s/\"version\": \".*\"/\"version\": \"$new_version\"/" "$file"
    else
        sed -i "0,/\"version\":/s/\"version\": \".*\"/\"version\": \"$new_version\"/" "$file"
    fi
}

# Function to release a package
release_package() {
    local package=$1
    local bump_type=$2
    local version_file=""
    local tag_prefix=""

    case "$package" in
        core)
            version_file="core/pyproject.toml"
            tag_prefix="core-v"
            ;;
        sdk-py)
            version_file="sdk-py/pyproject.toml"
            tag_prefix="sdk-py-v"
            ;;
        sdk-js)
            version_file="sdk-js/package.json"
            tag_prefix="sdk-js-v"
            ;;
        *)
            error "Invalid package: $package"
            exit 1
            ;;
    esac

    info "Releasing $package..."

    # Get current version
    local current_version=$(get_version "$version_file")
    info "Current version: $current_version"

    # Calculate new version
    local new_version=$(bump_version "$current_version" "$bump_type")
    info "New version: $new_version"

    # Update version in file
    if [[ $version_file == *.toml ]]; then
        update_pyproject_version "$version_file" "$new_version"
    elif [[ $version_file == *.json ]]; then
        update_package_version "$version_file" "$new_version"
    fi

    success "Updated version in $version_file"

    # Create git commit
    git add "$version_file"
    git commit -m "chore($package): release v$new_version"
    success "Created commit for $package v$new_version"

    # Create git tag
    local tag="${tag_prefix}${new_version}"
    git tag "$tag"
    success "Created tag: $tag"

    echo ""
}

# Main script
main() {
    # Check arguments
    if [ $# -ne 2 ]; then
        error "Usage: $0 <package> <bump_type>"
        echo ""
        echo "Arguments:"
        echo "  package    - Which package to release: core, sdk-py, sdk-js, or all"
        echo "  bump_type  - Version bump: patch, minor, or major"
        echo ""
        echo "Examples:"
        echo "  $0 core patch"
        echo "  $0 sdk-py minor"
        echo "  $0 all patch"
        exit 1
    fi

    local package=$1
    local bump_type=$2

    # Validate bump type
    if [[ ! "$bump_type" =~ ^(patch|minor|major)$ ]]; then
        error "Invalid bump type: $bump_type (must be patch, minor, or major)"
        exit 1
    fi

    # Check if we're in git repository
    if ! git rev-parse --git-dir > /dev/null 2>&1; then
        error "Not in a git repository"
        exit 1
    fi

    # Check if working directory is clean
    if [[ -n $(git status -s) ]]; then
        error "Working directory is not clean. Commit or stash your changes first."
        git status -s
        exit 1
    fi

    # Get current branch
    local current_branch=$(git rev-parse --abbrev-ref HEAD)
    info "Current branch: $current_branch"

    # Confirm release
    echo ""
    warning "This will:"
    echo "  1. Bump version ($bump_type)"
    echo "  2. Create commit(s)"
    echo "  3. Create git tag(s)"
    echo "  4. Push to remote"
    echo ""
    read -p "Continue? (y/n) " -n 1 -r
    echo ""

    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        warning "Release cancelled"
        exit 0
    fi

    echo ""
    info "Starting release process..."
    echo ""

    # Release package(s)
    if [ "$package" = "all" ]; then
        release_package "core" "$bump_type"
        release_package "sdk-py" "$bump_type"
        release_package "sdk-js" "$bump_type"
    else
        release_package "$package" "$bump_type"
    fi

    # Push to remote
    info "Pushing to remote..."
    git push origin "$current_branch" --tags
    success "Pushed commits and tags to remote"

    echo ""
    success "Release complete!"
    echo ""
    info "GitHub Actions will now:"
    echo "  • Run CI checks"
    echo "  • Build packages"
    echo "  • Publish to registries (PyPI/npm)"
    echo ""
    info "Monitor the workflows at:"
    echo "  https://github.com/desplega-ai/business-use/actions"
}

main "$@"
