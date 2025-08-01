# CLI Music Downloader - Test Suite

This directory contains comprehensive tests for the metadata functionality of the CLI Music Downloader.

## Test Structure

### Test Files

- `test_metadata_functionality.py` - Comprehensive unittest-based test suite
- `test_pytest_metadata.py` - Pytest-based test suite (same tests, different framework)
- `conftest.py` - Pytest configuration and fixtures
- `__init__.py` - Test package initialization

### Test Categories

1. **Metadata Extraction** (`TestMetadataExtraction`)
   - Filename pattern extraction
   - Field validation
   - Automatic correction
   - Genre standardization

2. **MusicBrainz Integration** (`TestMusicBrainzIntegration`)
   - API search functionality
   - Error handling
   - Response parsing
   - Availability checks

3. **Metadata Validation Rules** (`TestMetadataValidationRules`)
   - Required field validation
   - Data type validation
   - Format validation
   - Length restrictions

4. **Batch Processing** (`TestBatchProcessing`)
   - Multiple file processing
   - Validation summaries
   - Correction application
   - Performance testing

5. **Edge Cases** (`TestEdgeCases`)
   - Network errors
   - Missing data
   - Special characters
   - Unicode handling
   - API rate limiting
   - Provider fallback

6. **Metadata Enhancement** (`TestMetadataEnhancement`)
   - Complete pipeline testing
   - Multi-source merging
   - Integration testing

## Running Tests

### Using the Test Runner Script

```bash
# Run all tests with unittest
python run_tests.py

# Run all tests with pytest
python run_tests.py --pytest

# Run specific test category
python run_tests.py --category extraction
python run_tests.py --category musicbrainz
python run_tests.py --category validation
python run_tests.py --category batch
python run_tests.py --category edge_cases
python run_tests.py --category enhancement

# List available categories
python run_tests.py --list

# Run with verbose output
python run_tests.py --pytest --verbose

# Run specific tests
python run_tests.py --pytest -k "test_metadata_extraction"

# Run with coverage
python run_tests.py --pytest --cov=scripts --cov-report=html
```

### Direct Test Execution

```bash
# Run unittest-based tests directly
cd tests/
python test_metadata_functionality.py

# Run pytest-based tests
pytest test_pytest_metadata.py -v

# Run specific test class
pytest test_pytest_metadata.py::TestMetadataExtraction -v

# Run specific test method
pytest test_pytest_metadata.py::TestMetadataExtraction::test_filename_metadata_extraction -v
```

### Test with Different Verbosity Levels

```bash
# Quiet mode
python run_tests.py --pytest -q

# Normal mode
python run_tests.py --pytest

# Verbose mode
python run_tests.py --pytest -v

# Extra verbose mode
python run_tests.py --pytest -vv
```

## Test Dependencies

The tests require the following packages (included in requirements.txt):

- `pytest>=6.0.0` - Testing framework
- `pytest-asyncio>=0.21.0` - Async test support
- `pytest-mock>=3.10.0` - Mocking utilities

Install test dependencies:

```bash
pip install -r requirements.txt
```

## Test Coverage

The test suite covers:

- ✅ Metadata extraction from filenames
- ✅ MusicBrainz API integration
- ✅ Metadata validation rules
- ✅ Batch processing workflows
- ✅ Edge cases and error handling
- ✅ Network error simulation
- ✅ Unicode and special character handling
- ✅ Provider fallback mechanisms
- ✅ Metadata enhancement pipelines
- ✅ Multi-source data merging

## Mocking Strategy

The tests use extensive mocking to:

- Simulate API responses without making real network calls
- Test error conditions reliably
- Control test execution speed
- Avoid dependencies on external services

### Key Mocked Components

- `musicbrainzngs.search_recordings` - MusicBrainz API calls
- Network requests and timeouts
- File system operations
- Audio processing libraries

## Test Data

Tests use:

- Temporary directories for file operations
- Mock MP3 files with minimal headers
- Sample metadata records
- Predefined test cases for validation

## Continuous Integration

The test suite is designed to run in CI environments:

- No external dependencies
- Deterministic test results
- Clear pass/fail criteria
- Comprehensive error reporting

## Writing New Tests

When adding new functionality, follow these patterns:

1. **Test file structure**:
   ```python
   class TestNewFeature:
       def setUp(self):
           # Initialize test fixtures
           pass
       
       def test_specific_behavior(self):
           # Test one specific behavior
           pass
   ```

2. **Use appropriate assertions**:
   ```python
   # Unittest style
   self.assertEqual(actual, expected)
   self.assertTrue(condition)
   self.assertRaises(Exception, function)
   
   # Pytest style
   assert actual == expected
   assert condition
   with pytest.raises(Exception):
       function()
   ```

3. **Mock external dependencies**:
   ```python
   @patch('module.external_function')
   def test_with_mock(self, mock_function):
       mock_function.return_value = test_data
       # Test your code
   ```

4. **Use fixtures for common setup**:
   ```python
   @pytest.fixture
   def test_data():
       return create_test_data()
   ```

## Troubleshooting Tests

### Common Issues

1. **Import errors**: Ensure the scripts directory is in the Python path
2. **Missing dependencies**: Install all packages from requirements.txt
3. **File permissions**: Ensure test directories are writable
4. **Async test issues**: Use proper async test decorators

### Debugging

```bash
# Run tests with debugging output
python run_tests.py --pytest -vv -s

# Run only failing tests
python run_tests.py --pytest --lf

# Drop into debugger on failure
python run_tests.py --pytest --pdb
```

### Test Environment

Tests set the `TESTING=1` environment variable to modify behavior in the main code:

```python
if os.getenv('TESTING'):
    # Test-specific behavior
    pass
```

This allows tests to:
- Skip network calls
- Use test-specific configurations
- Enable debug logging
- Mock external services

