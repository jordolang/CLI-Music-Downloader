#!/bin/bash

# CLI Music Downloader Uninstallation Script
# Removes all installed components

set -euo pipefail

# --- Helper Functions ---

echoerr() {
    echo "$@" 1>&2
}

get_uninstall_help() {
    cat <<-'EOF'
🗑️ Uninstallation Tool Help
==========================

This tool uninstalls the CLI Music Downloader and removes its components from your system.

Features:
  • Removes the main scripts from your local bin directory
  • Removes the Warp workflow (if installed)
  • Provides instructions for manually removing Python dependencies and downloaded music

Usage:
  Run this tool to remove the music downloader. It will prompt for confirmation before proceeding.

Note:
  • This script does NOT delete your downloaded music files in ~/Music.
  • It does NOT automatically uninstall Python packages. You will need to do this manually if desired.
EOF
}

uninstall_ui() {
    local output=""
    
    output+=$(echo "🗑️  CLI Music Downloader Uninstallation")
    output+=$(echo "=======================================")
    output+=$(echo "")

    # Colors for output
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    BLUE='\033[0;34m'
    NC='\033[0m' # No Color

    # Helper functions
    info() { output+=$(echo -e "${BLUE}ℹ️  $1${NC}"); }
    success() { output+=$(echo -e "${GREEN}✅ $1${NC}"); }
    warning() { output+=$(echo -e "${YELLOW}⚠️  $1${NC}"); }
    error() { output+=$(echo -e "${RED}❌ $1${NC}"); }

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

    output+=$(echo "")
    success "Uninstallation completed! 👋"
    output+=$(echo "Thank you for using CLI Music Downloader!")
    
    echo "$output"
    return 0
}

# If script is executed directly, run the uninstall UI
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    # Confirmation
    read -p "Are you sure you want to uninstall CLI Music Downloader? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Uninstallation cancelled"
        exit 0
    fi
    uninstall_ui
fi

