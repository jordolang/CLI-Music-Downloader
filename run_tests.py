#!/usr/bin/env python3
"""
Test runner for CLI Music Downloader metadata functionality

This script provides various ways to run the test suite:
- All tests
- Specific test categories
- Individual test methods
- With different verbosity levels
"""

import sys
import os
import argparse
import subprocess
from pathlib import Path

def run_unittest():
    """Run tests using unittest"""
    test_file = Path(__file__).parent / "tests" / "test_metadata_functionality.py"
    
    cmd = [sys.executable, str(test_file)]
    
    print("Running tests with unittest...")
    print(f"Command: {' '.join(cmd)}")
    print("=" * 60)
    
    result = subprocess.run(cmd, cwd=Path(__file__).parent)
    return result.returncode

def run_pytest(args=None):
    """Run tests using pytest"""
    cmd = [sys.executable, "-m", "pytest"]
    
    if args:
        cmd.extend(args)
    else:
        # Default pytest arguments
        cmd.extend([
            "tests/",
            "-v",
            "--tb=short",
            "--strict-markers"
        ])
    
    print("Running tests with pytest...")
    print(f"Command: {' '.join(cmd)}")
    print("=" * 60)
    
    result = subprocess.run(cmd, cwd=Path(__file__).parent)
    return result.returncode

def main():
    parser = argparse.ArgumentParser(
        description='Test runner for CLI Music Downloader metadata functionality',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  python run_tests.py                                    # Run all tests with unittest
  python run_tests.py --pytest                          # Run all tests with pytest
  python run_tests.py --pytest -k "test_metadata"       # Run specific tests
  python run_tests.py --pytest --cov=scripts            # Run with coverage
  python run_tests.py --category extraction             # Run specific category
  python run_tests.py --list                            # List available test categories
        '''
    )
    
    parser.add_argument('--pytest', action='store_true',
                       help='Use pytest instead of unittest')
    parser.add_argument('--category', choices=[
        'extraction', 'musicbrainz', 'validation', 
        'batch', 'edge_cases', 'enhancement'
    ], help='Run tests for specific category')
    parser.add_argument('--list', action='store_true',
                       help='List available test categories')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Verbose output')
    parser.add_argument('--quiet', '-q', action='store_true',
                       help='Quiet output')
    parser.add_argument('pytest_args', nargs='*',
                       help='Additional arguments to pass to pytest')
    
    args = parser.parse_args()
    
    if args.list:
        print("Available test categories:")
        print("- extraction: Metadata extraction from various sources")
        print("- musicbrainz: MusicBrainz API integration tests")
        print("- validation: Metadata validation rules and logic")
        print("- batch: Batch metadata processing tests")
        print("- edge_cases: Edge cases and error handling")
        print("- enhancement: Metadata enhancement functionality")
        return 0
    
    # Check if required dependencies are available
    if args.pytest:
        try:
            import pytest
        except ImportError:
            print("Error: pytest not installed. Install with: pip install pytest pytest-asyncio pytest-mock")
            return 1
    
    # Build pytest arguments for categories
    pytest_args = list(args.pytest_args) if args.pytest_args else []
    
    if args.category:
        category_map = {
            'extraction': 'TestMetadataExtraction',
            'musicbrainz': 'TestMusicBrainzIntegration',
            'validation': 'TestMetadataValidationRules',
            'batch': 'TestBatchProcessing',
            'edge_cases': 'TestEdgeCases',
            'enhancement': 'TestMetadataEnhancement'
        }
        
        test_class = category_map[args.category]
        
        if args.pytest:
            pytest_args.extend(['-k', test_class])
        else:
            print(f"Running {args.category} tests...")
            # For unittest, we'll modify the approach
            os.environ['TEST_CATEGORY'] = test_class
    
    if args.verbose and args.pytest:
        pytest_args.append('-vv')
    elif args.quiet and args.pytest:
        pytest_args.append('-q')
    
    # Run the tests
    if args.pytest:
        return run_pytest(pytest_args)
    else:
        return run_unittest()

def get_tests_help() -> str:
    """Get help text for the test runner tool"""
    return """
🧪 Test Runner Tool Help
======================

This tool runs the test suite for the CLI Music Downloader to ensure all 
components are working correctly.

Features:
  • Runs comprehensive tests for metadata functionality
  • Tests integration with MusicBrainz, Genius, and other services
  • Validates metadata extraction, correction, and enhancement
  • Tests batch processing functionality
  • Includes edge case and error handling tests

Test Categories:
  • extraction: Metadata extraction from various sources
  • musicbrainz: MusicBrainz API integration tests
  • validation: Metadata validation rules and logic
  • batch: Batch metadata processing tests
  • edge_cases: Edge cases and error handling
  • enhancement: Metadata enhancement functionality

Usage:
  The test runner will execute all available tests and display the results.
  This helps ensure the music downloader is functioning properly after 
  installation or updates.

Note: Some tests may require internet connectivity to test API integrations.
    """

def run_tests_ui(progress_callback=None) -> tuple[bool, str]:
    """UI-friendly wrapper for running tests
    
    Args:
        progress_callback: Optional callback function for progress updates
        
    Returns:
        tuple[bool, str]: (success, output_message)
    """
    try:
        if progress_callback:
            progress_callback("🧪 Starting test suite...")
        
        # Run unittest by default
        return_code = run_unittest()
        
        if return_code == 0:
            message = "✅ All tests passed successfully!"
            if progress_callback:
                progress_callback(message)
            return True, message
        else:
            message = f"❌ Some tests failed (exit code: {return_code})"
            if progress_callback:
                progress_callback(message)
            return False, message
    
    except Exception as e:
        error_msg = f"💥 Error running tests: {e}"
        if progress_callback:
            progress_callback(error_msg)
        return False, error_msg

if __name__ == '__main__':
    sys.exit(main())

