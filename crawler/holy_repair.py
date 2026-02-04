"""
Holy-Repair Crawler
=====================
'발행글_재수집필요' 폴더에 있는 JSON 파일들을 로드하여,
각 교구 홈페이지에서 Playwright를 이용해 미사 시간을 직접 크롤링합니다.

[전략]
- 타겟 한정: 오직 '발행글_재수집필요/*.json' 파일만 읽음.
- 검색 기반: JSON 내 church_name으로 교구 사이트에서 검색/탐색.
"""

import asyncio
import json
import logging
import re
import argparse
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

from playwright.async_api import async_playwright, Page, BrowserContext

# =============================================================================
# CONFIGURATION
# =============================================================================

DIOCESE_CONFIG = {
    "군종교구": "https://www.gunjong.or.kr/main-parish/index.asp?ChurchMemberGrade=0",
    "안동교구": "https://www.acatholic.or.kr/sub3/sub3.asp",
    "대구대교구": "https://www.daegu-archdiocese.or.kr/page/area.html?srl=church_search",
    "전주교구": "https://www.jcatholic.or.kr/theme/main/pages/area.php",
    "제주교구": "https://www.diocesejeju.or.kr/church_main",
    "광주대교구": "https://www.gjcatholic.or.kr/church/mass",
    "서울대교구": "https://aos.catholic.or.kr/pro10314",
    "청주교구": "https://www.cdcj.or.kr/parish/parish",
    "대전교구": "https://www.djcatholic.or.kr/home/pages/church.php",
    "인천교구": "http://www.caincheon.or.kr",
    "수원교구": "https://www.casuwon.or.kr/parish/parish",
    "부산교구": "http://www.catholicbusan.or.kr/index.php?mid=page_ezLI10",
    "춘천교구": "https://www.cccatholic.or.kr/parish/missa",
    "원주교구": "http://wjcatholic.or.kr/parish/time?c=가나다순"
}

SCRIPT_DIR = Path(__file__).parent
INPUT_DIR = SCRIPT_DIR / '발행글_재수집필요'
OUTPUT_DIR = SCRIPT_DIR / '발행글'
LOG_FILE = SCRIPT_DIR / 'holy_repair.log'

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# =============================================================================
# LOGGING
# =============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("HolyRepair")

# =============================================================================
# UTILITY: 미사 시간 파싱 함수
# =============================================================================

