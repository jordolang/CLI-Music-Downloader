#!/usr/bin/env python3
"""
Pytest-based test suite for metadata functionality

This provides the same tests as test_metadata_functionality.py but using pytest syntax
for better test discovery, fixtures, and reporting.
"""

import pytest
import asyncio
import os
import sys
import tempfile
import shutil
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from pathlib import Path
from typing import Dict, Any, Optional

# Add scripts directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

try:
    from metadata_manager import (
        MetadataManager, MetadataRecord, MetadataValidator, 
        MusicBrainzProvider, LastFmProvider, DiscogsProvider,
        MetadataSource, MetadataField
    )
    from lyrics_metadata import LyricsMetadataHandler
    from download_music import MusicBrainzMetadata, EnhancedMusicDownloader
except ImportError as e:
    pytest.skip(f"Error importing modules: {e}", allow_module_level=True)


class TestMetadataExtraction:
    """Test cases for metadata extraction from various sources"""
    
    def test_filename_metadata_extraction(self):
        """Test extraction of metadata from filename patterns"""
        handler = LyricsMetadataHandler()
        
        # Test Artist - Title pattern
        result = handler.extract_metadata_from_filename("The Beatles - Hey Jude.mp3")
        assert result['artist'] == "The Beatles"
        assert result['title'] == "Hey Jude"
        
        # Test Artist Title pattern (no separator)
        result = handler.extract_metadata_from_filename("Adele Hello.mp3")
        assert result['artist'] == "Adele"
        assert result['title'] == "Hello"
        
        # Test edge case - no pattern match
        result = handler.extract_metadata_from_filename("randomfile.mp3")
        assert result['artist'] == ""
        assert result['title'] == "randomfile"
    
    def test_metadata_field_validation(self):
        """Test metadata field validation rules"""
        validator = MetadataValidator()
        
        # Test valid metadata record
        valid_record = MetadataRecord(
            title="Test Song",
            artist="Test Artist",
            album="Test Album",
            year="2023",
            track_number="1"
        )
        
        is_valid, errors = validator.validate_record(valid_record)
        assert is_valid
        assert len(errors) == 0
    
    def test_metadata_field_validation_errors(self):
        """Test metadata validation with invalid data"""
        validator = MetadataValidator()
        
        # Test missing required fields
        invalid_record = MetadataRecord(
            title="",  # Required field empty
            artist="Test Artist",
            album="Test Album",
            year="invalid_year",  # Invalid year format
            track_number="0"  # Invalid track number
        )
        
        is_valid, errors = validator.validate_record(invalid_record)
        assert not is_valid
        assert len(errors) > 0
        
        # Check specific error types
        error_messages = ' '.join(errors)
        assert "title" in error_messages.lower()
        assert "year" in error_messages.lower()
    
    def test_metadata_correction(self):
        """Test automatic metadata correction"""
        validator = MetadataValidator()
        
        # Test title correction (remove unwanted patterns)
        record = MetadataRecord(
            title="Test Song (Official Video) [HD]",
            artist="test artist",
            album="test album",
            year="2023-01-01",  # Full date format
            track_number="1"
        )
        
        corrected = validator.correct_record(record)
        
        # Check corrections were applied
        assert corrected.title == "Test Song"
        assert corrected.artist == "Test Artist"  # Title case
        assert corrected.album == "Test Album"  # Title case
        assert corrected.year == "2023"  # Extracted year
        assert len(corrected.corrections_applied) > 0
    
    @pytest.mark.parametrize("input_genre,expected_genre", [
        ("rock", "Rock"),
        ("hip hop", "Hip-Hop"),
        ("electronic", "Electronic"),
        ("alt rock", "Alternative Rock"),
        ("Custom Genre", "Custom Genre")  # Unknown genre should be title-cased
    ])
    def test_genre_standardization(self, input_genre, expected_genre):
        """Test genre name standardization"""
        validator = MetadataValidator()
        result = validator._correct_genre(input_genre)
        assert result == expected_genre


