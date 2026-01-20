"""
Stage 3: The Publisher (WordPress + Gemini AI)
==============================================
평화의인사 - 성당 정보 자동 발행 시스템

Features:
- Gemini AI로 랜드마크 기반 소개글 생성
- WordPress REST API로 게시글 자동 발행
- 이미지 업로드 및 Featured Image 설정
- SEO 태그 자동 등록 (Get or Create)
- 중복 발행 방지 (published_log.json)

Environment: Project IDX (NixOS) / Python 3.11
"""

import os
import sys
import json
import time
import random
import logging
import requests
import base64
from typing import Optional, Dict, List, Any
from datetime import datetime
from urllib.parse import quote

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Google Generative AI
import google.generativeai as genai

# =============================================================================
# CONFIGURATION
# =============================================================================

# WordPress API
WP_URL = os.getenv("WP_URL", "").rstrip("/")  # e.g., https://your-site.com
WP_USER = os.getenv("WP_USER", "")
WP_APP_PASSWORD = os.getenv("WP_APP_PASSWORD", "")
WP_CATEGORY_ID = int(os.getenv("WP_CATEGORY_ID", "1"))  # 성당/미사시간 카테고리
DEFAULT_IMAGE_ID = int(os.getenv("DEFAULT_IMAGE_ID", "0"))  # 기본 대표 이미지

# Gemini AI
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# File Paths
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
ENRICHED_DATA_FILE = os.path.join(DATA_DIR, "enriched_church_data.json")
PUBLISHED_LOG_FILE = os.path.join(DATA_DIR, "published_log.json")

# Delay settings (API rate limiting)
DELAY_MIN = 2.0
DELAY_MAX = 5.0

# =============================================================================
# LOGGING SETUP
# =============================================================================

def setup_logging(verbose: bool = False) -> logging.Logger:
    """Configure logging for IDX terminal environment."""
    level = logging.DEBUG if verbose else logging.INFO
    
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    return logging.getLogger(__name__)

logger = setup_logging()

# =============================================================================
# GEMINI AI CONTENT GENERATOR
# =============================================================================

class GeminiContentGenerator:
    """
    Gemini AI를 활용한 성당 소개글 생성기.
    
    Persona: 30대 냉담 교우도 부담 없이 읽을 수 있는 따뜻한 어조.
    """
    
    SYSTEM_INSTRUCTION = """
당신은 가톨릭 성당 정보 서비스 '평화의인사'의 친절한 안내원입니다.
성당을 소개하는 짧은 글을 작성해주세요.

## 작성 규칙
1. **어조**: 30대 냉담 교우도 부담을 느끼지 않는 따뜻하고 환대하는 어조. 교조적이거나 딱딱한 말투는 금지.
2. **분량**: 3~4문장 (100~150자 내외)
3. **구조**: 
   - 첫 문장: 성당의 위치를 주변 랜드마크와 함께 설명
   - 중간: 방문하기 좋은 이유나 분위기 언급
   - 마지막: 환영 인사 또는 방문 권유

## 금지 사항
- "하느님", "주님" 등 종교적 표현 과도하게 사용 금지
- "~하시옵소서" 등 고어체 사용 금지
- 너무 긴 설명이나 교리적 내용 금지

## 예시
"**노브랜드 세종조치원점(533m)**과 가까워 장보기 전후에 들르기 좋습니다. 
현대적인 시설과 따뜻한 신자분들이 반겨주는 곳이에요. 
편하게 미사에 참례해 보세요!"
"""

    def __init__(self):
        if not GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY not found in environment.")
        
        genai.configure(api_key=GEMINI_API_KEY)
        self.model = genai.GenerativeModel(
            model_name="gemini-2.0-flash",
            system_instruction=self.SYSTEM_INSTRUCTION
        )
        logger.info("Gemini AI initialized.")

    def _get_closest_landmarks(self, landmarks: List[Dict], count: int = 2) -> str:
        """거리가 가장 가까운 랜드마크 정보 추출."""
        if not landmarks:
            return "주변에 다양한 편의시설이 있습니다."
        
        # Sort by distance
        sorted_lm = sorted(landmarks, key=lambda x: x.get("distance", 9999))[:count]
        
        descriptions = []
        for lm in sorted_lm:
            name = lm.get("name", "")
            distance = lm.get("distance", 0)
            category = lm.get("category", "")
            descriptions.append(f"**{name}({distance}m)** - {category}")
        
        return ", ".join(descriptions)

    def generate_intro(self, church: Dict) -> str:
        """성당 소개글을 Gemini AI로 생성."""
        name = church.get("name", "")
        address = church.get("address", "")
        priest = church.get("priest", "")
        landmarks = church.get("nearby_landmarks", [])
        
        landmark_info = self._get_closest_landmarks(landmarks)
        
        # Build prompt
        prompt = f"""
다음 성당에 대한 소개글을 작성해주세요:

- 성당명: {name}
- 주소: {address}
- 주변 랜드마크: {landmark_info}
"""
        
        if priest:
            prompt += f"- 주임신부: {priest} (반드시 언급: '현재 **{priest}**과 함께하는 따뜻한 공동체입니다.')\n"
        
        try:
            response = self.model.generate_content(prompt)
            intro = response.text.strip()
            logger.debug(f"Gemini generated intro for {name}: {intro[:50]}...")
            return intro
        
        except Exception as e:
            logger.error(f"Gemini API error for {name}: {e}")
            # Fallback intro
            return f"{name}은 {landmark_info} 근처에 위치한 따뜻한 공동체입니다. 편하게 방문해 보세요!"


