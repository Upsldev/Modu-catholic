"""
Modu-Catholic Crawler - Test Suite
-----------------------------------
Regression tests to ensure crawler functionality.
Run with: python -m pytest crawler/test_crawler.py -v
Or simply: python crawler/test_crawler.py
"""

import json
import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from crawler import GoodNewsCrawler, API_URL, MOBILE_DETAIL_URL, DEFAULT_HEADERS


class TestCrawlerConfig(unittest.TestCase):
    """Test configuration and initialization."""
    
    def test_api_url_is_set(self):
        """API URL should be configured correctly."""
        self.assertEqual(API_URL, "https://catholicapi.catholic.or.kr/app/parish/getParishList.asp")
    
    def test_headers_have_referer(self):
        """Headers must include Referer and Origin for API to work."""
        self.assertIn('Referer', DEFAULT_HEADERS)
        self.assertIn('Origin', DEFAULT_HEADERS)
        self.assertIn('maria.catholic.or.kr', DEFAULT_HEADERS['Referer'])
    
    def test_crawler_initialization(self):
        """Crawler should initialize with default values."""
        crawler = GoodNewsCrawler(test_mode=True)
        self.assertEqual(crawler.max_pages, 5)
        self.assertEqual(crawler.max_items, 100)
        self.assertTrue(crawler.test_mode)
        self.assertEqual(len(crawler.collected_data), 0)
    
    def test_max_limits_are_enforced(self):
        """Crawler should enforce absolute max limits."""
        crawler = GoodNewsCrawler(max_pages=999, max_items=9999, test_mode=True)
        self.assertEqual(crawler.max_pages, 50)  # ABSOLUTE_MAX_PAGES
        self.assertEqual(crawler.max_items, 1000)  # ABSOLUTE_MAX_ITEMS


class TestChurchTypeDetection(unittest.TestCase):
    """Test church type detection logic."""
    
    def setUp(self):
        self.crawler = GoodNewsCrawler(test_mode=True)
    
    def test_detect_church(self):
        """Regular church names should return 'church'."""
        self.assertEqual(self.crawler._detect_type("명동성당"), "church")
        self.assertEqual(self.crawler._detect_type("세종성요한바오로2세"), "church")
    
    def test_detect_gongso(self):
        """Names with 공소 should return 'gongso'."""
        self.assertEqual(self.crawler._detect_type("산곡공소"), "gongso")
        self.assertEqual(self.crawler._detect_type("대전 공소"), "gongso")
    
    def test_detect_shrine(self):
        """Names with 성지 should return 'shrine'."""
        self.assertEqual(self.crawler._detect_type("절두산순교성지"), "shrine")
        self.assertEqual(self.crawler._detect_type("당고개 성지"), "shrine")


class TestAPIIntegration(unittest.TestCase):
    """Integration tests for actual API calls (requires network)."""
    
    def setUp(self):
        self.crawler = GoodNewsCrawler(test_mode=True, max_items=5)
    
    def test_api_returns_data(self):
        """API should return church data for a known keyword."""
        church_list, total_count = self.crawler.fetch_church_list(keyword="세종", page=1, p_size=5)
        
        # Should return some results
        self.assertGreater(len(church_list), 0, "API should return at least one church")
        self.assertGreater(total_count, 0, "Total count should be greater than 0")
        
        # Each item should have required fields
        first_item = church_list[0]
        self.assertIn('orgnum', first_item)
        self.assertIn('TITLE', first_item)
    
    def test_api_returns_correct_fields(self):
        """API response should contain expected fields."""
        church_list, _ = self.crawler.fetch_church_list(keyword="명동", page=1, p_size=1)
        
        if church_list:
            item = church_list[0]
            expected_fields = ['orgnum', 'TITLE', 'addr', 'phone']
            for field in expected_fields:
                self.assertIn(field, item, f"API response should contain '{field}'")
    
    def test_empty_keyword_returns_all(self):
        """Empty keyword should return all churches."""
        church_list, total_count = self.crawler.fetch_church_list(keyword="", page=1, p_size=5)
        self.assertGreater(total_count, 100, "Empty keyword should return many results")
    
    def test_pagination_works(self):
        """Different pages should return different results."""
        page1, _ = self.crawler.fetch_church_list(keyword="", page=1, p_size=5)
        page2, _ = self.crawler.fetch_church_list(keyword="", page=2, p_size=5)
        
        if page1 and page2:
            # First items should be different
            self.assertNotEqual(
                page1[0].get('orgnum'), 
                page2[0].get('orgnum'),
                "Page 1 and Page 2 should have different items"
            )


