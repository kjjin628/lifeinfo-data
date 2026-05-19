#!/usr/bin/env python3
"""
공공정보 블로그 데이터 갱신 스크립트
- 행정안전부 공공서비스(혜택) API → subsidies.json
- 한국관광공사 TourAPI → festivals.json, upcoming.json
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
if not API_KEY:
    print("ERROR: DATA_API_KEY 환경변수가 설정되지 않았습니다.")
    sys.exit(1)

# gov24 (odcloud)는 Decoding 키 그대로 사용
API_KEY_GOV = API_KEY

# TourAPI (apis.data.go.kr)는 URL 인코딩해서 사용
API_KEY_TOUR = urllib.parse.quote(API_KEY, safe="")

# URL 파라미터에 넣을 때는 Decoding 키를 인코딩해서 사용
API_KEY_ENCODED = API_KEY

# ─── 한국 시간 기준 ───
KST = datetime.timezone(datetime.timedelta(hours=9))
NOW = datetime.datetime.now(KST)
TODAY = NOW.strftime("%Y%m%d")

# ─── 출력 디렉토리 (레포 루트) ───
OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def fetch_json(url, timeout=30):
    """URL에서 JSON을 가져온다. 실패 시 None 반환."""
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "LifeInfo-Bot/1.0",
            "Accept": "application/json"
        })
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw)
    except Exception as e:
        print(f"  WARN: fetch 실패 → {e}")
        print(f"  URL: {url[:120]}...")
        return None


def save_json(filename, data):
    """JSON 파일을 레포 루트에 저장."""
    path = os.path.join(OUT_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  저장: {filename} ({len(data) if isinstance(data, list) else 'obj'})")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 1. 정부 지원금/혜택 (행정안전부 gov24 v3)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def get_subsidies():
    """공공서비스(혜택) 목록을 가져와 정리한다."""
    print("\n[1] 정부 지원금/혜택 수집 중...")

    all_items = []

    # 여러 페이지 수집 (최대 5페이지 = 100건)
    for page in range(1, 6):
        url = (
            f"https://api.odcloud.kr/api/gov24/v3/serviceList"
            f"?page={page}&perPage=20"
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

    # 정리
    result = []
    for item in all_items:
        result.append({
            "id": item.get("서비스ID", ""),
            "name": item.get("서비스명", ""),
            "desc": item.get("서비스목적요약", ""),
            "org": item.get("소관기관명", ""),
            "target": item.get("지원대상", ""),
            "how": item.get("신청방법", ""),
            "url": item.get("서비스상세URL", ""),
            "category": item.get("서비스분야", ""),
        })

    print(f"  총 {len(result)}건 정리 완료")
    return result


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 2. 축제/행사 (한국관광공사 TourAPI)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def get_festivals(event_start_date, num_of_rows=30):
    """TourAPI에서 축제/행사 정보를 가져온다."""
    url = (
        f"https://apis.data.go.kr/B551011/KorService1/searchFestival1"
        f"?MobileOS=ETC&MobileApp=LifeInfo&_type=json"
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
            items = [items]  # 단일 결과일 때 dict로 오는 경우
    except (KeyError, TypeError):
        print("  WARN: TourAPI 응답에 items가 없음 (결과 0건일 수 있음)")
        return []

    result = []
    for item in items:
        result.append({
            "title": item.get("title", ""),
            "addr": item.get("addr1", ""),
            "image": item.get("firstimage", ""),
            "thumb": item.get("firstimage2", ""),
            "start": item.get("eventstartdate", ""),
            "end": item.get("eventenddate", ""),
            "tel": item.get("tel", ""),
            "contentid": item.get("contentid", ""),
            "areacode": item.get("areacode", ""),
            "mapx": item.get("mapx", ""),
            "mapy": item.get("mapy", ""),
        })

    return result


def collect_festivals():
    """진행중 축제 + 다가오는 축제를 분리 수집."""
    print("\n[2] 축제/행사 수집 중...")

    # 오늘 기준 진행중인 축제
    print("  → 진행중 축제 (오늘 기준)...")
    current = get_festivals(TODAY, num_of_rows=30)
    print(f"  진행중: {len(current)}건")

    # 30일 후 시작하는 축제 (다가오는 행사)
    future_date = (NOW + datetime.timedelta(days=7)).strftime("%Y%m%d")
    print(f"  → 다가오는 축제 ({future_date} 이후)...")
    upcoming = get_festivals(future_date, num_of_rows=20)
    print(f"  다가오는: {len(upcoming)}건")

    return current, upcoming


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 3. 지역별 요약 생성
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
AREA_CODES = {
    "1": "서울", "2": "인천", "3": "대전", "4": "대구",
    "5": "광주", "6": "부산", "7": "울산", "8": "세종",
    "31": "경기", "32": "강원", "33": "충북", "34": "충남",
    "35": "경북", "36": "경남", "37": "전북", "38": "전남", "39": "제주"
}


def build_regions(festivals):
    """축제 목록에서 지역별 요약을 생성."""
    print("\n[3] 지역별 요약 생성 중...")
    regions = {}
    for f in festivals:
        code = f.get("areacode", "")
        name = AREA_CODES.get(code, "기타")
        if name not in regions:
            regions[name] = []
        regions[name].append({
            "title": f["title"],
            "addr": f["addr"],
            "start": f["start"],
            "end": f["end"],
        })

    # dict → list 변환
    result = []
    for region_name, items in sorted(regions.items()):
        result.append({
            "region": region_name,
            "count": len(items),
            "festivals": items[:10]  # 지역별 최대 10건
        })

    print(f"  {len(result)}개 지역 정리 완료")
    return result


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 메인 실행
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def main():
    print(f"===== 공공정보 데이터 갱신 시작 =====")
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

    # 3. 지역별 요약 (진행중 + 다가오는 합쳐서)
    all_festivals = festivals + upcoming
    if all_festivals:
        regions = build_regions(all_festivals)
        save_json("regions.json", regions)

    # 4. 메타 정보
    meta = {
        "updated_at": NOW.strftime("%Y-%m-%d %H:%M:%S"),
        "timezone": "KST",
        "subsidies_count": len(subsidies),
        "festivals_count": len(festivals),
        "upcoming_count": len(upcoming),
    }
    save_json("meta.json", meta)

    print(f"\n===== 갱신 완료 =====")
    print(f"지원금: {len(subsidies)}건 | 축제: {len(festivals)}건 | 다가오는: {len(upcoming)}건")


if __name__ == "__main__":
    main()