# =============================================================================
# HTML CONTENT BUILDER
# =============================================================================

class HTMLContentBuilder:
    """
    성당 정보를 SEO 최적화된 HTML로 변환.
    """
    
    # Table styles
    TABLE_STYLE = """
        width: 100%;
        border-collapse: collapse;
        margin: 20px 0;
        font-size: 15px;
    """
    TH_STYLE = """
        background-color: #f3f4f6;
        padding: 12px;
        border: 1px solid #e5e7eb;
        text-align: center;
        font-weight: 600;
    """
    TD_STYLE = """
        padding: 12px;
        border: 1px solid #e5e7eb;
        text-align: center;
    """
    WARNING_BOX_STYLE = """
        background: #fee2e2;
        color: #991b1b;
        padding: 15px;
        border-radius: 8px;
        margin: 20px 0;
        font-weight: 500;
    """
    
    def __init__(self, gemini_generator: GeminiContentGenerator):
        self.gemini = gemini_generator

    def build_intro_section(self, church: Dict) -> str:
        """Gemini AI로 생성한 소개글 섹션."""
        intro = self.gemini.generate_intro(church)
        return f'<p style="font-size: 16px; line-height: 1.8; margin-bottom: 25px;">{intro}</p>'

    def build_mass_table(self, church: Dict) -> str:
        """미사 시간표 HTML 생성."""
        has_mass_times = church.get("has_mass_times", False)
        
        if not has_mass_times:
            return f'''
<div style="{self.WARNING_BOX_STYLE}">
    ⚠️ 현재 온라인 미사 시간 정보가 없습니다. 방문 전 사무실로 확인 부탁드립니다.
</div>
'''
        
        mass_times = church.get("mass_times_structured", [])
        if not mass_times:
            return f'''
<div style="{self.WARNING_BOX_STYLE}">
    ⚠️ 미사 시간 정보를 불러올 수 없습니다. 성당에 직접 문의해 주세요.
</div>
'''
        
        # Group by mass type
        sunday_masses = []
        weekday_masses = []
        
        for item in mass_times:
            mass_type = item.get("type", "")
            if "주일" in mass_type:
                sunday_masses.append(item)
            else:
                weekday_masses.append(item)
        
        html = '<h2 style="margin-top: 30px;">⏰ 미사 시간표</h2>\n'
        
        # Sunday Mass Table
        if sunday_masses:
            html += f'<h3>🙏 주일 미사</h3>\n'
            html += f'<table style="{self.TABLE_STYLE}">\n'
            html += f'<tr><th style="{self.TH_STYLE}">요일</th><th style="{self.TH_STYLE}">시간</th></tr>\n'
            for item in sunday_masses:
                day = item.get("day", "")
                times = item.get("times", "")
                html += f'<tr><td style="{self.TD_STYLE}">{day}요일</td><td style="{self.TD_STYLE}">{times}</td></tr>\n'
            html += '</table>\n'
        
        # Weekday Mass Table
        if weekday_masses:
            html += f'<h3>📿 평일 미사</h3>\n'
            html += f'<table style="{self.TABLE_STYLE}">\n'
            html += f'<tr><th style="{self.TH_STYLE}">요일</th><th style="{self.TH_STYLE}">시간</th></tr>\n'
            for item in weekday_masses:
                day = item.get("day", "")
                times = item.get("times", "")
                html += f'<tr><td style="{self.TD_STYLE}">{day}요일</td><td style="{self.TD_STYLE}">{times}</td></tr>\n'
            html += '</table>\n'
        
        html += '<p style="color: #6b7280; font-size: 13px;">※ 미사 시간은 변경될 수 있습니다. 방문 전 확인을 권장합니다.</p>\n'
        
        return html

    def build_location_section(self, church: Dict) -> str:
        """위치 및 편의 정보 섹션."""
        name = church.get("name", "")
        address = church.get("address", "")
        phone = church.get("phone", "")
        landmarks = church.get("nearby_landmarks", [])
        
        naver_map_url = f"https://map.naver.com/v5/search/{quote(address)}"
        
        html = '<h2 style="margin-top: 30px;">📍 오시는 길 & 연락처</h2>\n'
        html += '<ul style="list-style: none; padding: 0; font-size: 15px; line-height: 2;">\n'
        
        if address:
            html += f'<li>🏠 <strong>주소:</strong> {address} <a href="{naver_map_url}" target="_blank" style="color: #2563eb;">📍 지도로 위치 보기</a></li>\n'
        
        if phone:
            html += f'<li>📞 <strong>전화:</strong> <a href="tel:{phone}" style="color: #2563eb;">{phone}</a></li>\n'
        
        html += '</ul>\n'
        
        # Nearby landmarks
        if landmarks:
            html += '<h3 style="margin-top: 20px;">🏪 주변 명소</h3>\n'
            html += '<ul style="padding-left: 20px; line-height: 1.8;">\n'
            for lm in landmarks[:3]:
                lm_name = lm.get("name", "")
                distance = lm.get("distance", 0)
                category = lm.get("category", "")
                html += f'<li><strong>{lm_name}</strong> ({distance}m) - {category}</li>\n'
            html += '</ul>\n'
        
        return html

    def build_footer_section(self, church: Dict) -> str:
        """하단 섹션 (태그, 수익화, 앱 유도)."""
        seo_tags = church.get("seo_tags", [])
        
        html = '<hr style="margin: 30px 0; border: none; border-top: 1px solid #e5e7eb;">\n'
        
        # SEO Tags as hashtags
        if seo_tags:
            tags_text = " ".join([f"#{tag}" for tag in seo_tags[:10]])
            html += f'<p style="color: #6b7280; font-size: 13px;">{tags_text}</p>\n'
        
        # Monetization placeholder
        html += '<!-- AD_SLOT_BOTTOM -->\n'
        
        # App promotion button
        html += '''
<div style="text-align: center; margin: 30px 0;">
    <a href="https://moducatholic.app.link" target="_blank" 
       style="display: inline-block; background: linear-gradient(135deg, #6366f1, #8b5cf6); 
              color: white; padding: 15px 30px; border-radius: 30px; 
              text-decoration: none; font-weight: 600; font-size: 15px;">
        🔔 모두의 성당 앱에서 알림 받기
    </a>
</div>
'''
        
        # Footer note
        html += '''
<p style="color: #9ca3af; font-size: 12px; text-align: center; margin-top: 20px;">
    ⓒ 평화의인사 | 정보 수정 요청: peace-greeting@gmail.com
</p>
'''
        
        return html

    def build_full_content(self, church: Dict) -> str:
        """전체 HTML 콘텐츠 생성."""
        name = church.get("name", "")
        
        content = f'<h1 style="font-size: 24px; margin-bottom: 20px;">🙏 {name} 안내</h1>\n'
        content += self.build_intro_section(church)
        content += self.build_mass_table(church)
        content += self.build_location_section(church)
        content += self.build_footer_section(church)
        
        return content


