#!/usr/bin/env python3
"""
혜택존 데이터 갱신 스크립트 (최종 통합 정제 버전)
- 행정안전부 공공서비스(혜택) API → subsidies.json (전체 동적 페이징 스캔 + 고정비/현금 필터)
- 한국관광공사 TourAPI → festivals.json, upcoming.json
- 기업마당 지원사업 API → business.json (소상공인 정책자금/고정비 필터)
- meta.json (갱신 시각 및 최종 필터링 카운트)
"""

import json
import os
import sys
import urllib.request
import urllib.parse
import datetime
import math

# ─── 환경변수에서 API 키 읽기 ───
API_KEY = os.environ.get("DATA_API_KEY", "").strip()
BIZ_KEY = os.environ.get("BIZ_API_KEY", "").strip()

if not API_KEY:
    print("ERROR: DATA_API_KEY 환경변수가 설정되지 않았습니다.")
    sys.exit(1)

if not BIZ_KEY:
    print("WARN: BIZ_API_KEY 없음 — 기업마당 데이터 건너뜀")

# gov24용 키 (Decoding 키 그대로)
API_KEY_GOV = API_KEY
# TourAPI용 키 (URL 인코딩)
API_KEY_TOUR = urllib.parse.quote(API_KEY, safe="")

# ─── 한국 시간 기준 ───
KST = datetime.timezone(datetime.timedelta(hours=9))
NOW = datetime.datetime.now(KST)
TODAY = NOW.strftime("%Y%m%d")

# ─── 출력 디렉토리 (레포 루트) ───
OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def fetch_json(url, timeout=30):
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "BenefitZone-Bot/1.0",
            "Accept": "application/json"
        })
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw)
    except Exception as e:
        print(f"  WARN: fetch 실패 → {e}")
        return None


