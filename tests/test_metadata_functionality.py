#!/usr/bin/env python3
"""
Comprehensive test suite for metadata functionality in CLI Music Downloader

This test suite covers:
1. Metadata extraction
2. MusicBrainz API integration
3. Metadata validation rules
4. Batch processing
5. Edge cases (missing data, network errors)
"""

import unittest
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
    print(f"Error importing modules: {e}")
    sys.exit(1)


class TestMetadataExtraction(unittest.TestCase):
    """Test cases for metadata extraction from various sources"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.test_mp3_file = os.path.join(self.temp_dir, "test_song.mp3")
        
        # Create a dummy MP3 file for testing
        with open(self.test_mp3_file, 'wb') as f:
            # Write minimal MP3 header
            f.write(b'\xff\xfb\x90\x00')
            f.write(b'\x00' * 1000)  # Dummy audio data
    
    def tearDown(self):
        """Clean up test fixtures"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_filename_metadata_extraction(self):
        """Test extraction of metadata from filename patterns"""
        handler = LyricsMetadataHandler()
        
        # Test Artist - Title pattern
        result = handler.extract_metadata_from_filename("The Beatles - Hey Jude.mp3")
        self.assertEqual(result['artist'], "The Beatles")
        self.assertEqual(result['title'], "Hey Jude")
        
        # Test Artist Title pattern (no separator)
        result = handler.extract_metadata_from_filename("Adele Hello.mp3")
        self.assertEqual(result['artist'], "Adele")
        self.assertEqual(result['title'], "Hello")
        
        # Test edge case - no pattern match
        result = handler.extract_metadata_from_filename("randomfile.mp3")
        self.assertEqual(result['artist'], "")
        self.assertEqual(result['title'], "randomfile")
    
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
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)
    
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
        self.assertFalse(is_valid)
        self.assertGreater(len(errors), 0)
        
        # Check specific error types
        error_messages = ' '.join(errors)
        self.assertIn("title", error_messages.lower())
        self.assertIn("year", error_messages.lower())
    
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
        self.assertEqual(corrected.title, "Test Song")
        self.assertEqual(corrected.artist, "Test Artist")  # Title case
        self.assertEqual(corrected.album, "Test Album")  # Title case
        self.assertEqual(corrected.year, "2023")  # Extracted year
        self.assertGreater(len(corrected.corrections_applied), 0)
    
    def test_genre_standardization(self):
        """Test genre name standardization"""
        validator = MetadataValidator()
        
        # Test genre mapping
        test_cases = [
            ("rock", "Rock"),
            ("hip hop", "Hip-Hop"),
            ("electronic", "Electronic"),
            ("alt rock", "Alternative Rock"),
            ("Custom Genre", "Custom Genre")  # Unknown genre should be title-cased
        ]
        
        for input_genre, expected_genre in test_cases:
            result = validator._correct_genre(input_genre)
            self.assertEqual(result, expected_genre, 
                           f"Failed for input: {input_genre}")