def get_chosung(text):
    """한글 문자열의 첫 글자 초성을 반환"""
    if not text: return None
    char = text[0]
    code = ord(char) - 44032
    if code < 0 or code > 11171: return None
    
    # 초성 리스트 (19개)
    CHOSUNG = ['ㄱ', 'ㄲ', 'ㄴ', 'ㄷ', 'ㄸ', 'ㄹ', 'ㅁ', 'ㅂ', 'ㅃ', 'ㅅ', 'ㅆ', 'ㅇ', 'ㅈ', 'ㅉ', 'ㅊ', 'ㅋ', 'ㅌ', 'ㅍ', 'ㅎ']
    return CHOSUNG[code // 588]

def normalize_time(time_str, ampm):
    if not ampm: return time_str 
    try:
        hour, minute = map(int, time_str.split(':'))
        if ampm == "오후" and hour < 12:
            hour += 12
        elif ampm == "오전" and hour == 12:
            hour = 0
        return f"{hour:02d}:{minute:02d}"
    except:
        return time_str

def expand_days(day_expression):
    weekdays = ["월", "화", "수", "목", "금", "토", "일", "주일"]
    if "매일" in day_expression:
        return ["월", "화", "수", "목", "금", "토", "주일"]
    if '-' in day_expression:
        try:
            start, end = day_expression.split('-')
            if start == "일": start = "주일"
            if end == "일": end = "주일"
            s_idx = weekdays.index(start)
            e_idx = weekdays.index(end)
            return weekdays[s_idx:e_idx+1]
        except:
            return [day_expression] 
    return [day_expression]

def _parse_daegu_style(text: str) -> Dict[str, Any]:
    """대구대교구 스타일 파싱 (섹션, 오전/오후, 요일범위 지원)"""
    result = {
        "주일미사": [],
        "평일미사": [],
        "토요미사": [],
        "기타": [],
        "raw_text": text[:500]
    }
    
    current_section = "기타"
    
    # 텍스트 정규화: 줄바꿈 삽입
    # [주일미사], [평일미사] 앞에 줄바꿈
    normalized = text
    normalized = re.sub(r'\[주일미사\]', r'\n[주일미사]\n', normalized)
    normalized = re.sub(r'\[평일미사\]', r'\n[평일미사]\n', normalized)
    # "토요일 -", "주일 -" 앞에 줄바꿈
    normalized = re.sub(r'(토요일\s*-)', r'\n\1', normalized)
    normalized = re.sub(r'(주일\s*-)', r'\n\1', normalized)
    # "오전", "오후" 앞에 줄바꿈 (단, 시간 뒤에 오는 것은 제외 - 어려움)
    # 일단 skip
    
    lines = normalized.split('\n')
    for line in lines:
        line = line.strip()
        if not line: continue
        
        if "[주일미사]" in line:
            current_section = "주일미사"
            continue
        if "[평일미사]" in line:
            current_section = "평일미사"
            continue
            
        current_ampm = None 
        current_days = []
        
        token_pattern = re.compile(r'(오전|오후)|([월화수목금토일주일]-[월화수목금토일주일])|([월화수목금토일주일](?!요|은|는))|(\d{1,2}:\d{2})|(\([^)]+\))')
        
        clean_line = line.replace("토요일", "토").replace("일요일", "주일")
        matches = token_pattern.finditer(clean_line)
        
        last_added_entries = []
        
        for match in matches:
            ampm, day_range, day, time_str, desc = match.groups()
            
            if ampm:
                current_ampm = ampm
            elif day_range:
                current_days = expand_days(day_range)
            elif day:
                current_days = [day]
            elif time_str:
                final_time = normalize_time(time_str, current_ampm)
                days_to_apply = current_days
                if not days_to_apply:
                    if current_section == "주일미사": days_to_apply = ["주일"]
                    elif current_section == "토요미사": pass
                
                new_entries = []
                for d in days_to_apply:
                    category = current_section
                    if d == "토" and current_section == "주일미사":
                        category = "토요미사"
                    if category == "평일미사" and d == "주일":
                         category = "주일미사"

                    entry = {"시간": final_time, "설명": "", "요일": d}
                    result[category].append(entry)
                    new_entries.append(entry)
                last_added_entries = new_entries
                
            elif desc:
                clean_desc = desc.strip('()')
                if last_added_entries:
                    for entry in last_added_entries:
                        if entry["설명"]: entry["설명"] += " " + clean_desc
                        else: entry["설명"] = clean_desc

    # 결과 정리
    final_result = {"raw_text": text[:500]}
    
    # 필터링할 키워드 (특수 미사, 교리 등)
    filter_keywords = ["후원회", "교리", "교정사목"]
    
    for cat, entries in result.items():
        if cat == "raw_text": continue
        seen = set()
        clean_entries = []
        for e in entries:
            # 필터링: 특수 키워드 포함 시 스킵
            if any(kw in e['설명'] for kw in filter_keywords):
                continue
                
            if cat == "평일미사":
                if e['요일'] not in e['설명']:
                     e['설명'] = f"{e['요일']} {e['설명']}".strip()
            
            key = f"{e['시간']}|{e['설명']}"
            if key not in seen:
                seen.add(key)
                if '요일' in e: del e['요일']
                clean_entries.append(e)
        
        if clean_entries:
            final_result[cat] = clean_entries

    return final_result

def parse_mass_times_from_text(text: str) -> Dict[str, Any]:
    """
    텍스트에서 미사 시간 정보를 추출.
    지원 패턴:
    1. 대구형 (섹션, 오전/오후, 범위)
    2. 서울형/수원형 (HH:MM)
    """
    # 대구형 패턴 체크
    if "[주일미사]" in text or "[평일미사]" in text:
        return _parse_daegu_style(text)
        
    # 기존 로직 (서울/수원)
    result = {
        "주일미사": [],
        "평일미사": [],
        "토요미사": [],
        "기타": [],
        "raw_text": text[:500]
    }
    
    # 패턴 1: 시간 + (설명)
    pattern1 = r'(\d{1,2}:\d{2})\s*\(([^)]+)\)'
    matches1 = re.findall(pattern1, text)
    
    for time_str, desc in matches1:
        entry = {"시간": time_str, "설명": desc}
        _classify_mass(result, entry, desc)
            
    # 패턴 2: 요일 + 시간들 (수원형)
    days = ["월", "화", "수", "목", "금", "토", "주일", "일"]
    lines = text.split('\n')
    for line in lines:
        line = line.strip()
        if not line: continue
        
        if any(line.startswith(d) for d in days) or any(line.startswith(f"{d}요일") for d in days):
            # 대구형인지 한번 더 체크? 아니오, 위에서 걸렀음.
            times = re.findall(r'(\d{1,2}:\d{2})', line)
            if times:
                # 요일 찾기
                day_found = ""
                for d in days:
                    if line.startswith(d):
                        day_found = d
                        break
                
                for t in times:
                    desc = f"{day_found}요일 {t} 미사"
                    entry = {"시간": t, "설명": desc}
                    _classify_mass(result, entry, day_found)

    # 중복 제거
    for cat in result:
        if isinstance(result[cat], list):
            unique = []
            seen = set()
            for item in result[cat]:
                key = f"{item['시간']}|{item['설명']}"
                if key not in seen:
                    seen.add(key)
                    unique.append(item)
            result[cat] = unique

    result = {k: v for k, v in result.items() if v}
    return result if len(result) > 1 else None

def _classify_mass(result_dict, entry, keyword_source):
    """미사 분류 헬퍼"""
    k = keyword_source.lower()
    if any(w in k for w in ["주일", "일요일", "교중", "청년", "청소년"]):
        result_dict["주일미사"].append(entry)
    elif any(w in k for w in ["토요", "토", "특전"]):
        result_dict["토요미사"].append(entry)
    elif any(w in k for w in ["평일", "월", "화", "수", "목", "금"]):
        result_dict["평일미사"].append(entry)
    else:
        result_dict["기타"].append(entry)

# =============================================================================
# CRAWLER CLASS
# =============================================================================

class RepairCrawler:
    def __init__(self, headless: bool = False):
        self.headless = headless
        self.browser = None
        self.context: BrowserContext = None
        self.playwright = None
        self.stats = {"total": 0, "success": 0, "failed": 0}

    async def start(self):
        """Playwright 시작"""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=self.headless)
        self.context = await self.browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        logger.info("🚀 Holy-Repair Crawler Started")

    async def stop(self):
        """Playwright 종료"""
        if self.context: await self.context.close()
        if self.browser: await self.browser.close()
        if self.playwright: await self.playwright.stop()
        logger.info(f"👋 Holy-Repair Crawler Stopped | Stats: {self.stats}")

    # =========================================================================
    # 파일 처리 (Targeted Repair - 핵심 로직 검증됨)
    # =========================================================================
    
    async def process_files(self, limit: int = None):
        """
        [핵심] 오직 '발행글_재수집필요' 폴더의 JSON만 읽어서 처리.
        전체 성당을 긁는 것이 아니라, JSON에 명시된 성당만 타겟팅.
        """
        # failed_ 파일 우선 처리 (이전에 실패한 것들)
        files = list(INPUT_DIR.glob('failed_posts_batch_*.json'))
        files += list(INPUT_DIR.glob('posts_batch_*.json'))
        
        if not files:
            logger.warning(f"⚠️ No files found in {INPUT_DIR}")
            return
            
        logger.info(f"📂 Found {len(files)} target files in '발행글_재수집필요'")

        for file_path in files:
            await self.process_single_file(file_path, limit=limit)

    async def process_single_file(self, file_path: Path, limit: int = None):
        logger.info(f"📄 Processing: {file_path.name}")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                posts = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load {file_path}: {e}")
            return

        repaired_posts = []
        failed_posts = []
        
        posts_to_process = posts[:limit] if limit else posts
        
        for idx, post in enumerate(posts_to_process):
            # church_name에서 "성당" 제거
            church_name = post.get('church_name', '').replace("성당", "").strip()
            
            # 교구 정보가 없으면 주소에서 추론
            diocese = post.get('diocese', '')
            if not diocese:
                address = post.get('address', '')
                diocese = self.infer_diocese(address)
            
            if not church_name or not diocese:
                # logger.debug(f"Skipping invalid entry: {church_name} (Addr: {post.get('address')})")
                continue
            
            # 교구별 핸들러 선택
            handler = self.get_handler(diocese)
            if not handler:
                # logger.debug(f"No handler for: {diocese}")
                failed_posts.append(post)
                continue

            self.stats["total"] += 1
            logger.info(f"[{idx+1}/{len(posts_to_process)}] 🔍 {diocese} - {church_name}")
            
            try:
                page = await self.context.new_page()
                result_data = await handler(page, church_name, post)
                await page.close()
                
                if result_data and len(result_data) > 1:  # 유효한 데이터
                    logger.info(f"  ✅ SUCCESS: {church_name}")
                    post['repaired_mass_times'] = result_data
                    post['repair_source'] = 'holy_repair_crawler'
                    post['repair_timestamp'] = datetime.now().isoformat()
                    repaired_posts.append(post)
                    self.stats["success"] += 1
                else:
                    logger.info(f"  ❌ FAILED: {church_name}")
                    failed_posts.append(post)
                    self.stats["failed"] += 1
                    
            except Exception as e:
                logger.error(f"  ❌ ERROR: {church_name} - {e}")
                failed_posts.append(post)
                self.stats["failed"] += 1
        
        # 결과 저장
        if repaired_posts:
            out_path = OUTPUT_DIR / f"repaired_{file_path.name}"
            with open(out_path, 'w', encoding='utf-8') as f:
                json.dump(repaired_posts, f, ensure_ascii=False, indent=2)
            logger.info(f"💾 Saved {len(repaired_posts)} repaired items -> {out_path.name}")

    def infer_diocese(self, address: str) -> str:
        """주소를 기반으로 교구를 추론"""
        if not address: return ""
        
        if "서울" in address: return "서울대교구"
        if "대구" in address: return "대구대교구"
        if "광주" in address: return "광주대교구"
        if "제주" in address: return "제주교구"
        if "대전" in address or "세종" in address or "충남" in address or "충청남도" in address: return "대전교구"
        if "부산" in address: return "부산교구"
        if "인천" in address: return "인천교구" # 부천/김포 등은 별도 로직 필요할 수 있음
        if "전북" in address or "전라북도" in address: return "전주교구"
        if "충북" in address or "충청북도" in address: return "청주교구"
        if "강원" in address or "강원도" in address:
            # 춘천/원주 구분 어렵지만 일단 춘천으로 매핑하거나 둘 다 시도?
            # 원주시가 포함되면 원주교구
            if "원주" in address: return "원주교구"
            return "춘천교구"
            
        # 경기 지역은 복잡함 (수원/인천/의정부)
        if "경기" in address:
            if any(c in address for c in ["수원", "성남", "용인", "안양", "안산", "화성", "평택"]): return "수원교구"
            if any(c in address for c in ["고양", "의정부", "파주", "남양주", "구리"]): return "의정부교구" # 설정에 없으면 무시됨
            if any(c in address for c in ["부천", "김포"]): return "인천교구"
            return "수원교구" # 기본값

        return ""

    def get_handler(self, diocese: str):
        """교구명 -> 핸들러 함수 매핑"""
        normalized = diocese.replace("천주교", "").replace(" ", "").strip()
        
        if "서울" in normalized: return self.handle_seoul
        if "대구" in normalized: return self.handle_daegu
        if "수원" in normalized: return self.handle_suwon
        if "인천" in normalized: return self.handle_incheon
        if "부산" in normalized: return self.handle_busan
        
        return None

    # =========================================================================
    # HANDLERS (교구별 상세 구현)
    # =========================================================================

    async def handle_seoul(self, page: Page, church_name: str, post: dict) -> Optional[Dict]:
        """
        서울대교구 핸들러
        
        [페이지 구조 분석 결과 - 업데이트됨]
        - URL: https://aos.catholic.or.kr/pro10314
        - 검색창: input#srchText (class="inp")
        - 검색 버튼: 엔터키 또는 버튼 클릭
        - 결과: 해당 성당의 미사 시간이 리스트로 표시
        """
        base_url = DIOCESE_CONFIG["서울대교구"]
        
        try:
            logger.info(f"  🌐 Opening Seoul diocese page...")
            await page.goto(base_url, timeout=15000)
            await page.wait_for_load_state("networkidle")
            
            # 검색창 찾기
            search_input = page.locator("#srchText")
            if await search_input.count() == 0:
                search_input = page.locator("input.inp")
            
            if await search_input.count() == 0:
                logger.warning("  ⚠️ Search input not found!")
                return None
            
            logger.info(f"  🔍 Searching for '{church_name}'...")
            await search_input.first.fill(church_name)
            await page.keyboard.press("Enter")
            
            # 결과 로딩 대기
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(1)  # 추가 대기 (동적 콘텐츠)
            
            # 결과 페이지 텍스트 가져오기
            text_content = await page.inner_text("body")
            logger.info(f"  📝 Result text length: {len(text_content)} chars")
            
            # 검색 결과에서 성당명 확인
            if church_name not in text_content and "검색결과" not in text_content:
                # 혹시 다른 방식으로 표시되는지 체크
                logger.info(f"  ⚠️ '{church_name}' 검색 결과 없음. 페이지 내용 샘플:")
                logger.info(f"  {text_content[:300]}...")
                return None
            
            logger.info(f"  ✅ Found results for '{church_name}'")
            
            # 미사 시간 추출
            # 패턴: "HH:MM (설명)" 
            result = parse_mass_times_from_text(text_content)
            
            if result:
                result["search_term"] = church_name
                return result
            
            # Fallback: 전체 텍스트라도 저장
            return {
                "raw_text": text_content[:1000],
                "search_term": church_name,
                "parsing_failed": True
            }
            
        except Exception as e:
            logger.error(f"  ❌ Seoul handler error: {e}")
            return None

    async def handle_suwon(self, page: Page, church_name: str, post: dict) -> Optional[Dict]:
        """수원교구 핸들러"""
        url = DIOCESE_CONFIG["수원교구"]
        
        try:
            logger.info(f"  🌐 Opening Suwon diocese page...")
            await page.goto(url, timeout=20000)
            await page.wait_for_load_state("domcontentloaded")
            
            # 검색창 찾기 (좀 더 유연하게)
            search_input = page.locator("input[name='k']")
            if await search_input.count() == 0:
                search_input = page.locator("input#k")
            
            # 검색창이 안 보일 수도 있으니 스크롤
            await page.evaluate("window.scrollTo(0, 0)")
            
            if await search_input.count() > 0:
                logger.info(f"  🔍 Searching for '{church_name}'...")
                await search_input.first.fill(church_name)
                
                # 엔터키 이벤트 또는 검색 버튼 클릭
                # 검색 버튼: .btn_search 또는 form submit
                if await page.locator("button.btn_search").count() > 0:
                    await page.locator("button.btn_search").click()
                elif await page.locator("input[type='submit']").count() > 0:
                     await page.locator("input[type='submit']").click()
                else:
                    await page.keyboard.press("Enter")
                
                await page.wait_for_load_state("networkidle")
                
                # 결과 리스트 확인
                logger.info("  👀 Checking results...")
                
                # 결과 테이블 존재 확인
                if await page.locator("table").count() == 0:
                    logger.warning("  ⚠️ Result table not found.")
                    return None
                
                # 명시적으로 링크 대기 (3초)
                try:
                    await page.wait_for_selector("table tbody tr a", timeout=3000)
                except:
                    pass
                
                # 모든 tr을 순회하며 찾기
                rows = await page.locator("table tbody tr").all()
                logger.info(f"  Found {len(rows)} rows in result table.")
                
                for row in rows:
                    text = await row.inner_text()
                    if church_name in text:
                        logger.info(f"  ✅ Found '{church_name}' in row. Clicking...")
                        link = row.locator("a")
                        if await link.count() > 0:
                            # 새 탭으로 열릴 수도 있으니 context 감시? 
                            # 보통은 같은 창 이동
                            await link.first.click()
                            await page.wait_for_load_state("domcontentloaded")
                            await asyncio.sleep(1) 
                            
                            # 상세 페이지 파싱
                            content = await page.inner_text("body")
                            logger.info(f"  📝 Content excerpt: {content[:500].replace(chr(10), ' ')}") # 디버깅용
                            
                            result = parse_mass_times_from_text(content)
                            if result:
                                result["search_term"] = church_name
                                return result
                        else:
                            logger.warning("  ⚠️ Found row but no link anchor.")
            else:
                logger.error("  ❌ Search input not found. Dump inputs:")
                inputs = await page.locator("input").all()
                for inp in inputs:
                    name = await inp.get_attribute("name")
                    logger.info(f"    - input name={name}")
            
        except Exception as e:
            logger.error(f"  ❌ Suwon handler error: {e}")
            
        return None

    async def handle_daegu(self, page: Page, church_name: str, post: dict) -> Optional[Dict]:
        """대구대교구 핸들러"""
        url = DIOCESE_CONFIG["대구대교구"]
        
        try:
            logger.info(f"  🌐 Opening Daegu diocese page...")
            await page.goto(url, timeout=15000)
            await page.wait_for_load_state("domcontentloaded")
            
            # 검색창 찾기: id='search', name='search', class='church_search_input'
            search_input = page.locator("input#search")
            if await search_input.count() == 0:
                search_input = page.locator("input.church_search_input")
            if await search_input.count() == 0:
                search_input = page.locator("input[name='search']")
                
            if await search_input.count() > 0:
                # 대구교구 검색어 튜닝: "주교좌" 제거 (예: 계산주교좌 -> 계산)
                search_term = church_name.replace("주교좌", "").strip()
                logger.info(f"  🔍 Searching for '{search_term}' (Original: {church_name})...")
                
                await search_input.first.fill(search_term)
                
                # 검색 버튼 클릭 (엔터가 안 먹힐 수도 있어서 버튼 클릭 시도)
                # 대구교구 버튼: input.btn_search 또는 img.btn_search 등
                # 일단 엔터 먼저
                await page.keyboard.press("Enter")
                await page.wait_for_load_state("networkidle")
                await asyncio.sleep(2) # 결과 로딩 대기
                
                # 결과 파싱
                logger.info("  👀 Checking results...")
                
                # 결과가 리스트 형태로 나옴. 클릭해야 함.
                # "검색결과 : 전체 N건" 확인 - 없으면 실패
                content = await page.inner_text("body")
                if "검색결과 : 전체 0건" in content:
                    logger.warning(f"  ⚠️ No results found for '{search_term}'")
                    return None

                # 첫 번째 결과 클릭 (class="result_tit" 또는 table 내 링크)
                # 대구교구 구조 추정: 게시판 형태 리스트
                # 링크 찾기: search_term을 포함하는 a 태그
                
                # 좀 더 명시적인 링크를 찾기 위해 wait
                try:
                    # 성당명(튜닝된)이 포함된 링크 대기
                    await page.wait_for_selector(f"a:has-text('{search_term}')", timeout=3000)
                except:
                    pass

                # 링크 클릭 시도
                links = await page.locator("a").all()
                found_link = False
                
                for link in links:
                    txt = await link.inner_text()
                    if search_term in txt and len(txt) < 20: # 너무 긴 텍스트 제외
                        logger.info(f"  ✅ Found link '{txt}'. Clicking...")
                        try:
                            await link.click()
                            await page.wait_for_load_state("domcontentloaded")
                            await asyncio.sleep(1)
                            found_link = True
                            break
                        except Exception as e:
                            logger.warning(f"  ⚠️ Failed to click link: {e}")
                
                if not found_link:
                    logger.warning("  ⚠️ Found results but could not locate click target.")
                    return None
                    
                # 상세 페이지 파싱
                content = await page.inner_text("body")
                logger.info(f"  📝 Content excerpt: {content[:1500].replace(chr(10), ' ')}")
                
                result = parse_mass_times_from_text(content)
                if result:
                    result["search_term"] = search_term
                    return result
                else:
                    logger.warning("  ⚠️ Parsed result is empty. Detailed parsing might be needed.")
            else:
                logger.error("  ❌ Search input not found.")
                # 디버그: 인풋 다 출력
                inputs = await page.locator("input").all()
                for inp in inputs:
                    logger.info(f"    - input: {await inp.evaluate('el => el.outerHTML')}")

        except Exception as e:
            logger.error(f"  ❌ Daegu handler error: {e}")
            
        return None

    async def handle_incheon(self, page: Page, church_name: str, post: dict) -> Optional[Dict]:
        """
        인천교구 핸들러
        
        [페이지 구조]
        - 목록: http://www.caincheon.or.kr/church/church_misa.do
        - 상세: http://www.caincheon.or.kr/church/church_jigu.do?churchIdx=...
        - 검색창이 없고, 목록에서 클릭해서 들어가야 함.
        - 미사시간 표기: 텍스트 ("월 오전 6시 30분")
        """
        list_url = DIOCESE_CONFIG["인천교구"] + "/church/church_misa.do" # config url 보정 필요할 수도
        if not list_url.startswith("http"): # DIOCESE_CONFIG["인천교구"]가 base url일 경우
             list_url = "http://www.caincheon.or.kr/church/church_misa.do"

        try:
            logger.info(f"  🌐 Opening Incheon diocese list page...")
            await page.goto(list_url, timeout=20000)
            await page.wait_for_load_state("domcontentloaded")
            
            # 성당명으로 링크 찾기
            # 인천교구 목록에는 "가정3동", "가정동" 처럼 "성당"이 빠진 이름으로 되어 있음.
            # 입력된 church_name에서 "성당"을 뺀 이름으로 검색
            target_name = church_name.replace("성당", "").strip()
            
            logger.info(f"  🔍 Finding link for '{target_name}'...")
            
            # 모든 링크 텍스트 확인
            found_link = None
            links = await page.locator(".con_area a").all() # .con_area 내의 링크로 한정
            
            if not links:
                 links = await page.locator("a").all() # 실패시 전체 검색

            for link in links:
                txt = await link.inner_text()
                txt = txt.strip()
                if txt == target_name: # 정확히 일치하는 것 우선
                    found_link = link
                    break
            
            if not found_link:
                # 포함되는 것 재검색 (예: "가정3동" -> "가정3동(준)" 같은 케이스 대비)
                for link in links:
                    txt = await link.inner_text()
                    txt = txt.strip()
                    if target_name in txt and len(txt) < len(target_name) + 5:
                        found_link = link
                        break
            
            if found_link:
                logger.info(f"  ✅ Found link: {await found_link.inner_text()} -> Clicking...")
                await found_link.click()
                
                # 상세 페이지 로딩 대기
                try:
                    # "미사안내" 또는 "성당정보" 가 나올 때까지 대기
                    await page.wait_for_load_state("networkidle")
                    # h4 태그 등을 기다림
                    await asyncio.sleep(2) 
                except:
                    pass
                
                # 상세 페이지 파싱
                body_text = await page.inner_text("body")
                # print(f"DEBUG_BODY_LEN: {len(body_text)}") # 디버깅
                
                # "미사안내" 텍스트 확인
                if "미사안내" in body_text:
                    # 미사안내 섹션 추출
                    split_text = body_text.split("미사안내")
                    if len(split_text) > 1:
                        target_text = split_text[1]
                        
                        # "비고" 또는 다음 섹션 전까지
                        for terminator in ["비고", "본당 소식", "수도회", "관할구역"]:
                            if terminator in target_text:
                                target_text = target_text.split(terminator)[0]
                        
                        logger.info(f"  📝 Mass info excerpt: {target_text[:200].replace(chr(10), ' ')}")
                        
                        result = parse_mass_times_from_text(target_text)
                        if result:
                            result["search_term"] = church_name
                            return result
                        else:
                            logger.warning(f"  ⚠️ Parsing failed. Text was: {target_text[:100]}")
                else:
                    logger.warning("  ⚠️ '미사안내' text not found in body.")
                    # print(f"DEBUG_BODY: {body_text[:500]}") # 디버깅

                return {
                    "raw_text": body_text[:1000],
                    "search_term": church_name
                }

            else:
                logger.warning(f"  ⚠️ Link for '{target_name}' not found.")
                return None
                
        except Exception as e:
            logger.error(f"  ❌ Incheon handler error: {e}")
            return None

    async def handle_busan(self, page: Page, church_name: str, post: dict) -> Optional[Dict]:
        """부산교구 핸들러 (AJAX 탭 방식 - DOM 구조 기반)"""
        url = DIOCESE_CONFIG["부산교구"] # http://www.catholicbusan.or.kr/index.php?mid=page_ezLI10
        
        try:
            logger.info(f"  🌐 Opening Busan diocese page...")
            await page.goto(url, timeout=20000)
            await page.wait_for_load_state("domcontentloaded")
            
            # 1. 가나다순 탭 클릭
            ganada_tab = page.locator("#ganadaTab")
            if await ganada_tab.count() > 0:
                logger.info("  Clicking '#ganadaTab'...")
                await ganada_tab.click()
                await asyncio.sleep(0.5)
            else:
                logger.error("  ❌ '#ganadaTab' not found.")
                return None
            
            # 2. 초성 탭 클릭
            target_name = church_name.replace("성당", "").strip()
            chosung = get_chosung(target_name) # 'ㄱ', 'ㄴ', ...
            
            # 부산교구 매핑 (14개)
            mapping = {
                'ㄱ': 0, 'ㄲ': 0,
                'ㄴ': 1,
                'ㄷ': 2, 'ㄸ': 2,
                'ㄹ': 3,
                'ㅁ': 4,
                'ㅂ': 5, 'ㅃ': 5,
                'ㅅ': 6, 'ㅆ': 6,
                'ㅇ': 7,
                'ㅈ': 8, 'ㅉ': 8,
                'ㅊ': 9,
                'ㅋ': 10,
                'ㅌ': 11,
                'ㅍ': 12,
                'ㅎ': 13
            }
            
            idx = mapping.get(chosung)
            logger.info(f"  Church={target_name}, Chosung={chosung}, Index={idx}")
            
            if idx is None:
                logger.warning(f"  ⚠️ Unknown chosung '{chosung}' for '{target_name}'")
                return None
            
            # <div class="word" value="idx">...</div>
            tab_btn = page.locator(f"#ganadaOrder .word[value='{idx}']")
            
            if await tab_btn.count() > 0:
                logger.info(f"  Clicking chosung tab '{chosung}' (value={idx})...")
                await tab_btn.click()
                # 탭 클릭 후 리스트 로딩 대기 
                # (wait_for_selector가 알아서 기다리겠지만 혹시 모르니)
                await asyncio.sleep(0.5)
            else:
                logger.warning(f"  ⚠️ Chosung tab element not found for value='{idx}'")
                return None # 탭 못 누르면 진행 불가

            # 3. 성당 목록 스캔 (wait_for_selector 사용)
            logger.info(f"  🔍 Waiting for church '{target_name}' to appear...")
            
            # 정확한 성당 이름을 가진 요소가 나타날 때까지 대기
            selector = f"#catholicChurch .bondang:has-text('{target_name}')"
            logger.info(f"  Waiting for selector: {selector}")
            
            try:
                # 5초간 대기
                target_el = await page.wait_for_selector(selector, state="visible", timeout=5000)
                
                if target_el:
                    logger.info("  ✅ Found church element -> Clicking...")
                    await target_el.click()
                    
                    # 4. 미사 정보 로딩 대기
                    await asyncio.sleep(1.5)
                    
                    misa_content = page.locator("#misaContent")
                    if await misa_content.count() > 0:
                        content = await misa_content.inner_text()
                        logger.debug(f"  Misa Content Len={len(content)}")
                        logger.debug(f"  Misa Content Start={content[:50]}")
                        
                        logger.info(f"  📝 Content excerpt: {content[:200].replace(chr(10), ' ')}")
                        
                        result = parse_mass_times_from_text(content)
                        if result:
                            result["search_term"] = church_name
                            return result
                        else:
                            logger.warning(f"  ⚠️ Parsing failed. Text was: {content[:100]}")
                    else:
                        logger.warning("  ⚠️ '#misaContent' is not visible or empty.")
                else:
                    logger.warning(f"  ⚠️ Church '{target_name}' not found (wait returned None).")
            
            except Exception as wait_err:
                logger.warning(f"  ⚠️ Timeout waiting for '{target_name}': {wait_err}")
                
                # 디버깅: 현재 있는 모든 본당 출력
                els = await page.locator("#catholicChurch .bondang").all()
                names = [await el.inner_text() for el in els]
                logger.debug(f"  Current list: {names[:10]}...")
                
        except Exception as e:
            logger.error(f"  ❌ Busan handler error: {e}")
            
        return None