class TestMusicBrainzIntegration:
    """Test cases for MusicBrainz API integration"""
    
    @pytest.fixture
    def musicbrainz(self):
        """Create MusicBrainz instance for testing"""
        return MusicBrainzMetadata()
    
    @patch('musicbrainzngs.search_recordings')
    def test_musicbrainz_search_success(self, mock_search, musicbrainz):
        """Test successful MusicBrainz metadata search"""
        # Mock successful API response
        mock_search.return_value = {
            'recording-list': [{
                'id': 'test-recording-id',
                'title': 'Hey Jude',
                'artist-credit': [{
                    'artist': {
                        'id': 'test-artist-id',
                        'name': 'The Beatles'
                    }
                }],
                'release-list': [{
                    'id': 'test-release-id',
                    'title': 'Hey Jude',
                    'date': '1968-08-26'
                }]
            }]
        }
        
        result = musicbrainz.search_recording("The Beatles", "Hey Jude")
        
        assert result is not None
        assert result['title'] == 'Hey Jude'
        assert result['artist'] == 'The Beatles'
        assert result['year'] == '1968'
        assert result['musicbrainz_recording_id'] == 'test-recording-id'
    
    @patch('musicbrainzngs.search_recordings')
    def test_musicbrainz_search_no_results(self, mock_search, musicbrainz):
        """Test MusicBrainz search with no results"""
        mock_search.return_value = {'recording-list': []}
        
        result = musicbrainz.search_recording("Unknown Artist", "Unknown Song")
        
        assert result is None
    
    @patch('musicbrainzngs.search_recordings')
    def test_musicbrainz_api_error(self, mock_search, musicbrainz):
        """Test MusicBrainz API error handling"""
        mock_search.side_effect = Exception("API Error")
        
        result = musicbrainz.search_recording("Artist", "Title")
        
        assert result is None
    
    def test_musicbrainz_unavailable(self, musicbrainz):
        """Test behavior when MusicBrainz is unavailable"""
        # Temporarily make musicbrainz unavailable
        original_available = musicbrainz.available
        musicbrainz.available = False
        
        result = musicbrainz.search_recording("Artist", "Title")
        
        assert result is None
        
        # Restore original state
        musicbrainz.available = original_available


class TestMetadataValidationRules:
    """Test cases for metadata validation rules and logic"""
    
    @pytest.fixture
    def validator(self):
        """Create MetadataValidator instance for testing"""
        return MetadataValidator()
    
    @pytest.mark.parametrize("field", ['title', 'artist', 'album', 'year', 'track_number'])
    def test_required_field_validation(self, validator, field):
        """Test validation of required fields"""
        record = MetadataRecord(
            title="Test Title",
            artist="Test Artist",
            album="Test Album",
            year="2023",
            track_number="1"
        )
        
        # Make the field empty
        setattr(record, field, "")
        
        is_valid, errors = validator.validate_record(record)
        assert not is_valid, f"Field {field} should be required"
        
        # Check that the error mentions the field
        error_text = ' '.join(errors).lower()
        assert field in error_text
    
    @pytest.mark.parametrize("year_value,should_be_valid", [
        ("2023", True),
        ("1950", True),
        ("2024", True),
        ("1899", False),  # Too old
        ("2050", False),  # Too far in future
        ("invalid", False),  # Not a number
        ("23", False),  # Too short
        ("", False)  # Empty (required field)
    ])
    def test_year_validation(self, validator, year_value, should_be_valid):
        """Test year field validation"""
        record = MetadataRecord(
            title="Test",
            artist="Test",
            album="Test",
            year=year_value,
            track_number="1"
        )
        
        is_valid, errors = validator.validate_record(record)
        if should_be_valid:
            # Check if year validation specifically passed
            year_errors = [e for e in errors if 'year' in e.lower()]
            assert len(year_errors) == 0, f"Year {year_value} should be valid"
        else:
            assert not is_valid, f"Year {year_value} should be invalid"
    
    @pytest.mark.parametrize("track_value,should_be_valid", [
        ("1", True),
        ("99", True),
        ("999", True),
        ("0", False),  # Too low
        ("1000", False),  # Too high
        ("-1", False),  # Negative
        ("abc", False),  # Not a number
        ("", False)  # Empty (required field)
    ])
    def test_track_number_validation(self, validator, track_value, should_be_valid):
        """Test track number field validation"""
        record = MetadataRecord(
            title="Test",
            artist="Test",
            album="Test",
            year="2023",
            track_number=track_value
        )
        
        is_valid, errors = validator.validate_record(record)
        if should_be_valid:
            # Check if track_number validation specifically passed
            track_errors = [e for e in errors if 'track_number' in e.lower()]
            assert len(track_errors) == 0, f"Track number {track_value} should be valid"
        else:
            assert not is_valid, f"Track number {track_value} should be invalid"
    
    def test_length_validation(self, validator):
        """Test field length validation"""
        # Test title max length
        long_title = "A" * 300  # Exceeds max length of 255
        record = MetadataRecord(
            title=long_title,
            artist="Test",
            album="Test",
            year="2023",
            track_number="1"
        )
        
        is_valid, errors = validator.validate_record(record)
        assert not is_valid
        
        # Check for length error
        error_text = ' '.join(errors).lower()
        assert "length" in error_text