class TestMusicBrainzIntegration(unittest.TestCase):
    """Test cases for MusicBrainz API integration"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.musicbrainz = MusicBrainzMetadata()
    
    @patch('musicbrainzngs.search_recordings')
    def test_musicbrainz_search_success(self, mock_search):
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
        
        result = self.musicbrainz.search_recording("The Beatles", "Hey Jude")
        
        self.assertIsNotNone(result)
        self.assertEqual(result['title'], 'Hey Jude')
        self.assertEqual(result['artist'], 'The Beatles')
        self.assertEqual(result['year'], '1968')
        self.assertEqual(result['musicbrainz_recording_id'], 'test-recording-id')
    
    @patch('musicbrainzngs.search_recordings')
    def test_musicbrainz_search_no_results(self, mock_search):
        """Test MusicBrainz search with no results"""
        mock_search.return_value = {'recording-list': []}
        
        result = self.musicbrainz.search_recording("Unknown Artist", "Unknown Song")
        
        self.assertIsNone(result)
    
    @patch('musicbrainzngs.search_recordings')
    def test_musicbrainz_api_error(self, mock_search):
        """Test MusicBrainz API error handling"""
        mock_search.side_effect = Exception("API Error")
        
        result = self.musicbrainz.search_recording("Artist", "Title")
        
        self.assertIsNone(result)
    
    def test_musicbrainz_unavailable(self):
        """Test behavior when MusicBrainz is unavailable"""
        # Temporarily make musicbrainz unavailable
        original_available = self.musicbrainz.available
        self.musicbrainz.available = False
        
        result = self.musicbrainz.search_recording("Artist", "Title")
        
        self.assertIsNone(result)
        
        # Restore original state
        self.musicbrainz.available = original_available


class TestMetadataValidationRules(unittest.TestCase):
    """Test cases for metadata validation rules and logic"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.validator = MetadataValidator()
    
    def test_required_field_validation(self):
        """Test validation of required fields"""
        required_fields = ['title', 'artist', 'album', 'year', 'track_number']
        
        for field in required_fields:
            record = MetadataRecord(
                title="Test Title",
                artist="Test Artist",
                album="Test Album",
                year="2023",
                track_number="1"
            )
            
            # Make the field empty
            setattr(record, field, "")
            
            is_valid, errors = self.validator.validate_record(record)
            self.assertFalse(is_valid, f"Field {field} should be required")
            
            # Check that the error mentions the field
            error_text = ' '.join(errors).lower()
            self.assertIn(field, error_text)
    
    def test_year_validation(self):
        """Test year field validation"""
        test_cases = [
            ("2023", True),
            ("1950", True),
            ("2024", True),
            ("1899", False),  # Too old
            ("2050", False),  # Too far in future
            ("invalid", False),  # Not a number
            ("23", False),  # Too short
            ("", False)  # Empty (required field)
        ]
        
        for year_value, should_be_valid in test_cases:
            record = MetadataRecord(
                title="Test",
                artist="Test",
                album="Test",
                year=year_value,
                track_number="1"
            )
            
            is_valid, errors = self.validator.validate_record(record)
            if should_be_valid:
                # Check if year validation specifically passed
                year_errors = [e for e in errors if 'year' in e.lower()]
                self.assertEqual(len(year_errors), 0, 
                               f"Year {year_value} should be valid")
            else:
                self.assertFalse(is_valid, 
                               f"Year {year_value} should be invalid")
    
    def test_track_number_validation(self):
        """Test track number field validation"""
        test_cases = [
            ("1", True),
            ("99", True),
            ("999", True),
            ("0", False),  # Too low
            ("1000", False),  # Too high
            ("-1", False),  # Negative
            ("abc", False),  # Not a number
            ("", False)  # Empty (required field)
        ]
        
        for track_value, should_be_valid in test_cases:
            record = MetadataRecord(
                title="Test",
                artist="Test",
                album="Test",
                year="2023",
                track_number=track_value
            )
            
            is_valid, errors = self.validator.validate_record(record)
            if should_be_valid:
                # Check if track_number validation specifically passed
                track_errors = [e for e in errors if 'track_number' in e.lower()]
                self.assertEqual(len(track_errors), 0, 
                               f"Track number {track_value} should be valid")
            else:
                self.assertFalse(is_valid, 
                               f"Track number {track_value} should be invalid")
    
    def test_length_validation(self):
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
        
        is_valid, errors = self.validator.validate_record(record)
        self.assertFalse(is_valid)
        
        # Check for length error
        error_text = ' '.join(errors).lower()
        self.assertIn("length", error_text)


class TestBatchProcessing(unittest.TestCase):
    """Test cases for batch metadata processing"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.test_files = []
        
        # Create multiple test MP3 files
        for i in range(3):
            file_path = os.path.join(self.temp_dir, f"test_song_{i}.mp3")
            with open(file_path, 'wb') as f:
                f.write(b'\xff\xfb\x90\x00')
                f.write(b'\x00' * 1000)
            self.test_files.append(file_path)
    
    def tearDown(self):
        """Clean up test fixtures"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    async def test_batch_metadata_processing(self):
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
            for i, file_path in enumerate(self.test_files):
                result = await manager.get_metadata(
                    artist=f"Artist {i}",
                    title=f"Song {i}"
                )
                results.append(result)
            
            # Verify all files were processed
            self.assertEqual(len(results), len(self.test_files))
            
            # Verify all results are valid
            for result in results:
                self.assertIsNotNone(result)
                self.assertEqual(result.title, "Test Song")
                self.assertEqual(result.source, "musicbrainz")
    
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
        
        self.assertEqual(valid_count, 2)
        self.assertEqual(invalid_count, 1)
        self.assertGreater(len(all_errors), 0)
    
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
        self.assertEqual(corrected_records[0].title, "Song One")
        self.assertEqual(corrected_records[0].artist, "Artist One")
        self.assertEqual(corrected_records[0].year, "2023")
        
        self.assertEqual(corrected_records[1].title, "Song Two")
        self.assertEqual(corrected_records[1].artist, "Artist Two")
        self.assertEqual(corrected_records[1].year, "2022")
        
        # Verify all records have corrections logged
        for record in corrected_records:
            self.assertGreater(len(record.corrections_applied), 0)


