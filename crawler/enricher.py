"""
Stage 2: The Alchemist (Data Enrichment)
-----------------------------------------
Enriches raw church data with:
- Geocoding (address → lat/lng via Kakao API)
- Wide-area landmark discovery (1km radius)
- SEO tag generation for inflow traffic

Strategy:
- Radius: 1km (expanded for wide-area coverage)
- Priority 1: Category codes (AT4, CT1, MT1)
- Priority 2: Keywords (백화점, 아울렛, 터미널, etc.)
- Sort: Accuracy (not distance)
"""

import os
import json
import time
import random
import argparse
import logging
import requests
from dotenv import load_dotenv

# =============================================================================
# CONFIGURATION
# =============================================================================

# Load .env file
load_dotenv()

# Kakao API
KAKAO_API_KEY = os.getenv('KAKAO_API_KEY')
KAKAO_GEOCODE_URL = "https://dapi.kakao.com/v2/local/search/address.json"
KAKAO_KEYWORD_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"
KAKAO_CATEGORY_URL = "https://dapi.kakao.com/v2/local/search/category.json"

# File paths
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
RAW_DATA_FILE = os.path.join(DATA_DIR, 'catholic_data.json')
ENRICHED_DATA_FILE = os.path.join(DATA_DIR, 'enriched_church_data.json')

# API Settings
REQUEST_TIMEOUT = 15       # 노후 서버 대응
NEARBY_RADIUS = 1000       # 1km
DELAY_MIN = 0.5            # 카카오 API 보호
DELAY_MAX = 1.5

# Priority 1: Category codes for landmark discovery
# AT4: 관광명소 (수목원, 공원, 유적지, 테마파크)
# CT1: 문화시설 (박물관, 미술관, 공연장, 문화원)
# SW8: 지하철역 (주요 교통 거점)
PRIORITY_CATEGORIES = ["AT4", "CT1", "SW8"]

# Priority 2: Fallback keywords - 관광/여행 키워드 집중
FALLBACK_KEYWORDS = [
    "수목원", "공원", "유적지", "명소",      # 자연/역사
    "박물관", "미술관", "전시관", "기념관",  # 문화시설
    "해수욕장", "호수", "산", "계곡",        # 자연경관
    "기차역", "터미널", "KTX역",             # 교통거점
    "대학교", "캠퍼스"                       # 대학가
]

# =============================================================================
# LOGGING
# =============================================================================

