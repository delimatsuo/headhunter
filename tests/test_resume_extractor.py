#!/usr/bin/env python3
"""
Test suite for Resume Text Extractor
"""

import sys
import os
import unittest
from pathlib import Path

# Add scripts directory to path
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts'))

from resume_extractor import ResumeTextExtractor, ExtractionResult


class TestResumeTextExtractor(unittest.TestCase):
    """Test suite for Resume Text Extractor"""
    
    @classmethod
    def setUpClass(cls):
        """Initialize extractor once for all tests"""
        cls.extractor = ResumeTextExtractor()
        cls.test_files_dir = Path(__file__).parent / "sample_resumes"
        print(f"\n✓ ResumeTextExtractor initialized")
        print(f"✓ Test files directory: {cls.test_files_dir}")
    
    def test_text_file_extraction(self):
        """Test extraction from plain text files"""
        test_file = self.test_files_dir / "sarah_chen_resume.txt"
        if not test_file.exists():
            self.skipTest(f"Test file not found: {test_file}")
        
        result = self.extractor.extract_text_from_file(str(test_file))
        
        self.assertTrue(result.success)
        self.assertEqual(result.file_type, 'txt')
        self.assertGreater(len(result.text), 100)  # Should have substantial content
        self.assertIn("Sarah Chen", result.text)
        self.assertIn("Senior Software Engineer", result.text)
        
        print(f"✓ Text extraction - {len(result.text)} characters extracted")
    
    def test_pdf_file_extraction(self):
        """Test extraction from PDF files"""
        test_file = self.test_files_dir / "james_thompson_resume.pdf"
        if not test_file.exists():
            self.skipTest(f"Test file not found: {test_file}")
        
        result = self.extractor.extract_text_from_file(str(test_file))
        
        self.assertTrue(result.success)
        self.assertEqual(result.file_type, 'pdf')
        self.assertGreater(len(result.text), 50)
        self.assertIn("James Thompson", result.text)
        
        print(f"✓ PDF extraction - {len(result.text)} characters extracted")
    
    def test_docx_file_extraction(self):
        """Test extraction from DOCX files"""
        test_file = self.test_files_dir / "lisa_park_resume.docx"
        if not test_file.exists():
            self.skipTest(f"Test file not found: {test_file}")
        
        result = self.extractor.extract_text_from_file(str(test_file))
        
        self.assertTrue(result.success)
        self.assertEqual(result.file_type, 'docx')
        self.assertGreater(len(result.text), 100)
        self.assertIn("Lisa Park", result.text)
        self.assertIn("Full-Stack Developer", result.text)
        
        print(f"✓ DOCX extraction - {len(result.text)} characters extracted")
    
    def test_image_file_extraction(self):
        """Test OCR extraction from image files"""
        test_file = self.test_files_dir / "john_smith_resume.png"
        if not test_file.exists():
            self.skipTest(f"Test file not found: {test_file}")
        
        result = self.extractor.extract_text_from_file(str(test_file))
        
        self.assertTrue(result.success)
        self.assertEqual(result.file_type, 'image')
        self.assertGreater(len(result.text), 20)  # OCR might not be perfect
        
        # OCR might not be 100% accurate, so check for likely text
        text_lower = result.text.lower()
        self.assertTrue(
            "john" in text_lower or "smith" in text_lower or "engineer" in text_lower,
            f"Expected text not found in OCR result: {result.text}"
        )
        
        print(f"✓ OCR extraction - {len(result.text)} characters extracted")
        print(f"  Sample OCR text: {result.text[:100]}...")
    
    def test_batch_extraction(self):
        """Test extraction from multiple files"""
        test_files = [
            self.test_files_dir / "sarah_chen_resume.txt",
            self.test_files_dir / "marcus_rodriguez_resume.txt",
            self.test_files_dir / "emily_watson_resume.txt"
        ]
        
        # Filter to only existing files
        existing_files = [str(f) for f in test_files if f.exists()]
        if not existing_files:
            self.skipTest("No test files found for batch extraction")
        
        results = self.extractor.extract_text_from_multiple_files(existing_files)
        
        self.assertEqual(len(results), len(existing_files))
        successful_results = [r for r in results if r.success]
        self.assertGreater(len(successful_results), 0)
        
        # Check summary stats
        summary = self.extractor.get_extraction_summary(results)
        self.assertEqual(summary['total_files'], len(existing_files))
        self.assertGreater(summary['success_rate'], 0)
        
        print(f"✓ Batch extraction - {summary['successful']}/{summary['total_files']} successful")
        print(f"  Success rate: {summary['success_rate']:.1f}%")
    
    def test_nonexistent_file(self):
        """Test handling of nonexistent files"""
        result = self.extractor.extract_text_from_file("nonexistent_file.txt")
        
        self.assertFalse(result.success)
        self.assertIn("File not found", result.error_message)
        
        print("✓ Nonexistent file handling")
    
    def test_unsupported_file_type(self):
        """Test handling of unsupported file types"""
        # Create a temporary file with unsupported extension
        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.xyz', delete=False) as f:
            f.write(b"test content")
            temp_file = f.name
        
        try:
            result = self.extractor.extract_text_from_file(temp_file)
            self.assertFalse(result.success)
            self.assertIn("Unsupported file type", result.error_message)
            
            print("✓ Unsupported file type handling")
        finally:
            os.unlink(temp_file)
    
    def test_supported_file_types(self):
        """Test that all expected file types are supported"""
        expected_types = {'.pdf', '.docx', '.doc', '.txt', '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff'}
        self.assertEqual(self.extractor.supported_types, expected_types)
        
        print(f"✓ Supported file types: {', '.join(sorted(expected_types))}")


def run_tests():
    """Run all tests"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test class
    suite.addTests(loader.loadTestsFromTestCase(TestResumeTextExtractor))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "="*50)
    print("RESUME EXTRACTOR TEST SUMMARY")
    print("="*50)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success: {result.wasSuccessful()}")
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)