class TestCrawlerRun(unittest.TestCase):
    """Test the main crawl execution."""
    
    def test_run_collects_data(self):
        """run() should collect church data."""
        crawler = GoodNewsCrawler(test_mode=True, max_items=2, max_pages=1)
        result = crawler.run(keyword="세종")
        
        self.assertGreater(len(result), 0, "Should collect at least one church")
        self.assertEqual(len(result), len(crawler.collected_data))
    
    def test_run_respects_max_items(self):
        """run() should stop when max_items is reached."""
        crawler = GoodNewsCrawler(test_mode=True, max_items=3, max_pages=5)
        result = crawler.run(keyword="")
        
        self.assertLessEqual(len(result), 3, "Should not exceed max_items")
    
    def test_collected_data_structure(self):
        """Collected data should have correct structure."""
        crawler = GoodNewsCrawler(test_mode=True, max_items=1, max_pages=1)
        result = crawler.run(keyword="세종")
        
        if result:
            item = result[0]
            required_fields = ['name', 'orgnum', 'type', 'address', 'phone', 'mass_times', 'url']
            for field in required_fields:
                self.assertIn(field, item, f"Collected data should contain '{field}'")


class TestDataPersistence(unittest.TestCase):
    """Test data saving and merging."""
    
    def setUp(self):
        self.crawler = GoodNewsCrawler(test_mode=False, max_items=1)
        self.test_file = os.path.join(self.crawler.data_dir, 'test_data.json')
        
        # Ensure data directory exists
        os.makedirs(self.crawler.data_dir, exist_ok=True)
    
    def tearDown(self):
        # Cleanup test file
        if os.path.exists(self.test_file):
            os.remove(self.test_file)
    
    def test_save_creates_file(self):
        """save_data() should create a JSON file."""
        self.crawler.collected_data = [
            {"name": "테스트성당", "orgnum": "99999", "type": "church"}
        ]
        self.crawler.save_data(filename='test_data.json')
        
        self.assertTrue(os.path.exists(self.test_file))
        
        with open(self.test_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['name'], "테스트성당")
    
    def test_save_merges_with_existing(self):
        """save_data() should merge with existing data."""
        # Create initial data
        initial_data = [{"name": "기존성당", "orgnum": "11111", "type": "church"}]
        with open(self.test_file, 'w', encoding='utf-8') as f:
            json.dump(initial_data, f)
        
        # Add new data
        self.crawler.collected_data = [
            {"name": "새성당", "orgnum": "22222", "type": "church"}
        ]
        self.crawler.save_data(filename='test_data.json')
        
        with open(self.test_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        self.assertEqual(len(data), 2, "Should have both old and new data")
    
    def test_save_updates_existing(self):
        """save_data() should update existing records by orgnum."""
        # Create initial data
        initial_data = [{"name": "기존성당", "orgnum": "11111", "type": "church", "phone": ""}]
        with open(self.test_file, 'w', encoding='utf-8') as f:
            json.dump(initial_data, f)
        
        # Update with new phone
        self.crawler.collected_data = [
            {"name": "기존성당", "orgnum": "11111", "type": "church", "phone": "02-1234-5678"}
        ]
        self.crawler.save_data(filename='test_data.json')
        
        with open(self.test_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        self.assertEqual(len(data), 1, "Should still have one record")
        self.assertEqual(data[0]['phone'], "02-1234-5678", "Phone should be updated")


# =============================================================================
# RUN TESTS
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Modu-Catholic Crawler - Test Suite")
    print("=" * 60)
    
    # Run with verbosity
    unittest.main(verbosity=2)
