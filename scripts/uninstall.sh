#!/bin/bash

# CLI Music Downloader Uninstallation Script
# Removes all installed components

set -euo pipefail

echo "🗑️  CLI Music Downloader Uninstallation"
echo "======================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
info() { echo -e "${BLUE}ℹ️  $1${NC}"; }
success() { echo -e "${GREEN}✅ $1${NC}"; }
warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
error() { echo -e "${RED}❌ $1${NC}"; }

# Confirmation
read -p "Are you sure you want to uninstall CLI Music Downloader? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    info "Uninstallation cancelled"
    exit 0
fi

info "Removing scripts from ~/.local/bin/..."
rm -f ~/.local/bin/download_music
rm -f ~/.local/bin/fixalbumart_improved
success "Scripts removed"

info "Removing Warp workflow..."
rm -f ~/.config/warp/workflows/download_music.yaml
success "Warp workflow removed"

warning "Note: Python dependencies (instantmusic, eyed3, requests) were NOT removed"
info "You can remove them manually with: pip uninstall instantmusic eyed3 requests"

warning "Note: Downloaded music files in ~/Music were NOT removed"
info "You can remove them manually if desired"

echo ""
success "Uninstallation completed! 👋"
echo "Thank you for using CLI Music Downloader!"