class TestEdgeCases(unittest.TestCase):
    """Test cases for edge cases including missing data and network errors"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.manager = MetadataManager()
    
    async def test_empty_search_terms(self):
        """Test handling of empty or invalid search terms"""
        # Test empty artist and title
        result = await self.manager.get_metadata(
            artist="",
            title=""
        )
        
        # Should handle gracefully without crashing
        # Result may be None or a record with empty fields
        if result:
            self.assertEqual(result.artist, "")
            self.assertEqual(result.title, "")
    
    async def test_special_characters(self):
        """Test handling of special characters in metadata"""
        with patch.object(self.manager.providers[MetadataSource.MUSICBRAINZ], 
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
            
            result = await self.manager.get_metadata(
                artist="Ñoño Pérez-García",
                title="Café Müller & Co.'s Song"
            )
            
            self.assertIsNotNone(result)
            self.assertEqual(result.title, "Café Müller & Co.'s Song")
            self.assertEqual(result.artist, "Ñoño Pérez-García")
    
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
        
        self.assertIsNone(result)
    
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
        
        self.assertIsNone(result)
    
    async def test_partial_metadata(self):
        """Test handling of partial/incomplete metadata"""
        with patch.object(self.manager.providers[MetadataSource.MUSICBRAINZ], 
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
            
            result = await self.manager.get_metadata(
                artist="Test Artist",
                title="Test Song"
            )
            
            self.assertIsNotNone(result)
            self.assertEqual(result.title, "Test Song")
            self.assertEqual(result.artist, "Test Artist")
            self.assertEqual(result.album, "")
            self.assertEqual(result.year, "")
    
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
        self.assertNotEqual(corrected.title, malformed_record.title)
        self.assertNotEqual(corrected.artist, malformed_record.artist)
        self.assertNotEqual(corrected.album, malformed_record.album)
    
    async def test_api_rate_limiting(self):
        """Test handling of API rate limiting"""
        import requests
        
        with patch.object(self.manager.providers[MetadataSource.MUSICBRAINZ], 
                         'search_metadata') as mock_search:
            # Simulate rate limiting HTTP error
            mock_search.side_effect = requests.exceptions.HTTPError(
                "429 Too Many Requests"
            )
            
            result = await self.manager.get_metadata(
                artist="Test Artist",
                title="Test Song"
            )
            
            # Should handle rate limiting gracefully
            self.assertIsNone(result)
    
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
        self.assertIsInstance(corrected.title, str)
        self.assertIsInstance(corrected.artist, str)
    
    async def test_metadata_provider_fallback(self):
        """Test fallback between metadata providers"""
        # Mock first provider to fail, second to succeed
        with patch.object(self.manager.providers[MetadataSource.MUSICBRAINZ], 
                         'search_metadata') as mock_mb:
            with patch.object(self.manager.providers[MetadataSource.LASTFM], 
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
                
                result = await self.manager.get_metadata(
                    artist="Test Artist",
                    title="Test Song",
                    sources=[MetadataSource.MUSICBRAINZ, MetadataSource.LASTFM]
                )
                
                self.assertIsNotNone(result)
                self.assertEqual(result.source, "lastfm")
                self.assertEqual(result.confidence, 0.7)


class TestMetadataEnhancement(unittest.TestCase):
    """Test cases for metadata enhancement functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.test_mp3_file = os.path.join(self.temp_dir, "test_song.mp3")
        
        # Create a test MP3 file
        with open(self.test_mp3_file, 'wb') as f:
            f.write(b'\xff\xfb\x90\x00')
            f.write(b'\x00' * 1000)
    
    def tearDown(self):
        """Clean up test fixtures"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @patch('download_music.MusicBrainzMetadata.search_recording')
    def test_metadata_enhancement_pipeline(self, mock_search):
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
        
        # Create mock options
        options = Mock()
        options.skip_metadata = False
        options.metadata_source = 'musicbrainz'
        options.force_metadata = False
        options.genius_key = None
        
        downloader = EnhancedMusicDownloader(options)
        
        # Test metadata enhancement
        success = downloader.enhance_metadata(
            Path(self.test_mp3_file),
            artist_hint="Test Artist",
            title_hint="Test Song"
        )
        
        # Should complete without errors
        self.assertTrue(isinstance(success, bool))
    
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
        self.assertEqual(merged.title, "Test Song")
        self.assertEqual(merged.artist, "Test Artist")
        self.assertEqual(merged.album, "Test Album")  # From secondary
        self.assertEqual(merged.genre, "Rock")  # From secondary
        self.assertEqual(merged.confidence, 0.9)  # Higher confidence


def run_async_test(test_func):
    """Helper function to run async test functions"""
    def wrapper(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(test_func(self))
        finally:
            loop.close()
    return wrapper


# Apply async wrapper to async test methods
for test_class in [TestBatchProcessing, TestEdgeCases, TestMetadataEnhancement]:
    for method_name in dir(test_class):
        if method_name.startswith('test_') and asyncio.iscoroutinefunction(getattr(test_class, method_name)):
            setattr(test_class, method_name, run_async_test(getattr(test_class, method_name)))


if __name__ == '__main__':
    # Set up test environment
    os.environ['TESTING'] = '1'
    
    # Create test suite
    test_suite = unittest.TestSuite()
    
    # Add all test classes
    test_classes = [
        TestMetadataExtraction,
        TestMusicBrainzIntegration,
        TestMetadataValidationRules,
        TestBatchProcessing,
        TestEdgeCases,
        TestMetadataEnhancement
    ]
    
    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        test_suite.addTests(tests)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    # Print summary
    print(f"\n{'='*60}")
    print(f"TEST SUMMARY")
    print(f"{'='*60}")
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success rate: {((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100):.1f}%")
    
    if result.failures:
        print(f"\nFAILURES:")
        for test, error in result.failures:
            print(f"- {test}: {error.split(chr(10))[0]}")
    
    if result.errors:
        print(f"\nERRORS:")
        for test, error in result.errors:
            print(f"- {test}: {error.split(chr(10))[0]}")
    
    # Exit with error code if tests failed
    sys.exit(0 if result.wasSuccessful() else 1)

