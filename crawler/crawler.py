"""
Modu-Catholic Crawler - AJAX API Version
-----------------------------------------
Uses direct AJAX API calls for efficient data collection.
No browser required - uses requests with proper headers.
"""

import time
import random
import json
import os
import argparse
import logging
import requests
from datetime import datetime
from requests.exceptions import Timeout, ConnectionError, RequestException
from bs4 import BeautifulSoup

# =============================================================================
# CONFIGURATION (Constants)
# =============================================================================

# API Endpoints
API_URL = "https://catholicapi.catholic.or.kr/app/parish/getParishList.asp"
MOBILE_DETAIL_URL = "https://maria.catholic.or.kr/mobile/church/bondang_view.asp"

# Request Settings
REQUEST_TIMEOUT = 15
DEFAULT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Content-Type': 'application/x-www-form-urlencoded',
    'Referer': 'https://maria.catholic.or.kr/',
    'Origin': 'https://maria.catholic.or.kr'
}

# Safety Limits (Defaults)
DEFAULT_MAX_PAGES = 5
DEFAULT_MAX_ITEMS = 100
ABSOLUTE_MAX_PAGES = 200      # 전체 수집용 (약 100페이지 = 2000개)
ABSOLUTE_MAX_ITEMS = 3000     # 전국 성당 수 고려

# Retry Settings
MAX_RETRIES = 3
RETRY_DELAY = 5

# Ethical Delay Range (seconds) - 노후 서버 보호용
DELAY_MIN = 2.0   # 최소 2초 대기
DELAY_MAX = 4.0   # 최대 4초 대기

# =============================================================================
# LOGGING SETUP
# =============================================================================