# =============================================================================
# MAIN
# =============================================================================

async def main():
    parser = argparse.ArgumentParser(description="Holy-Repair Crawler")
    parser.add_argument("--test", type=str, help="테스트할 성당명 (단일 테스트)")
    parser.add_argument("--diocese", type=str, default="서울대교구", help="테스트할 교구명")
    parser.add_argument("--limit", type=int, help="처리할 성당 수 제한")
    parser.add_argument("--headless", action="store_true", help="헤드리스 모드 (브라우저 숨김)")
    args = parser.parse_args()

    crawler = RepairCrawler(headless=args.headless)
    await crawler.start()
    
    try:
        if args.test:
            # 단일 성당 테스트 모드
            logger.info(f"🧪 TEST MODE: {args.test} ({args.diocese})")
            handler = crawler.get_handler(args.diocese)
            
            if handler:
                page = await crawler.context.new_page()
                mock_post = {"church_name": args.test, "diocese": args.diocese}
                
                try:
                    result = await handler(page, args.test, mock_post)
                    print("\n" + "="*50)
                    print("📋 RESULT:")
                    print("="*50)
                    print(json.dumps(result, ensure_ascii=False, indent=2))
                    print("="*50 + "\n")
                except Exception as e:
                    logger.error(f"🧪 Test failed: {e}")
                finally:
                    await asyncio.sleep(3)  # 결과 확인용 대기
            else:
                logger.error(f"❌ No handler for: {args.diocese}")
        else:
            # 전체 파일 처리 모드
            await crawler.process_files(limit=args.limit)
            
    finally:
        await crawler.stop()

if __name__ == "__main__":
    asyncio.run(main())