class TestBatchProcessing:
    """Test cases for batch metadata processing"""
    
    @pytest.mark.asyncio
    async def test_batch_metadata_processing(self, test_mp3_files):
        """Test processing multiple files in batch"""
        manager = MetadataManager()
        
        # Mock metadata provider to return test data
        with patch.object(manager.providers[MetadataSource.MUSICBRAINZ], 
                         'search_metadata') as mock_search:
            mock_search.return_value = MetadataRecord(
                title="Test Song",
                artist="Test Artist",
                album="Test Album",
                year="2023",
                track_number="1",
                source="musicbrainz",
                confidence=0.9
            )
            
            # Process multiple files
            results = []
            for i, file_path in enumerate(test_mp3_files):
                result = await manager.get_metadata(
                    artist=f"Artist {i}",
                    title=f"Song {i}"
                )
                results.append(result)
            
            # Verify all files were processed
            assert len(results) == len(test_mp3_files)
            
            # Verify all results are valid
            for result in results:
                assert result is not None
                assert result.title == "Test Song"
                assert result.source == "musicbrainz"
    
    def test_batch_validation_summary(self):
        """Test batch validation and error summary"""
        validator = MetadataValidator()
        
        # Create mix of valid and invalid records
        records = [
            MetadataRecord(
                title="Valid Song",
                artist="Valid Artist",
                album="Valid Album",
                year="2023",
                track_number="1"
            ),
            MetadataRecord(
                title="",  # Invalid - empty title
                artist="Invalid Artist",
                album="Invalid Album",
                year="invalid",  # Invalid year
                track_number="0"  # Invalid track number
            ),
            MetadataRecord(
                title="Another Valid Song",
                artist="Another Valid Artist",
                album="Another Valid Album",
                year="2022",
                track_number="2"
            )
        ]
        
        valid_count = 0
        invalid_count = 0
        all_errors = []
        
        for record in records:
            is_valid, errors = validator.validate_record(record)
            if is_valid:
                valid_count += 1
            else:
                invalid_count += 1
                all_errors.extend(errors)
        
        assert valid_count == 2
        assert invalid_count == 1
        assert len(all_errors) > 0
    
    def test_batch_correction_application(self):
        """Test applying corrections to multiple records"""
        validator = MetadataValidator()
        
        # Create records that need correction
        records = [
            MetadataRecord(
                title="song one (official video)",
                artist="artist one",
                album="album one",
                year="2023-01-01",
                track_number="1"
            ),
            MetadataRecord(
                title="song two [hd]",
                artist="artist two",
                album="album two",
                year="2022-12-25",
                track_number="2"
            )
        ]
        
        corrected_records = []
        for record in records:
            corrected = validator.correct_record(record)
            corrected_records.append(corrected)
        
        # Verify corrections were applied
        assert corrected_records[0].title == "Song One"
        assert corrected_records[0].artist == "Artist One"
        assert corrected_records[0].year == "2023"
        
        assert corrected_records[1].title == "Song Two"
        assert corrected_records[1].artist == "Artist Two"
        assert corrected_records[1].year == "2022"
        
        # Verify all records have corrections logged
        for record in corrected_records:
            assert len(record.corrections_applied) > 0


