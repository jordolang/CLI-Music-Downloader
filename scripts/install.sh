#!/bin/bash

# CLI Music Downloader Installation Script
# Installs all components and dependencies

set -euo pipefail

echo "🎵 CLI Music Downloader Installation"
echo "===================================="
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

# Check if we're in the right directory
if [[ ! -f "bin/download_music" ]] || [[ ! -f "bin/fixalbumart_improved" ]]; then
    error "Please run this script from the CLI-Music-Downloader directory"
    exit 1
fi

info "Checking system requirements..."

# Check for Homebrew
if ! command -v brew &> /dev/null; then
    error "Homebrew is required but not installed. Please install Homebrew first."
    info "Visit https://brew.sh for installation instructions."
    exit 1
fi

# Check for Python
if ! command -v python3 &> /dev/null; then
    error "Python 3 is required but not installed. Please install Python 3.8+ first."
    exit 1
fi

# Check for pip
if ! command -v pip3 &> /dev/null && ! command -v pip &> /dev/null; then
    error "pip is required but not installed. Please install pip first."
    exit 1
fi

success "System requirements check passed"

info "Installing system dependencies via Homebrew..."
if brew list exiftool &> /dev/null && brew list id3v2 &> /dev/null; then
    success "System dependencies already installed"
else
    brew install exiftool id3v2
    success "System dependencies installed (exiftool, id3v2)"
fi

info "Installing Python dependencies..."
if command -v pip3 &> /dev/null; then
    pip3 install -r requirements.txt
else
    pip install -r requirements.txt
fi
success "Python dependencies installed"

info "Creating local bin directory..."
mkdir -p ~/.local/bin

info "Installing scripts..."
cp bin/download_music ~/.local/bin/
cp bin/fixalbumart_improved ~/.local/bin/
chmod +x ~/.local/bin/download_music
chmod +x ~/.local/bin/fixalbumart_improved
success "Scripts installed to ~/.local/bin/"

# Check if ~/.local/bin is in PATH
if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
    warning "~/.local/bin is not in your PATH"
    info "Adding ~/.local/bin to your PATH..."
    
    # Detect shell and add to appropriate config file
    if [[ "$SHELL" == *"zsh"* ]]; then
        echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
        info "Added to ~/.zshrc - please run 'source ~/.zshrc' or restart your terminal"
    elif [[ "$SHELL" == *"bash"* ]]; then
        echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
        info "Added to ~/.bashrc - please run 'source ~/.bashrc' or restart your terminal"
    else
        warning "Unknown shell: $SHELL"
        info "Please manually add ~/.local/bin to your PATH"
    fi
else
    success "~/.local/bin is already in your PATH"
fi

# Install Warp workflow if Warp is detected
if [[ -d ~/.config/warp ]] || command -v warp &> /dev/null; then
    info "Installing Warp Terminal workflow..."
    mkdir -p ~/.config/warp/workflows
    cp workflows/download_music.yaml ~/.config/warp/workflows/
    success "Warp workflow installed"
else
    info "Warp Terminal not detected - skipping workflow installation"
    info "You can manually install the workflow later if needed"
fi

# Create Music directory
info "Creating Music directory..."
mkdir -p ~/Music
success "Music directory ready"

echo ""
success "Installation completed successfully! 🎉"
echo ""
info "Quick test:"
echo "  download_music \"Coldplay Yellow\""
echo ""
info "For Warp users:"
echo "  Press Cmd+Shift+R and search for 'Download Music'"
echo ""
info "Enjoy your music! 🎵"

