#!/usr/bin/env python3
"""
혜택존 데이터 갱신 스크립트
- 행정안전부 공공서비스(혜택) API → subsidies.json
- 한국관광공사 TourAPI → festivals.json, upcoming.json
- 기업마당 지원사업 API → business.json
- meta.json (갱신 시각)
"""

import json
import os
import sys
import urllib.request
import urllib.parse
import datetime

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
# 1. 정부 지원금/혜택 (행정안전부 gov24 v3)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def get_subsidies():
    print("\n[1] 정부 지원금/혜택 수집 중...")
    all_items = []
    for page in range(1, 11):
        url = (
            f"https://api.odcloud.kr/api/gov24/v3/serviceList"
            f"?page={page}&perPage=100"
            f"&serviceKey={API_KEY_GOV}"
        )
        data = fetch_json(url)
        if not data or "data" not in data:
            print(f"  페이지 {page}: 데이터 없음, 중단")
            break
        items = data["data"]
        if not items:
            break
        all_items.extend(items)
        print(f"  페이지 {page}: {len(items)}건 수집")

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

    print(f"  총 {len(result)}건 정리 완료")
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
        print("  WARN: TourAPI 응답에 items가 없음")
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
    print("\n[2] 축제/행사 수집 중...")
    print("  → 진행중 축제 (오늘 기준)...")
    current = get_festivals(TODAY, num_of_rows=50)
    print(f"  진행중: {len(current)}건")

    future_date = (NOW + datetime.timedelta(days=7)).strftime("%Y%m%d")
    print(f"  → 다가오는 축제 ({future_date} 이후)...")
    upcoming = get_festivals(future_date, num_of_rows=30)
    print(f"  다가오는: {len(upcoming)}건")

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

    print("\n[3] 기업마당 사업자 지원사업 수집 중...")
    all_items = []

    # 분야별로 수집
    for field_code, field_name in BIZ_FIELDS.items():
        url = (
            f"https://www.bizinfo.go.kr/uss/rss/bizinfoApi.do"
            f"?crtfcKey={BIZ_KEY}"
            f"&dataType=json"
            f"&searchLclasId={field_code}"
            f"&pageUnit=20&pageIndex=1"
        )
        data = fetch_json(url)
        if not data:
            print(f"  {field_name}: 실패")
            continue

        try:
            items = data.get("jsonArray", [])
            if not items:
                items = data.get("items", [])
            if not items:
                # RSS 구조일 수 있음
                channel = data.get("channel", data.get("rss", {}).get("channel", {}))
                items = channel.get("item", [])
            if not isinstance(items, list):
                items = [items]
        except Exception:
            print(f"  {field_name}: 파싱 실패")
            continue

        count = 0
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
            count += 1

        print(f"  {field_name}: {count}건")

    print(f"  총 {len(all_items)}건 정리 완료")
    return all_items


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 메인 실행
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def main():
    print(f"===== 혜택존 데이터 갱신 시작 =====")
    print(f"시각: {NOW.strftime('%Y-%m-%d %H:%M:%S')} KST")
    print(f"오늘: {TODAY}")

    # 1. 지원금
    subsidies = get_subsidies()
    if subsidies:
        save_json("subsidies.json", subsidies)
    else:
        print("  WARN: 지원금 데이터 수집 실패 — 기존 파일 유지")

    # 2. 축제
    festivals, upcoming = collect_festivals()
    if festivals:
        save_json("festivals.json", festivals)
    else:
        print("  WARN: 축제 데이터 수집 실패 — 기존 파일 유지")

    if upcoming:
        save_json("upcoming.json", upcoming)
    else:
        print("  WARN: 다가오는 행사 수집 실패 — 기존 파일 유지")

    # 3. 사업자 지원
    business = get_business()
    if business:
        save_json("business.json", business)
    else:
        print("  WARN: 사업자 지원 수집 실패 — 기존 파일 유지")

    # 4. 메타 정보
    meta = {
        "updated_at": NOW.strftime("%Y-%m-%d %H:%M:%S"),
        "timezone": "KST",
        "subsidies_count": len(subsidies),
        "festivals_count": len(festivals),
        "upcoming_count": len(upcoming),
        "business_count": len(business) if business else 0,
    }
    save_json("meta.json", meta)

    print(f"\n===== 갱신 완료 =====")
    print(f"지원금: {len(subsidies)}건 | 축제: {len(festivals)}건 | 다가오는: {len(upcoming)}건 | 사업자: {len(business) if business else 0}건")


if __name__ == "__main__":
    main()