def setup_logging(verbose=False):
    """Configures logging for the crawler."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    return logging.getLogger(__name__)

# =============================================================================
# CRAWLER CLASS
# =============================================================================

class GoodNewsCrawler:
    """
    AJAX API-based Crawler that:
    - Calls the Catholic API directly for listing churches
    - Parses church details from mobile detail pages
    """

    def __init__(self, max_pages=DEFAULT_MAX_PAGES, max_items=DEFAULT_MAX_ITEMS, test_mode=False):
        self.max_pages = min(max_pages, ABSOLUTE_MAX_PAGES)
        self.max_items = min(max_items, ABSOLUTE_MAX_ITEMS)
        self.test_mode = test_mode
        
        self.data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
        self.collected_data = []
        self.missing_mass_times = []  # Churches without mass times for follow-up
        self.collected_orgnums = set()  # Already collected orgnums (for skip logic)
        self.skipped_count = 0  # Counter for skipped items
        self.logger = logging.getLogger(__name__)
        
        # Load existing orgnums for duplicate check
        self._load_existing_orgnums()
        
        self.logger.info(f"Crawler initialized (MaxPages={self.max_pages}, MaxItems={self.max_items}, TestMode={self.test_mode}, ExistingData={len(self.collected_orgnums)})")

    def _load_existing_orgnums(self):
        """Load orgnums from existing data file for duplicate checking."""
        filepath = os.path.join(self.data_dir, "catholic_data.json")
        if not os.path.exists(filepath):
            return
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                for item in json.load(f):
                    # Only skip if has_mass_times is True (complete data)
                    if item.get('has_mass_times') == True:
                        orgnum = item.get('orgnum')
                        if orgnum:
                            self.collected_orgnums.add(str(orgnum))
            self.logger.info(f"Loaded {len(self.collected_orgnums)} existing orgnums with mass times.")
        except Exception as e:
            self.logger.warning(f"Could not load existing orgnums: {e}")

    def _sleep_random(self):
        """Ethical delay between requests."""
        delay = random.uniform(DELAY_MIN, DELAY_MAX)
        time.sleep(delay)

    def _make_request(self, method, url, **kwargs):
        """Makes an HTTP request with retry logic and adaptive throttling."""
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                start_time = time.time()
                
                response = requests.request(
                    method, 
                    url, 
                    headers=DEFAULT_HEADERS, 
                    timeout=REQUEST_TIMEOUT, 
                    **kwargs
                )
                response.raise_for_status()
                
                # Adaptive throttling: if response took 5+ seconds, server is slow
                elapsed = time.time() - start_time
                if elapsed >= 5.0:
                    self.logger.warning(f"⚠️ 서버 응답 느림 ({elapsed:.1f}초). 30초 대기 후 재개...")
                    time.sleep(30)
                elif elapsed >= 3.0:
                    self.logger.info(f"서버 응답 지연 ({elapsed:.1f}초). 10초 추가 대기...")
                    time.sleep(10)
                
                return response
                
            except Timeout:
                self.logger.error(f"Timeout on {url} (Attempt {attempt}/{MAX_RETRIES})")
                # Server is overwhelmed, wait longer
                self.logger.warning("⏸️ 서버 타임아웃. 60초 대기 후 재시도...")
                time.sleep(60)
            except ConnectionError:
                self.logger.error(f"Connection error on {url} (Attempt {attempt}/{MAX_RETRIES})")
            except RequestException as e:
                self.logger.error(f"Request failed for {url}: {e} (Attempt {attempt}/{MAX_RETRIES})")
            
            if attempt < MAX_RETRIES:
                self.logger.info(f"Retrying in {RETRY_DELAY}s...")
                time.sleep(RETRY_DELAY)
        
        self.logger.error(f"All retries exhausted for {url}. Skipping.")
        return None

    # -------------------------------------------------------------------------
    # API Methods
    # -------------------------------------------------------------------------

    def fetch_church_list(self, keyword="", page=1, p_size=20):
        """
        Fetches church list from the Catholic API.
        Returns list of church dicts from BOARDLIST.
        """
        payload = {
            'gyoCode': '',
            'localCode': '',
            'giguCode': '',
            'keyword': keyword,
            'app': 'goodnews',
            'PAGE': str(page),
            'P_SIZE': str(p_size)
        }
        
        self.logger.info(f"API Request: Page={page}, Keyword='{keyword}', P_SIZE={p_size}")
        response = self._make_request('POST', API_URL, data=payload)
        
        if not response:
            return [], 0
        
        try:
            data = response.json()
            result_count = data.get('ResultCount', 0)
            board_list = data.get('BOARDLIST', [])
            
            self.logger.info(f"API Response: {len(board_list)} items (Total: {result_count})")
            return board_list, result_count
            
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to decode JSON: {e}")
            self.logger.debug(f"Response content: {response.text[:500]}")
            return [], 0

    def parse_church_detail(self, orgnum):
        """
        Parses mass times from the mobile detail page.
        Extracts from table.register05 which has structure:
        - th: Mass type (주일미사, 평일미사) with rowspan
        - td[0]: Day (토, 일, 월, 화, etc.)
        - td[1]: Times
        """
        self._sleep_random()
        
        params = {'app': 'goodnews', 'orgnum': orgnum}
        response = self._make_request('GET', MOBILE_DETAIL_URL, params=params)
        
        if not response:
            return {}

        try:
            soup = BeautifulSoup(response.content, 'html.parser')
            
            result = {
                'mass_times_structured': [],  # List of {type, day, times}
                'mass_times_text': ''         # Formatted text version
            }
            
            # Parse Mass Times from table.register05
            mass_table = soup.select_one('table.register05')
            if not mass_table:
                return result
            
            current_mass_type = ""
            mass_entries = []
            
            for row in mass_table.find_all('tr'):
                # Check for th (mass type header with possible rowspan)
                th = row.find('th')
                if th:
                    current_mass_type = th.get_text(strip=True)
                
                # Get all td elements in this row
                tds = row.find_all('td')
                
                if len(tds) >= 2:
                    # First td: day, Second td: times
                    day = tds[0].get_text(strip=True)
                    times = tds[1].get_text(strip=True)
                    
                    if day and times:
                        entry = {
                            'type': current_mass_type,
                            'day': day,
                            'times': times
                        }
                        mass_entries.append(entry)
                        
                elif len(tds) == 1 and th:
                    # Single td with th (less common structure)
                    times = tds[0].get_text(strip=True)
                    if times:
                        entry = {
                            'type': current_mass_type,
                            'day': '',
                            'times': times
                        }
                        mass_entries.append(entry)
            
            result['mass_times_structured'] = mass_entries
            
            # Create formatted text version
            text_parts = []
            for entry in mass_entries:
                if entry['day']:
                    text_parts.append(f"[{entry['type']}] {entry['day']}: {entry['times']}")
                else:
                    text_parts.append(f"[{entry['type']}] {entry['times']}")
            
            result['mass_times_text'] = " | ".join(text_parts)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error parsing detail for orgnum={orgnum}: {e}")
            return {}


    # -------------------------------------------------------------------------
    # Main Execution Flow
    # -------------------------------------------------------------------------

    def run(self, keyword="", start_page=1, p_size=20, fetch_details=True, force_update=False):
        """Main crawling loop using AJAX API."""
        self.logger.info(f"=== Crawling Started (ForceUpdate={force_update}) ===")
        
        items_collected = 0
        
        for page in range(start_page, start_page + self.max_pages):
            if items_collected >= self.max_items:
                self.logger.warning(f"MAX_ITEMS limit reached ({self.max_items}). Stopping.")
                break
            
            church_list, total_count = self.fetch_church_list(keyword=keyword, page=page, p_size=p_size)
            
            if not church_list:
                self.logger.info("No more data from API. Stopping.")
                break

            for item in church_list:
                if items_collected >= self.max_items:
                    self.logger.warning(f"MAX_ITEMS limit reached. Breaking.")
                    break
                
                try:
                    # API provides these fields directly:
                    # TITLE, addr, phone, father, missatime, orgnum, imgURL
                    orgnum = item.get('orgnum')
                    name = item.get('TITLE', '').strip()
                    
                    if not orgnum or not name:
                        continue

                    # Skip if already collected (unless force_update)
                    if not force_update and str(orgnum) in self.collected_orgnums:
                        self.logger.debug(f"Skipping (already collected): {name} (orgnum={orgnum})")
                        self.skipped_count += 1
                        continue

                    self.logger.info(f"Processing: {name} (orgnum={orgnum})")                    
                    # Build data entry from API response
                    data_entry = {
                        "name": name,
                        "orgnum": str(orgnum),
                        "type": self._detect_type(name),
                        "address": item.get('addr', '').strip(),
                        "phone": item.get('phone', '').strip(),
                        "mass_times": item.get('missatime', '').strip(),
                        "priest": item.get('father', '').strip(),
                        "image_url": item.get('imgURL', '').strip(),
                        "foundation_date": "",
                        "url": f"{MOBILE_DETAIL_URL}?app=goodnews&orgnum={orgnum}",
                        "crawled_at": datetime.now().isoformat()  # Crawl timestamp
                    }
                    
                    # Optionally fetch additional details from detail page
                    if fetch_details:
                        details = self.parse_church_detail(orgnum)
                        if details.get('mass_times_structured'):
                            data_entry['mass_times_structured'] = details['mass_times_structured']
                            data_entry['has_mass_times'] = True
                        else:
                            data_entry['has_mass_times'] = False
                            # Track churches without mass times for follow-up
                            self.missing_mass_times.append({
                                'name': name,
                                'orgnum': str(orgnum),
                                'url': data_entry['url'],
                                'address': data_entry['address']
                            })
                            self.logger.warning(f"No mass times found for: {name}")
                        
                        if details.get('mass_times_text'):
                            data_entry['mass_times_detail'] = details['mass_times_text']
                    else:
                        data_entry['has_mass_times'] = None  # Not checked

                    
                    self.collected_data.append(data_entry)
                    items_collected += 1
                    self.logger.info(f"Collected: {name} ({items_collected}/{self.max_items})")

                except Exception as e:
                    self.logger.error(f"Error processing item: {e}. Skipping.")
        
        # Log summary of missing mass times
        if self.missing_mass_times:
            self.logger.warning(f"Churches without mass times: {len(self.missing_mass_times)}")
        
        # Log summary including skipped items
        self.logger.info(f"=== Crawling Finished: {items_collected} collected, {self.skipped_count} skipped ===")
        return self.collected_data

    def _detect_type(self, name):
        """Detects church type based on name."""
        if "공소" in name:
            return "gongso"
        elif "성지" in name:
            return "shrine"
        return "church"

    # -------------------------------------------------------------------------
    # Data Persistence
    # -------------------------------------------------------------------------

    def save_data(self, filename="catholic_data.json"):
        """Saves data with merge logic. Skipped in test mode."""
        if self.test_mode:
            self.logger.info("[TEST MODE] Skipping file save. Printing collected data:")
            print(json.dumps(self.collected_data, ensure_ascii=False, indent=2))
            if self.missing_mass_times:
                print(f"\n=== Missing Mass Times ({len(self.missing_mass_times)} churches) ===")
                print(json.dumps(self.missing_mass_times, ensure_ascii=False, indent=2))
            return

        os.makedirs(self.data_dir, exist_ok=True)
        filepath = os.path.join(self.data_dir, filename)
        
        # Load existing data
        existing_map = {}
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    for item in json.load(f):
                        key = item.get('orgnum') or item.get('name')
                        existing_map[key] = item
                self.logger.info(f"Loaded {len(existing_map)} existing records.")
            except Exception as e:
                self.logger.warning(f"Could not load existing data: {e}")

        # Merge
        updated, added = 0, 0
        for new_item in self.collected_data:
            key = new_item.get('orgnum') or new_item.get('name')
            if key in existing_map:
                existing_map[key].update(new_item)
                updated += 1
            else:
                existing_map[key] = new_item
                added += 1
        
        # Save main data
        final_list = list(existing_map.values())
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(final_list, f, ensure_ascii=False, indent=4)
        
        self.logger.info(f"Saved to {filepath} (Updated: {updated}, Added: {added}, Total: {len(final_list)})")
        
        # Save missing mass times to separate file for follow-up
        if self.missing_mass_times:
            missing_filepath = os.path.join(self.data_dir, "missing_mass_times.json")
            
            # Load existing missing list and merge
            existing_missing = {}
            if os.path.exists(missing_filepath):
                try:
                    with open(missing_filepath, 'r', encoding='utf-8') as f:
                        for item in json.load(f):
                            existing_missing[item.get('orgnum')] = item
                except Exception:
                    pass
            
            # Add new missing entries
            for item in self.missing_mass_times:
                existing_missing[item.get('orgnum')] = item
            
            # Save
            with open(missing_filepath, 'w', encoding='utf-8') as f:
                json.dump(list(existing_missing.values()), f, ensure_ascii=False, indent=4)
            
            self.logger.warning(f"Saved {len(existing_missing)} churches without mass times to {missing_filepath}")


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Modu-Catholic AJAX Crawler",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    parser.add_argument("--keyword", default="", help="Search keyword (church name)")
    parser.add_argument("--page", type=int, default=1, help="Start page")
    parser.add_argument("--p-size", type=int, default=20, help="Items per page")
    parser.add_argument("--max-pages", type=int, default=DEFAULT_MAX_PAGES, help=f"Max pages (max: {ABSOLUTE_MAX_PAGES})")
    parser.add_argument("--max-items", type=int, default=DEFAULT_MAX_ITEMS, help=f"Max items (max: {ABSOLUTE_MAX_ITEMS})")
    parser.add_argument("--skip-details", action="store_true", help="Skip fetching detailed mass times (faster but less data)")
    parser.add_argument("--force-update", action="store_true", help="Force re-fetch even for already collected churches")
    parser.add_argument("--test", action="store_true", help="Dry-run: print results, do not save")
    parser.add_argument("--verbose", "-v", action="store_true", help="Debug logging")
    
    args = parser.parse_args()

    setup_logging(verbose=args.verbose)

    crawler = GoodNewsCrawler(
        max_pages=args.max_pages,
        max_items=args.max_items,
        test_mode=args.test
    )
    
    crawler.run(
        keyword=args.keyword, 
        start_page=args.page, 
        p_size=args.p_size,
        fetch_details=not args.skip_details,
        force_update=args.force_update
    )
    crawler.save_data()


if __name__ == "__main__":
    main()
