#!/usr/bin/env python3
"""
CLI Music Downloader - Command-line interface module

This module provides entry points for all CLI tools in the package:
- download-music: Main music downloader
- batch-metadata: Batch metadata processor  
- fixalbumart: Album art fixer (Python wrapper for shell script)
- cli-music-downloader: Main entry point with subcommands
"""

import sys
import os
import subprocess
import argparse
import asyncio
from pathlib import Path
from typing import List, Optional

from . import __version__
from .download_music import main as download_music_main
from .batch_metadata import main as batch_metadata_main

def download_music():
    """Entry point for download-music command"""
    try:
        download_music_main()
    except SystemExit:
        pass
    except KeyboardInterrupt:
        print("\n⚠️ Download interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"💥 Unexpected error: {e}")
        sys.exit(1)

def batch_metadata():
    """Entry point for batch-metadata command"""
    try:
        asyncio.run(batch_metadata_main())
    except SystemExit:
        pass
    except KeyboardInterrupt:
        print("\n⚠️ Operation cancelled by user")
        sys.exit(130)
    except Exception as e:
        print(f"💥 Unexpected error: {e}")
        sys.exit(1)

def fixalbumart_improved():
    """Entry point for fixalbumart command (wrapper for shell script)"""
    parser = argparse.ArgumentParser(
        description='Fix album artwork for MP3 files',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  fixalbumart "/path/to/song.mp3" "Artist Name" "Track Name"
  fixalbumart "/path/to/Artist - Track.mp3"
        '''
    )
    
    parser.add_argument('file_path', help='Path to MP3 file')
    parser.add_argument('artist', nargs='?', help='Artist name (optional)')
    parser.add_argument('track', nargs='?', help='Track name (optional)')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.file_path):
        print(f"❌ Error: File not found: {args.file_path}")
        sys.exit(1)
    
    # Find the original fixalbumart_improved script
    script_paths = [
        # Look in bin directory relative to package
        Path(__file__).parent.parent / 'bin' / 'fixalbumart_improved',
        # Look in PATH
        'fixalbumart_improved'
    ]
    
    script_path = None
    for path in script_paths:
        if isinstance(path, Path) and path.exists():
            script_path = str(path)
            break
        elif isinstance(path, str):
            # Check if it's in PATH
            try:
                result = subprocess.run(['which', path], capture_output=True, text=True)
                if result.returncode == 0:
                    script_path = path
                    break
            except:
                continue
    
    if not script_path:
        print("❌ Error: fixalbumart_improved script not found")
        print("Please ensure the original bin/fixalbumart_improved script is available")
        sys.exit(1)
    
    # Build command
    cmd = [script_path, args.file_path]
    
    if args.artist and args.track:
        cmd.extend([args.artist, args.track])
    
    try:
        if args.verbose:
            print(f"🔧 Running: {' '.join(cmd)}")
        
        result = subprocess.run(cmd, check=False)
        sys.exit(result.returncode)
        
    except FileNotFoundError:
        print(f"❌ Error: Script not found: {script_path}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n⚠️ Operation interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"💥 Unexpected error: {e}")
        sys.exit(1)

def main():
    """Main CLI entry point with subcommands"""
    parser = argparse.ArgumentParser(
        prog='cli-music-downloader',
        description='CLI Music Downloader - A powerful command-line music downloader',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Subcommands:
  download    Download music with metadata and album art
  batch       Process metadata for multiple files
  fix-art     Fix album artwork for existing files
  
Examples:
  cli-music-downloader download "The Beatles Hey Jude"
  cli-music-downloader batch --scan ~/Music
  cli-music-downloader fix-art "/path/to/song.mp3"
  
For more help on a subcommand:
  cli-music-downloader SUBCOMMAND --help
        '''
    )
    
    parser.add_argument('--version', action='version', version=f'cli-music-downloader {__version__}')
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Download subcommand
    download_parser = subparsers.add_parser(
        'download', 
        help='Download music with metadata and album art',
        description='Download music from YouTube with automatic organization and metadata'
    )
    download_parser.add_argument('search_term', help='Search term for the music (e.g., "Artist - Song")')
    download_parser.add_argument('--artist', help='Artist name hint (overrides parsing)')
    download_parser.add_argument('--title', help='Song title hint (overrides parsing)')
    download_parser.add_argument('--skip-metadata', action='store_true', help='Skip metadata enhancement')
    download_parser.add_argument('--force-metadata', action='store_true', help='Force metadata refresh')
    download_parser.add_argument('--metadata-source', choices=['musicbrainz', 'shazam', 'all'], default='all')
    download_parser.add_argument('--genius-key', help='Genius API key for lyrics')
    download_parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    download_parser.add_argument('-q', '--quiet', action='store_true', help='Quiet mode')
    
    # Batch subcommand
    batch_parser = subparsers.add_parser(
        'batch',
        help='Process metadata for multiple files',
        description='Scan and fix metadata for music libraries'
    )
    batch_parser.add_argument('--scan', metavar='DIRECTORY', help='Scan directory for incomplete metadata')
    batch_parser.add_argument('--fix', metavar='DIRECTORY', help='Fix metadata for files in directory')
    batch_parser.add_argument('--report', action='store_true', help='Display the most recent scan report')
    batch_parser.add_argument('--detailed', action='store_true', help='Show detailed report')
    batch_parser.add_argument('--dry-run', action='store_true', help='Show what would be fixed')
    batch_parser.add_argument('--config', action='store_true', help='Show current configuration')
    batch_parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    
    # Fix-art subcommand
    fixart_parser = subparsers.add_parser(
        'fix-art',
        help='Fix album artwork for existing files',
        description='Add or fix album artwork for MP3 files'
    )
    fixart_parser.add_argument('file_path', help='Path to MP3 file')
    fixart_parser.add_argument('artist', nargs='?', help='Artist name (optional)')
    fixart_parser.add_argument('track', nargs='?', help='Track name (optional)')
    fixart_parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Handle subcommands
    if args.command == 'download':
        # Set up arguments for download_music module
        download_args = [
            'download_music.py',  # Script name
            args.search_term
        ]
        
        if args.artist:
            download_args.extend(['--artist', args.artist])
        if args.title:
            download_args.extend(['--title', args.title])
        if args.skip_metadata:
            download_args.append('--skip-metadata')
        if args.force_metadata:
            download_args.append('--force-metadata')
        if args.metadata_source:
            download_args.extend(['--metadata-source', args.metadata_source])
        if args.genius_key:
            download_args.extend(['--genius-key', args.genius_key])
        if args.verbose:
            download_args.append('--verbose')
        if args.quiet:
            download_args.append('--quiet')
        
        # Replace sys.argv and call download function
        original_argv = sys.argv[:]
        try:
            sys.argv = download_args
            download_music()
        finally:
            sys.argv = original_argv
    
    elif args.command == 'batch':
        # Set up arguments for batch_metadata module
        batch_args = ['batch_metadata.py']
        
        if args.scan:
            batch_args.extend(['--scan', args.scan])
        if args.fix:
            batch_args.extend(['--fix', args.fix])
        if args.report:
            batch_args.append('--report')
        if args.detailed:
            batch_args.append('--detailed')
        if args.dry_run:
            batch_args.append('--dry-run')
        if args.config:
            batch_args.append('--config')
        if args.verbose:
            batch_args.append('--verbose')
        
        # Replace sys.argv and call batch function
        original_argv = sys.argv[:]
        try:
            sys.argv = batch_args
            batch_metadata()
        finally:
            sys.argv = original_argv
    
    elif args.command == 'fix-art':
        # Set up arguments for fixalbumart function
        fixart_args = ['fixalbumart_improved', args.file_path]
        
        if args.artist:
            fixart_args.append(args.artist)
        if args.track:
            fixart_args.append(args.track)
        if args.verbose:
            fixart_args.append('--verbose')
        
        # Replace sys.argv and call fixalbumart function
        original_argv = sys.argv[:]
        try:
            sys.argv = fixart_args
            fixalbumart_improved()
        finally:
            sys.argv = original_argv

if __name__ == '__main__':
    main()
