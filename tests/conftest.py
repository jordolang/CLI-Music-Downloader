#!/usr/bin/env python3
"""
Pytest configuration and fixtures for metadata functionality tests
"""

import pytest
import tempfile
import shutil
import os
import sys
from pathlib import Path
from unittest.mock import Mock

# Add scripts directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests"""
    temp_path = tempfile.mkdtemp()
    yield temp_path
    shutil.rmtree(temp_path, ignore_errors=True)

@pytest.fixture
def test_mp3_file(temp_dir):
    """Create a test MP3 file"""
    file_path = os.path.join(temp_dir, "test_song.mp3")
    with open(file_path, 'wb') as f:
        # Write minimal MP3 header
        f.write(b'\xff\xfb\x90\x00')
        f.write(b'\x00' * 1000)  # Dummy audio data
    return file_path

@pytest.fixture
def test_mp3_files(temp_dir):
    """Create multiple test MP3 files"""
    files = []
    for i in range(3):
        file_path = os.path.join(temp_dir, f"test_song_{i}.mp3")
        with open(file_path, 'wb') as f:
            f.write(b'\xff\xfb\x90\x00')
            f.write(b'\x00' * 1000)
        files.append(file_path)
    return files

@pytest.fixture
def mock_options():
    """Create mock options for downloader"""
    options = Mock()
    options.skip_metadata = False
    options.metadata_source = 'musicbrainz'
    options.force_metadata = False
    options.genius_key = None
    return options

@pytest.fixture(autouse=True)
def set_test_environment():
    """Set testing environment variables"""
    os.environ['TESTING'] = '1'
    yield
    if 'TESTING' in os.environ:
        del os.environ['TESTING']