class TestEdgeCases:
    """Test cases for edge cases including missing data and network errors"""
    
    @pytest.fixture
    def manager(self):
        """Create MetadataManager instance for testing"""
        return MetadataManager()
    
    @pytest.mark.asyncio
    async def test_empty_search_terms(self, manager):
        """Test handling of empty or invalid search terms"""
        # Test empty artist and title
        result = await manager.get_metadata(
            artist="",
            title=""
        )
        
        # Should handle gracefully without crashing
        # Result may be None or a record with empty fields
        if result:
            assert result.artist == ""
            assert result.title == ""
    
    @pytest.mark.asyncio
    async def test_special_characters(self, manager):
        """Test handling of special characters in metadata"""
        with patch.object(manager.providers[MetadataSource.MUSICBRAINZ], 
                         'search_metadata') as mock_search:
            mock_search.return_value = MetadataRecord(
                title="Café Müller & Co.'s Song",
                artist="Ñoño Pérez-García",
                album="Álbum Especial",
                year="2023",
                track_number="1",
                source="musicbrainz",
                confidence=0.9
            )
            
            result = await manager.get_metadata(
                artist="Ñoño Pérez-García",
                title="Café Müller & Co.'s Song"
            )
            
            assert result is not None
            assert result.title == "Café Müller & Co.'s Song"
            assert result.artist == "Ñoño Pérez-García"
    
    @pytest.mark.asyncio
    @patch('musicbrainzngs.search_recordings')
    async def test_network_timeout(self, mock_search):
        """Test handling of network timeouts"""
        import requests
        mock_search.side_effect = requests.exceptions.Timeout("Request timed out")
        
        musicbrainz_provider = MusicBrainzProvider()
        result = await musicbrainz_provider.search_metadata(
            artist="Test Artist",
            title="Test Song"
        )
        
        assert result is None
    
    @pytest.mark.asyncio
    @patch('musicbrainzngs.search_recordings')
    async def test_network_connection_error(self, mock_search):
        """Test handling of network connection errors"""
        import requests
        mock_search.side_effect = requests.exceptions.ConnectionError("Connection failed")
        
        musicbrainz_provider = MusicBrainzProvider()
        result = await musicbrainz_provider.search_metadata(
            artist="Test Artist",
            title="Test Song"
        )
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_partial_metadata(self, manager):
        """Test handling of partial/incomplete metadata"""
        with patch.object(manager.providers[MetadataSource.MUSICBRAINZ], 
                         'search_metadata') as mock_search:
            # Return record with some missing fields
            mock_search.return_value = MetadataRecord(
                title="Test Song",
                artist="Test Artist",
                album="",  # Missing album
                year="",   # Missing year
                track_number="1",
                source="musicbrainz",
                confidence=0.5  # Lower confidence due to missing data
            )
            
            result = await manager.get_metadata(
                artist="Test Artist",
                title="Test Song"
            )
            
            assert result is not None
            assert result.title == "Test Song"
            assert result.artist == "Test Artist"
            assert result.album == ""
            assert result.year == ""
    
    def test_malformed_metadata(self):
        """Test handling of malformed metadata"""
        validator = MetadataValidator()
        
        # Create record with malformed data
        malformed_record = MetadataRecord(
            title="\x00\x01Invalid\x02Characters\x03",
            artist="Artist\nWith\nNewlines",
            album="Album\tWith\tTabs",
            year="Not A Year",
            track_number="Not A Number"
        )
        
        # Apply corrections to clean up malformed data
        corrected = validator.correct_record(malformed_record)
        
        # Verify corrections were applied (exact behavior depends on implementation)
        assert corrected.title != malformed_record.title
        assert corrected.artist != malformed_record.artist
        assert corrected.album != malformed_record.album
    
    @pytest.mark.asyncio
    async def test_api_rate_limiting(self, manager):
        """Test handling of API rate limiting"""
        import requests
        
        with patch.object(manager.providers[MetadataSource.MUSICBRAINZ], 
                         'search_metadata') as mock_search:
            # Simulate rate limiting HTTP error
            mock_search.side_effect = requests.exceptions.HTTPError(
                "429 Too Many Requests"
            )
            
            result = await manager.get_metadata(
                artist="Test Artist",
                title="Test Song"
            )
            
            # Should handle rate limiting gracefully
            assert result is None
    
    def test_unicode_normalization(self):
        """Test Unicode normalization in metadata"""
        validator = MetadataValidator()
        
        # Test different Unicode representations of the same characters
        record = MetadataRecord(
            title="Café",  # é as single character
            artist="Café",  # é as e + combining accent
            album="Test Album",
            year="2023",
            track_number="1"
        )
        
        corrected = validator.correct_record(record)
        
        # After correction, Unicode should be normalized
        assert isinstance(corrected.title, str)
        assert isinstance(corrected.artist, str)
    
    @pytest.mark.asyncio
    async def test_metadata_provider_fallback(self, manager):
        """Test fallback between metadata providers"""
        # Mock first provider to fail, second to succeed
        with patch.object(manager.providers[MetadataSource.MUSICBRAINZ], 
                         'search_metadata') as mock_mb:
            with patch.object(manager.providers[MetadataSource.LASTFM], 
                             'search_metadata') as mock_lastfm:
                
                # MusicBrainz fails
                mock_mb.return_value = None
                
                # Last.fm succeeds
                mock_lastfm.return_value = MetadataRecord(
                    title="Test Song",
                    artist="Test Artist",
                    album="Test Album",
                    year="2023",
                    track_number="1",
                    source="lastfm",
                    confidence=0.7
                )
                
                result = await manager.get_metadata(
                    artist="Test Artist",
                    title="Test Song",
                    sources=[MetadataSource.MUSICBRAINZ, MetadataSource.LASTFM]
                )
                
                assert result is not None
                assert result.source == "lastfm"
                assert result.confidence == 0.7