def setup_logging(verbose=False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    return logging.getLogger(__name__)

# =============================================================================
# ENRICHER CLASS
# =============================================================================

class ChurchEnricher:
    """
    Enriches church data with location info and SEO tags using Kakao API.
    
    Strategy:
    - Wide-area landmark discovery (1km radius)
    - Priority-based category and keyword search
    - Accuracy-based sorting (not distance)
    """
    
    def __init__(self, test_mode=False, force_update=False):
        self.test_mode = test_mode
        self.force_update = force_update  # Re-enrich already processed items
        self.logger = logging.getLogger(__name__)
        
        if not KAKAO_API_KEY:
            raise ValueError("KAKAO_API_KEY not found in environment. Check .env file.")
        
        self.headers = {
            "Authorization": f"KakaoAK {KAKAO_API_KEY}"
        }
        
        self.processed_count = 0
        self.skipped_count = 0
        self.failed_count = 0
        
        self.logger.info(f"Enricher initialized (TestMode={test_mode}, ForceUpdate={force_update})")

    def _sleep_random(self):
        """Rate limiting delay."""
        time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))

    def _geocode_address(self, address):
        """
        Convert address to coordinates using Kakao API.
        Returns (lat, lng) or (None, None) on failure.
        """
        if not address:
            return None, None
        
        try:
            response = requests.get(
                KAKAO_GEOCODE_URL,
                headers=self.headers,
                params={"query": address},
                timeout=REQUEST_TIMEOUT
            )
            response.raise_for_status()
            
            data = response.json()
            documents = data.get("documents", [])
            
            if documents:
                doc = documents[0]
                lat = float(doc.get("y", 0))
                lng = float(doc.get("x", 0))
                return lat, lng
            
            return None, None
            
        except Exception as e:
            self.logger.error(f"Geocoding failed for '{address}': {e}")
            return None, None

    def _search_by_category(self, lat, lng, category_code):
        """
        Search for landmarks by category code using Kakao Category API.
        Sorted by accuracy (default).
        """
        if not lat or not lng:
            return []
        
        try:
            response = requests.get(
                KAKAO_CATEGORY_URL,
                headers=self.headers,
                params={
                    "category_group_code": category_code,
                    "x": str(lng),
                    "y": str(lat),
                    "radius": NEARBY_RADIUS,
                    "sort": "accuracy",  # Sort by accuracy, not distance
                    "size": 3
                },
                timeout=REQUEST_TIMEOUT
            )
            response.raise_for_status()
            
            data = response.json()
            return data.get("documents", [])
            
        except Exception as e:
            self.logger.debug(f"Category search failed for {category_code}: {e}")
            return []

    def _search_by_keyword(self, lat, lng, keyword):
        """
        Search for landmarks by keyword using Kakao Keyword API.
        Sorted by accuracy (default).
        """
        if not lat or not lng:
            return []
        
        try:
            response = requests.get(
                KAKAO_KEYWORD_URL,
                headers=self.headers,
                params={
                    "query": keyword,
                    "x": str(lng),
                    "y": str(lat),
                    "radius": NEARBY_RADIUS,
                    "sort": "accuracy",
                    "size": 3
                },
                timeout=REQUEST_TIMEOUT
            )
            response.raise_for_status()
            
            data = response.json()
            return data.get("documents", [])
            
        except Exception as e:
            self.logger.debug(f"Keyword search failed for {keyword}: {e}")
            return []

    def _discover_landmarks(self, lat, lng):
        """
        Discover landmarks using priority-based search strategy.
        
        Priority 1: Category codes (AT4, CT1, MT1)
        Priority 2: Keywords (백화점, 아울렛, etc.)
        
        Returns: Best landmark(s) found
        """
        if not lat or not lng:
            return []
        
        all_landmarks = []
        
        # Priority 1: Search by category codes
        for category in PRIORITY_CATEGORIES:
            self._sleep_random()
            results = self._search_by_category(lat, lng, category)
            
            for doc in results:
                landmark = {
                    "name": doc.get("place_name", ""),
                    "category": doc.get("category_group_name", ""),
                    "category_code": category,
                    "distance": int(doc.get("distance", 0)),
                    "address": doc.get("road_address_name", "") or doc.get("address_name", ""),
                    "priority": 1
                }
                all_landmarks.append(landmark)
        
        # If no results from categories, try keywords
        if not all_landmarks:
            for keyword in FALLBACK_KEYWORDS:
                self._sleep_random()
                results = self._search_by_keyword(lat, lng, keyword)
                
                if results:
                    for doc in results:
                        landmark = {
                            "name": doc.get("place_name", ""),
                            "category": doc.get("category_group_name", "") or keyword,
                            "category_code": "KEYWORD",
                            "distance": int(doc.get("distance", 0)),
                            "address": doc.get("road_address_name", "") or doc.get("address_name", ""),
                            "priority": 2
                        }
                        all_landmarks.append(landmark)
                    break  # Stop after first successful keyword
        
        # Remove duplicates by name
        seen = set()
        unique_landmarks = []
        for lm in all_landmarks:
            if lm["name"] not in seen:
                seen.add(lm["name"])
                unique_landmarks.append(lm)
        
        return unique_landmarks[:5]  # Return top 5

    def _generate_seo_tags(self, church_name, address, landmarks):
        """
        Generate SEO-friendly tags for inflow traffic.
        
        Tags include:
        - Church name variations
        - District/area tags
        - Landmark proximity tags
        """
        tags = set()
        
        # Church name tags
        tags.add(church_name)
        if "성당" not in church_name:
            tags.add(f"{church_name}성당")
        
        # Extract district from address
        district = None
        if address:
            parts = address.split()
            for part in parts:
                if part.endswith(("동", "읍", "면")):
                    district = part
                    tags.add(f"{part}성당")
                    tags.add(f"{part}미사시간")
                    tags.add(f"{part}천주교")
                    break
        
        # Landmark proximity tags (most valuable for SEO)
        for lm in landmarks[:3]:  # Top 3 landmarks only
            full_name = lm.get("name", "")
            if full_name:
                # Full landmark name (with branch info like "노브랜드 세종조치원점")
                tags.add(f"{full_name}근처성당")
                tags.add(f"{full_name}주변미사")
                
                # Clean short name (brand only like "노브랜드")
                short_name = full_name.split()[0] if " " in full_name else full_name
                if short_name != full_name:
                    tags.add(f"{short_name}근처성당")
                
                # Additional tags for high-value landmarks (관광/여행 집중)
                category = lm.get("category", "")
                category_code = lm.get("category_code", "")
                
                # 관광명소 태그
                if "관광" in category or category_code == "AT4":
                    tags.add(f"{full_name}앞성당")
                    tags.add(f"{full_name}여행")
                
                # 문화시설 태그
                if "문화" in category or category_code == "CT1":
                    tags.add(f"{full_name}근처미사")
        
        return list(tags)

    def enrich_church(self, church):
        """
        Enrich a single church with location, landmarks, and SEO data.
        """
        name = church.get("name", "Unknown")
        address = church.get("address", "")
        
        self.logger.info(f"Enriching: {name}")
        
        # Geocoding
        self._sleep_random()
        lat, lng = self._geocode_address(address)
        
        if lat and lng:
            church["location"] = {"lat": lat, "lng": lng}
            self.logger.debug(f"  Geocoded: ({lat:.4f}, {lng:.4f})")
        else:
            church["location"] = None
            self.logger.warning(f"  Geocoding failed for {name}")
        
        # Landmark discovery (priority-based)
        landmarks = []
        if lat and lng:
            landmarks = self._discover_landmarks(lat, lng)
            church["nearby_landmarks"] = landmarks
            self.logger.info(f"  Found {len(landmarks)} landmarks")
            for lm in landmarks[:2]:
                self.logger.debug(f"    - {lm['name']} ({lm['distance']}m)")
        else:
            church["nearby_landmarks"] = []
        
        # SEO tag generation
        seo_tags = self._generate_seo_tags(name, address, landmarks)
        church["seo_tags"] = seo_tags
        self.logger.debug(f"  Generated {len(seo_tags)} SEO tags")
        
        # Mark as enriched
        church["enrichment_status"] = "completed"
        church["enrichment_version"] = "v2"  # Track version for re-enrichment
        
        return church

    def run(self, max_items=None):
        """
        Main enrichment loop with incremental processing.
        """
        self.logger.info("=== Enrichment Started (v2: Wide-area Strategy) ===")
        
        # Load raw data
        if not os.path.exists(RAW_DATA_FILE):
            self.logger.error(f"Raw data file not found: {RAW_DATA_FILE}")
            return []
        
        with open(RAW_DATA_FILE, 'r', encoding='utf-8') as f:
            churches = json.load(f)
        
        self.logger.info(f"Loaded {len(churches)} churches from raw data")
        
        # Load existing enriched data for incremental update
        existing_enriched = {}
        if os.path.exists(ENRICHED_DATA_FILE) and not self.force_update:
            try:
                with open(ENRICHED_DATA_FILE, 'r', encoding='utf-8') as f:
                    for item in json.load(f):
                        if item.get("enrichment_version") == "v2":
                            existing_enriched[item.get("orgnum")] = item
                self.logger.info(f"Loaded {len(existing_enriched)} existing v2 enriched items")
            except Exception as e:
                self.logger.warning(f"Could not load existing enriched data: {e}")
        
        enriched_churches = []
        
        for i, church in enumerate(churches):
            if max_items and self.processed_count >= max_items:
                self.logger.info(f"Max items ({max_items}) reached. Stopping.")
                break
            
            orgnum = church.get("orgnum")
            
            # Check if already enriched with v2 (skip unless force_update)
            if orgnum in existing_enriched and not self.force_update:
                self.logger.debug(f"Skipping (already v2 enriched): {church.get('name')}")
                self.skipped_count += 1
                enriched_churches.append(existing_enriched[orgnum])
                continue
            
            try:
                enriched = self.enrich_church(church)
                enriched_churches.append(enriched)
                self.processed_count += 1
                
            except Exception as e:
                self.logger.error(f"Failed to enrich {church.get('name')}: {e}")
                church["enrichment_status"] = "failed"
                enriched_churches.append(church)
                self.failed_count += 1
            
            # Save periodically (every 3 items for safety)
            if (i + 1) % 3 == 0:
                self._save_progress(enriched_churches)
        
        # Final save
        self._save_progress(enriched_churches)
        
        self.logger.info(f"=== Enrichment Finished ===")
        self.logger.info(f"Processed: {self.processed_count}, Skipped: {self.skipped_count}, Failed: {self.failed_count}")
        
        return enriched_churches

    def _save_progress(self, data):
        """Save current progress to file (upsert behavior)."""
        if self.test_mode:
            self.logger.info("[TEST MODE] Skipping file save")
            return
        
        os.makedirs(DATA_DIR, exist_ok=True)
        
        with open(ENRICHED_DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        
        self.logger.info(f"Progress saved: {len(data)} churches to {ENRICHED_DATA_FILE}")


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Church Data Enricher v2 (Wide-area Landmark Strategy)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    parser.add_argument("--max-items", type=int, default=None, help="Max items to process")
    parser.add_argument("--force-update", action="store_true", help="Re-enrich all items (ignore existing v2 data)")
    parser.add_argument("--test", action="store_true", help="Test mode (no file save)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")
    
    args = parser.parse_args()
    
    setup_logging(verbose=args.verbose)
    
    try:
        enricher = ChurchEnricher(
            test_mode=args.test,
            force_update=args.force_update
        )
        result = enricher.run(max_items=args.max_items)
        
        if args.test:
            print("\n=== Sample Enriched Data ===")
            for church in result[:2]:
                print(json.dumps(church, ensure_ascii=False, indent=2))
                
    except ValueError as e:
        logging.error(f"Configuration error: {e}")
        return 1
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
