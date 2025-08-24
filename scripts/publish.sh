#!/bin/bash
# 
# PyPI Publishing Script for CLI Music Downloader
# 
# This script builds and publishes the package to PyPI.
# Run this from the project root directory.
#
# Usage:
#   ./scripts/publish.sh          # Publish to PyPI
#   ./scripts/publish.sh test     # Publish to Test PyPI
#

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check if we're in the right directory
if [[ ! -f "pyproject.toml" ]]; then
    echo -e "${RED}Error: pyproject.toml not found. Run this script from the project root.${NC}"
    exit 1
fi

# Check for required tools
echo -e "${BLUE}🔍 Checking required tools...${NC}"
command -v python3 >/dev/null 2>&1 || { echo -e "${RED}Error: python3 is required but not installed.${NC}"; exit 1; }
command -v pip >/dev/null 2>&1 || { echo -e "${RED}Error: pip is required but not installed.${NC}"; exit 1; }

# Determine target (PyPI or Test PyPI)
TARGET="pypi"
if [[ "${1:-}" == "test" ]]; then
    TARGET="testpypi"
    echo -e "${YELLOW}📦 Publishing to Test PyPI${NC}"
else
    echo -e "${YELLOW}📦 Publishing to PyPI${NC}"
fi

# Install/upgrade build tools
echo -e "${BLUE}🔨 Installing build tools...${NC}"
pip install --upgrade build twine

# Clean previous builds
echo -e "${BLUE}🧹 Cleaning previous builds...${NC}"
rm -rf build/
rm -rf dist/
rm -rf *.egg-info/

# Build the package
echo -e "${BLUE}🏗️  Building package...${NC}"
python -m build

# List built files
echo -e "${BLUE}📋 Built files:${NC}"
ls -la dist/

# Check the package
echo -e "${BLUE}🔍 Checking package...${NC}"
python -m twine check dist/*

# Upload to PyPI
echo -e "${BLUE}🚀 Uploading to ${TARGET}...${NC}"

if [[ "$TARGET" == "testpypi" ]]; then
    # Upload to Test PyPI
    python -m twine upload --repository testpypi dist/*
    echo -e "${GREEN}✅ Successfully uploaded to Test PyPI!${NC}"
    echo -e "${YELLOW}📋 You can view your package at: https://test.pypi.org/project/CLI-Music-Downloader/${NC}"
    echo -e "${YELLOW}📋 Install with: pip install --index-url https://test.pypi.org/simple/ CLI-Music-Downloader${NC}"
else
    # Upload to PyPI
    echo -e "${YELLOW}⚠️  You are about to publish to PyPI. This action cannot be undone.${NC}"
    echo -e "${YELLOW}❓ Are you sure you want to continue? (y/N)${NC}"
    read -r response
    if [[ "$response" =~ ^[Yy]$ ]]; then
        python -m twine upload dist/*
        echo -e "${GREEN}✅ Successfully uploaded to PyPI!${NC}"
        echo -e "${YELLOW}📋 You can view your package at: https://pypi.org/project/CLI-Music-Downloader/${NC}"
        echo -e "${YELLOW}📋 Install with: pip install CLI-Music-Downloader${NC}"
    else
        echo -e "${YELLOW}❌ Upload cancelled.${NC}"
        exit 1
    fi
fi

echo -e "${GREEN}🎉 Publishing complete!${NC}"