# =============================================================================
# WORDPRESS API CLIENT
# =============================================================================

class WordPressClient:
    """
    WordPress REST API Client.
    
    Features:
    - Post creation with featured image
    - Media upload
    - Tag management (Get or Create)
    """
    
    def __init__(self):
        if not WP_URL or not WP_USER or not WP_APP_PASSWORD:
            raise ValueError("WordPress credentials not found in environment.")
        
        self.base_url = WP_URL
        self.auth = (WP_USER, WP_APP_PASSWORD)
        self.tag_cache: Dict[str, int] = {}  # tag_name -> tag_id
        
        logger.info(f"WordPress client initialized for {WP_URL}")

    def _request(self, method: str, endpoint: str, **kwargs) -> Optional[Dict]:
        """Make authenticated request to WordPress API."""
        url = f"{self.base_url}/wp-json/wp/v2/{endpoint}"
        
        try:
            response = requests.request(
                method=method,
                url=url,
                auth=self.auth,
                timeout=30,
                **kwargs
            )
            response.raise_for_status()
            return response.json()
        
        except requests.exceptions.HTTPError as e:
            logger.error(f"WP API Error ({endpoint}): {e.response.status_code} - {e.response.text[:200]}")
            return None
        except Exception as e:
            logger.error(f"WP Request failed: {e}")
            return None

    def get_or_create_tag(self, tag_name: str) -> Optional[int]:
        """Get existing tag ID or create new one."""
        # Check cache first
        if tag_name in self.tag_cache:
            return self.tag_cache[tag_name]
        
        # Search for existing tag
        result = self._request("GET", f"tags?search={quote(tag_name)}")
        
        if result:
            for tag in result:
                if tag.get("name", "").lower() == tag_name.lower():
                    self.tag_cache[tag_name] = tag["id"]
                    return tag["id"]
        
        # Create new tag
        new_tag = self._request("POST", "tags", json={"name": tag_name})
        
        if new_tag and "id" in new_tag:
            self.tag_cache[tag_name] = new_tag["id"]
            logger.debug(f"Created tag: {tag_name} (ID: {new_tag['id']})")
            return new_tag["id"]
        
        return None

    def upload_image(self, image_url: str, filename: str) -> Optional[int]:
        """Download image and upload to WordPress Media Library."""
        if not image_url:
            return None
        
        try:
            # Download image
            response = requests.get(image_url, timeout=15)
            response.raise_for_status()
            
            content_type = response.headers.get("Content-Type", "image/jpeg")
            
            # Upload to WordPress
            headers = {
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Type": content_type
            }
            
            upload_url = f"{self.base_url}/wp-json/wp/v2/media"
            upload_response = requests.post(
                upload_url,
                auth=self.auth,
                headers=headers,
                data=response.content,
                timeout=60
            )
            upload_response.raise_for_status()
            
            media_data = upload_response.json()
            media_id = media_data.get("id")
            logger.info(f"Image uploaded: {filename} (ID: {media_id})")
            return media_id
        
        except Exception as e:
            logger.warning(f"Image upload failed: {e}")
            return None

    def create_post(
        self,
        title: str,
        content: str,
        tags: List[int],
        featured_media: int = 0,
        status: str = "draft"
    ) -> Optional[Dict]:
        """Create WordPress post."""
        post_data = {
            "title": title,
            "content": content,
            "status": status,
            "categories": [WP_CATEGORY_ID],
            "tags": tags,
            "featured_media": featured_media or DEFAULT_IMAGE_ID
        }
        
        result = self._request("POST", "posts", json=post_data)
        
        if result and "id" in result:
            logger.info(f"Post created: {title} (ID: {result['id']})")
            return result
        
        return None