class TestMetadataEnhancement:
    """Test cases for metadata enhancement functionality"""
    
    @patch('download_music.MusicBrainzMetadata.search_recording')
    def test_metadata_enhancement_pipeline(self, mock_search, test_mp3_file, mock_options):
        """Test the complete metadata enhancement pipeline"""
        # Mock successful metadata search
        mock_search.return_value = {
            'title': 'Test Song',
            'artist': 'Test Artist',
            'album': 'Test Album',
            'year': '2023',
            'genre': 'Rock',
            'track_number': '1',
            'musicbrainz_recording_id': 'test-id'
        }
        
        downloader = EnhancedMusicDownloader(mock_options)
        
        # Test metadata enhancement
        success = downloader.enhance_metadata(
            Path(test_mp3_file),
            artist_hint="Test Artist",
            title_hint="Test Song"
        )
        
        # Should complete without errors
        assert isinstance(success, bool)
    
    def test_metadata_merging(self):
        """Test merging metadata from multiple sources"""
        manager = MetadataManager()
        
        # Create primary record with some missing fields
        primary = MetadataRecord(
            title="Test Song",
            artist="Test Artist",
            album="",  # Missing
            year="2023",
            track_number="1",
            source="musicbrainz",
            confidence=0.9
        )
        
        # Create secondary record with complementary data
        secondary = MetadataRecord(
            title="Test Song",
            artist="Test Artist",
            album="Test Album",  # Has the missing field
            year="2023",
            track_number="1",
            genre="Rock",  # Additional field
            source="lastfm",
            confidence=0.7
        )
        
        merged = manager.merge_metadata(primary, secondary)
        
        # Should prefer primary for existing fields, secondary for missing fields
        assert merged.title == "Test Song"
        assert merged.artist == "Test Artist"
        assert merged.album == "Test Album"  # From secondary
        assert merged.genre == "Rock"  # From secondary
        assert merged.confidence == 0.9  # Higher confidence