def save_json(filename, data):
    path = os.path.join(OUT_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  저장: {filename} ({len(data) if isinstance(data, list) else 'obj'})")


# ─── 지역 추출 함수 ───
REGION_KEYWORDS = {
    "서울": ["서울"],
    "경기": ["경기"],
    "부산": ["부산"],
    "대구": ["대구"],
    "인천": ["인천"],
    "광주": ["광주광역"],
    "대전": ["대전"],
    "울산": ["울산"],
    "세종": ["세종"],
    "강원": ["강원"],
    "충북": ["충청북", "충북"],
    "충남": ["충청남", "충남"],
    "전북": ["전라북", "전북특별", "전북"],
    "전남": ["전라남", "전남"],
    "경북": ["경상북", "경북"],
    "경남": ["경상남", "경남"],
    "제주": ["제주"],
}

def extract_region(addr):
    if not addr:
        return "전국"
    for region, keywords in REGION_KEYWORDS.items():
        for kw in keywords:
            if kw in addr:
                return region
    return "전국"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# [핵심 매립] 전국민 / 소상공인 돈·고정비 혜택 필터링 엔진
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def filter_real_benefit_items(all_items):
    """
    어업, 선박, 단체보험, R&D 등 자영업자/일반 주민과 상관없는 대중성 없는 데이터는 원천 차단하고,
    소득수준이나 특정 계층(한부모, 특고, 소득하위)에 상관없이 무조건 돈(지원금), 이자감면, 국가대출,
    그리고 생활 고정비(전기세, 배달비, 임대료) 혜택만 정밀 타격하여 골라냅니다.
    """
    approved_queue = []
    
    # 1. 제목에 포함 시 무조건 패스시키는 무소통과 블랙리스트 키워드
    drop_keywords = [
        "어업", "선박", "감척", "원양", "해기사", "농업인", "전력기자재",
        "단체보험", "수출대금", "수출보험", "해외박람회", "바이어", "스마트공장", 
        "벤처인증", "특허", "기술개발", "R&D"
    ]
    
    # 2. 소상공인/지역민들이 즉각 체감할 수 있는 현금 및 비용 절감 골드 키워드
    pass_keywords = [
        # [고정비 및 공과금 절감]
        "전기세", "전기요금", "가스비", "에너지", "난방비", "냉방비", "공공요금",
        "배달비", "택배비", "임대료", "월세", "수수료", "카드수수료",
        
        # [금융, 이자, 정책 대출]
        "이자", "이차보전", "이자차액", "감면", "저금리", "무이자", "대환",
        "대출", "융자", "정책자금", "육성자금", "경영안정자금", "특례보증",
        
        # [직접 현금 및 수당성 자금]
        "지원금", "장려금", "근로장려금", "자녀장려금", "재난지원금", "민생지원금",
        "수당", "환급", "교통비", "지역사랑상품권", "지역화폐",
        
        # [생활 밀착 학비 지원]
        "학비", "장학금", "교육비", "교재비", "수업료"
    ]
    
    for item in all_items:
        # 지원금(name)과 사업자(title) 필드 범용 매칭
        title = item.get("name", item.get("title", ""))
        
        # 금지 단어가 하나라도 들어가 있다면 컷
        if any(drop_word in title for drop_word in drop_keywords):
            continue
            
        # 자격 조건 유무를 불문하고 진짜 돈을 주거나 깎아주는 핵심 조건 매칭 시 최종 승인
        is_real_benefit = any(pass_word in title for pass_word in pass_keywords)
        
        if is_real_benefit:
            approved_queue.append(item)
            
    return approved_queue


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 1. 정부 지원금/혜택 (행정안전부 gov24 v3 - 전체 페이지 동적 스캔형 개정)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def get_subsidies():
    print("\n[1] 정부 지원금/혜택 수집 중 (전체 누적 페이지 동적 스캔)...")
    
    # 시스템에 등록된 전체 데이터 건수를 확인하기 위한 선행 1페이지 호출
    init_url = f"https://api.odcloud.kr/api/gov24/v3/serviceList?page=1&perPage=1&serviceKey={API_KEY_GOV}"
    init_data = fetch_json(init_url)
    
    total_count = 1000
    if init_data and "totalCount" in init_data:
        total_count = init_data["totalCount"]
    
    per_page = 100
    total_pages = math.ceil(total_count / per_page)
    print(f"  → 탐색 대상 데이터: 총 {total_count}건 ({total_pages}개 페이지 동적 루프 실행)")

    all_items = []
    for page in range(1, total_pages + 1):
        url = f"https://api.odcloud.kr/api/gov24/v3/serviceList?page={page}&perPage={per_page}&serviceKey={API_KEY_GOV}"
        data = fetch_json(url)
        if not data or "data" not in data:
            print(f"  페이지 {page}: 데이터 덤프 실패, 스캔 중단")
            break
        items = data["data"]
        if not items:
            break
        all_items.extend(items)

    result = []
    for item in all_items:
        target = item.get("지원대상", "")
        region = extract_region(target)
        if region == "전국":
            region = extract_region(item.get("소관기관명", ""))
        result.append({
            "id": item.get("서비스ID", ""),
            "name": item.get("서비스명", ""),
            "desc": item.get("서비스목적요약", ""),
            "org": item.get("소관기관명", ""),
            "target": target,
            "how": item.get("신청방법", ""),
            "url": item.get("서비스상세URL", ""),
            "category": item.get("서비스분야", ""),
            "region": region,
        })

    print(f"  행안부 수집 완료: 원본 {len(result)}건 확보")
    return result


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 2. 축제/행사 (한국관광공사 TourAPI)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def get_festivals(event_start_date, num_of_rows=50):
    url = (
        f"https://apis.data.go.kr/B551011/KorService2/searchFestival2"
        f"?MobileOS=ETC&MobileApp=BenefitZone&_type=json"
        f"&numOfRows={num_of_rows}&pageNo=1"
        f"&eventStartDate={event_start_date}"
        f"&serviceKey={API_KEY_TOUR}"
    )
    data = fetch_json(url)
    if not data:
        return []
    try:
        items = data["response"]["body"]["items"]["item"]
        if not isinstance(items, list):
            items = [items]
    except (KeyError, TypeError):
        return []

    result = []
    for item in items:
        addr = item.get("addr1", "")
        result.append({
            "title": item.get("title", ""),
            "addr": addr,
            "image": item.get("firstimage", ""),
            "thumb": item.get("firstimage2", ""),
            "start": item.get("eventstartdate", ""),
            "end": item.get("eventenddate", ""),
            "tel": item.get("tel", ""),
            "contentid": item.get("contentid", ""),
            "areacode": item.get("areacode", ""),
            "mapx": item.get("mapx", ""),
            "mapy": item.get("mapy", ""),
            "region": extract_region(addr),
        })
    return result


def collect_festivals():
    print("\n[2] 축제/행사 데이터 패치 중...")
    current = get_festivals(TODAY, num_of_rows=50)
    future_date = (NOW + datetime.timedelta(days=7)).strftime("%Y%m%d")
    upcoming = get_festivals(future_date, num_of_rows=30)
    return current, upcoming


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 3. 기업마당 사업자 지원사업
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BIZ_FIELDS = {
    "01": "금융", "02": "기술", "03": "인력",
    "04": "수출", "05": "내수", "06": "창업",
    "07": "경영", "09": "기타"
}

def get_business():
    if not BIZ_KEY:
        print("\n[3] 기업마당 — API 키 없음, 건너뜀")
        return []

    print("\n[3] 기업마당 사업자 자금/공과금 공고 수집 중...")
    all_items = []

    for field_code, field_name in BIZ_FIELDS.items():
        # 대출자금, 이자 지원 공고가 밀집된 금융(01), 경영(07), 창업(06) 파트는 수집 단위를 50건으로 확장해 누락 원천 방어
        unit_size = 50 if field_code in ["01", "06", "07"] else 20
        
        url = (
            f"https://www.bizinfo.go.kr/uss/rss/bizinfoApi.do"
            f"?crtfcKey={BIZ_KEY}"
            f"&dataType=json"
            f"&searchLclasId={field_code}"
            f"&pageUnit={unit_size}&pageIndex=1"
        )
        data = fetch_json(url)
        if not data:
            continue

        try:
            items = data.get("jsonArray", data.get("items", []))
            if not items:
                channel = data.get("channel", data.get("rss", {}).get("channel", {}))
                items = channel.get("item", [])
            if not isinstance(items, list):
                items = [items]
        except Exception:
            continue

        for item in items:
            hashtags = item.get("hashTags", item.get("hashtags", ""))
            region = "전국"
            for r in REGION_KEYWORDS:
                if r in hashtags:
                    region = r
                    break

            all_items.append({
                "title": item.get("pblancNm", item.get("title", "")),
                "desc": item.get("bsnsSumryCn", item.get("description", "")),
                "org": item.get("jrsdInsttNm", item.get("author", "")),
                "exec_org": item.get("excInsttNm", ""),
                "field": field_name,
                "field_code": field_code,
                "target": item.get("trgetNm", ""),
                "url": item.get("pblancUrl", item.get("link", "")),
                "apply_date": item.get("reqstBeginEndDe", item.get("reqstDt", "")),
                "pub_date": item.get("creatPnttm", item.get("pubDate", "")),
                "hashtags": hashtags,
                "region": region,
            })

    print(f"  기업마당 수집 완료: 원본 {len(all_items)}건 확보")
    return all_items


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 메인 통합 제어 파이프라인
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def main():
    print(f"===== 혜택존 자동 데이터 정제 파이프라인 가동 =====")
    print(f"시각: {NOW.strftime('%Y-%m-%d %H:%M:%S')} KST | 기준일: {TODAY}")

    # 1. 정부 지원금 (전체 가져와서 현금/고정비 정밀 필터링 단행)
    raw_subsidies = get_subsidies()
    if raw_subsidies:
        subsidies = filter_real_benefit_items(raw_subsidies)
        save_json("subsidies.json", subsidies)
    else:
        subsidies = []
        print("  WARN: 지원금 데이터 수집 실패 — 기존 파일 보존")

    # 2. 축제/행사 파트 (규격 유지)
    festivals, upcoming = collect_festivals()
    if festivals:
        save_json("festivals.json", festivals)
    else:
        print("  WARN: 축제 데이터 수집 실패 — 기존 파일 보존")

    if upcoming:
        save_json("upcoming.json", upcoming)
    else:
        print("  WARN: 다가오는 행사 수집 실패 — 기존 파일 보존")

    # 3. 사업자 지원 (가져와서 정책 대출/이자 감면/고정비 특별 지원 필터링 단행)
    raw_business = get_business()
    if raw_business:
        business = filter_real_benefit_items(raw_business)
        save_json("business.json", business)
    else:
        business = []
        print("  WARN: 사업자 지원 수집 실패 — 기존 파일 보존")

    # 4. 메타 데이터 빌드 및 정제 카운트 동기화
    meta = {
        "updated_at": NOW.strftime("%Y-%m-%d %H:%M:%S"),
        "timezone": "KST",
        "subsidies_count": len(subsidies),
        "festivals_count": len(festivals),
        "upcoming_count": len(upcoming),
        "business_count": len(business),
    }
    save_json("meta.json", meta)

    print(f"\n===== 데이터 파이프라인 빌드 정상 완료 =====")
    print(f"최종 저장 내역 -> 지원금: {len(subsidies)}건 | 사업자: {len(business)}건 | 축제: {len(festivals)}건")


if __name__ == "__main__":
    main()