# =============================================================================
# PUBLISHER ORCHESTRATOR
# =============================================================================

class WordPressPublisher:
    """
    Main publisher orchestrator.
    
    Workflow:
    1. Load enriched data
    2. Check published log (skip duplicates)
    3. Generate content via Gemini AI
    4. Build HTML
    5. Upload to WordPress
    6. Update published log
    """
    
    def __init__(self, test_mode: bool = False):
        self.test_mode = test_mode
        self.gemini = GeminiContentGenerator()
        self.html_builder = HTMLContentBuilder(self.gemini)
        self.wp_client = WordPressClient()
        self.published_log = self._load_published_log()
        
        self.stats = {
            "processed": 0,
            "skipped": 0,
            "success": 0,
            "failed": 0
        }

    def _load_published_log(self) -> Dict[str, Any]:
        """Load or create published log."""
        if os.path.exists(PUBLISHED_LOG_FILE):
            try:
                with open(PUBLISHED_LOG_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Could not load published log: {e}")
        return {}

    def _save_published_log(self):
        """Save published log."""
        try:
            with open(PUBLISHED_LOG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.published_log, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Could not save published log: {e}")

    def _generate_title(self, church: Dict) -> str:
        """SEO 최적화된 제목 생성."""
        name = church.get("name", "")
        address = church.get("address", "")
        landmarks = church.get("nearby_landmarks", [])
        
        # Extract region from address
        region = ""
        if address:
            parts = address.split()
            for part in parts:
                if part.endswith(("시", "구", "군")):
                    region = part.replace("시", "").replace("구", "").replace("군", "")
                    break
        
        # Get closest landmark
        landmark_name = ""
        if landmarks:
            closest = min(landmarks, key=lambda x: x.get("distance", 9999))
            landmark_name = closest.get("name", "")
        
        if region and landmark_name:
            return f"[{region}] {name} 미사시간 정보 ({landmark_name} 근처)"
        elif region:
            return f"[{region}] {name} 미사시간 & 위치 안내"
        else:
            return f"{name} 미사시간 & 위치 안내"

    def _sleep_random(self):
        """Rate limiting delay."""
        time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))

    def publish_church(self, church: Dict) -> bool:
        """Publish single church to WordPress."""
        orgnum = church.get("orgnum", "")
        name = church.get("name", "Unknown")
        
        # Check if already published
        if orgnum in self.published_log:
            logger.info(f"[SKIP] {name} - 이미 발행됨 (ID: {self.published_log[orgnum].get('post_id')})")
            self.stats["skipped"] += 1
            return True
        
        logger.info(f"[PROCESSING] {name}...")
        
        try:
            # Generate content
            title = self._generate_title(church)
            content = self.html_builder.build_full_content(church)
            
            # Get or create tags
            seo_tags = church.get("seo_tags", [])
            tag_ids = []
            for tag in seo_tags[:10]:  # Max 10 tags
                tag_id = self.wp_client.get_or_create_tag(tag)
                if tag_id:
                    tag_ids.append(tag_id)
            
            # Upload featured image
            image_url = church.get("image_url", "")
            featured_media = 0
            if image_url:
                filename = f"church_{orgnum}.jpg"
                featured_media = self.wp_client.upload_image(image_url, filename) or 0
            
            if self.test_mode:
                logger.info(f"[TEST] Would publish: {title}")
                logger.debug(f"Content length: {len(content)} chars, Tags: {len(tag_ids)}")
                self.stats["success"] += 1
                return True
            
            # Create post
            self._sleep_random()  # Rate limiting
            result = self.wp_client.create_post(
                title=title,
                content=content,
                tags=tag_ids,
                featured_media=featured_media,
                status="draft"  # Always draft first
            )
            
            if result:
                # Update published log
                self.published_log[orgnum] = {
                    "name": name,
                    "post_id": result.get("id"),
                    "url": result.get("link"),
                    "published_at": datetime.now().isoformat()
                }
                self._save_published_log()
                
                logger.info(f"[SUCCESS] {name} 발행 완료 (ID: {result.get('id')})")
                self.stats["success"] += 1
                return True
            else:
                logger.error(f"[FAILED] {name} 발행 실패")
                self.stats["failed"] += 1
                return False
        
        except Exception as e:
            logger.error(f"[ERROR] {name}: {e}")
            self.stats["failed"] += 1
            return False

    def run(self, max_items: Optional[int] = None):
        """Main publishing loop."""
        logger.info("=" * 60)
        logger.info("🚀 WordPress Publisher Started")
        logger.info("=" * 60)
        
        # Load enriched data
        if not os.path.exists(ENRICHED_DATA_FILE):
            logger.error(f"Enriched data not found: {ENRICHED_DATA_FILE}")
            return
        
        with open(ENRICHED_DATA_FILE, "r", encoding="utf-8") as f:
            churches = json.load(f)
        
        # Filter candidates
        candidates = [
            c for c in churches
            if c.get("enrichment_status") == "completed"
        ]
        
        logger.info(f"Total churches: {len(churches)}, Candidates: {len(candidates)}")
        
        # Process
        for i, church in enumerate(candidates):
            if max_items and self.stats["processed"] >= max_items:
                logger.info(f"Max items ({max_items}) reached.")
                break
            
            self.publish_church(church)
            self.stats["processed"] += 1
        
        # Summary
        logger.info("=" * 60)
        logger.info("📊 Publishing Summary")
        logger.info(f"   Processed: {self.stats['processed']}")
        logger.info(f"   Success: {self.stats['success']}")
        logger.info(f"   Skipped: {self.stats['skipped']}")
        logger.info(f"   Failed: {self.stats['failed']}")
        logger.info("=" * 60)


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Peace-Greeting WordPress Auto Publisher",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    parser.add_argument(
        "--max-items", type=int, default=None,
        help="Maximum number of items to publish"
    )
    parser.add_argument(
        "--test", action="store_true",
        help="Test mode (no actual publishing)"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Enable debug logging"
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        publisher = WordPressPublisher(test_mode=args.test)
        publisher.run(max_items=args.max_items)
    
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Interrupted by user.")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
