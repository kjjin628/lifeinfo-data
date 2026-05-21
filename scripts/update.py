#!/usr/bin/env python3
"""
혜택존 데이터 갱신 스크립트 — 금융/소상공인 올인 정화 버전
- 축제 및 행사(TourAPI) 관련 수집 로직 완전 제거
- 지원금: 지정 화이트+블랙리스트 기반 알짜 필터링 및 서비스ID 중복 제거
- 사업자: 소상공인 중심의 금융/고정비 지원 사업 정밀 필터링
- 메타: 축제 카운트를 제외한 순수 자금 데이터 현황 빌드
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

API_KEY_GOV = API_KEY

KST = datetime.timezone(datetime.timedelta(hours=9))
NOW = datetime.datetime.now(KST)
TODAY = NOW.strftime("%Y%m%d")

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


# ─── 지역 추출 ───
REGION_KEYWORDS = {
    "서울": ["서울"], "경기": ["경기"], "부산": ["부산"], "대구": ["대구"],
    "인천": ["인천"], "광주": ["광주광역"], "대전": ["대전"], "울산": ["울산"],
    "세종": ["세종"], "강원": ["강원"], "충북": ["충청북", "충북"], "충남": ["충청남", "충남"],
    "전북": ["전라북", "전북특별", "전북"], "전남": ["전라남", "전남"], "경북": ["경상북", "경북"],
    "경남": ["경상남", "경남"], "제주": ["제주"],
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
# 💰 정부 지원금 정밀 필터셋
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SUBSIDY_WHITELIST = [
    # 현금 (다수 대상)
    "근로장려", "자녀장려", "민생지원금", "재난지원금",
    "아동수당", "양육수당", "부모급여", "실업급여", "구직급여",
    # 출산/육아
    "출산지원", "출산장려", "출산축하", "출산비",
    "산후조리", "난임", "보육료", "첫만남이용권", "임신지원",
    # 시니어/어르신
    "기초연금", "노인일자리", "경로수당", "장기요양", "노인돌봄", "치매",
    "틀니", "임플란트", "안검하수", "어르신 교통", "경로우대",
    "장수수당", "장수축하", "냉난방비",
    # 주거
    "월세", "전세자금", "주거급여", "주거비", "주거바우처", "신혼부부 주거",
    # 공과금
    "전기요금", "가스비", "난방비", "연료비", "energy바우처", "에너지바우처",
    # 바우처/상품권
    "문화누리", "국민행복카드", "지역사랑상품권", "지역화폐",
    # 건강보험
    "건강보험료",
    # 세금 감면
    "자동차세 감면", "자동차세감면", "취득세 감면", "취득세감면",
    # 교육 (보편적)
    "교육비 지원", "급식비",
]

SUBSIDY_BLACKLIST = [
    # 소수/특정 대상
    "장학금", "장학생", "국가유공", "보훈", "참전", "유공자",
    "고엽제", "민주화운동", "5·18", "5.18", "의사상자", "특별공로",
    # 농축수산
    "농업", "축산", "수산", "어업", "어민", "농가", "한우", "고급육", 
    "친환경 농산물", "양식", "어촌", "영농", "농림", "사료", "종묘", "종자",
    # 기관/법인/종사자
    "법인", "종사자", "사회적기업", "교육연구단",
    # 공무원/군인
    "공무원", "군무원", "군인", "병역",
    # 귀화/외국인
    "귀화", "국적회복", "북한이탈", "탈북",
    # 기관 전용
    "전문인력양성기관",
]


def filter_subsidy_items(all_items):
    matched = []
    for item in all_items:
        title = item.get("name", "")
        if any(kw in title for kw in SUBSIDY_WHITELIST):
            matched.append(item)

    cleaned = []
    for item in matched:
        title = item.get("name", "")
        desc = item.get("desc", "")
        target = item.get("target", "")
        combined = title + " " + desc + " " + target
        if any(bk in combined for bk in SUBSIDY_BLACKLIST):
            continue
        cleaned.append(item)

    seen_ids = set()
    deduped = []
    for item in cleaned:
        sid = item.get("id", "")
        if sid and sid in seen_ids:
            continue
        seen_ids.add(sid)
        deduped.append(item)

    print(f"  지원금 필터링: 화이트 {len(matched)}건 → 블랙차단 {len(cleaned)}건 → ID중복제거 {len(deduped)}건")
    return deduped


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🏢 소상공인·사업자 자금 정밀 필터셋
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

BIZ_WHITELIST = [
    "소상공인", "정책자금", "경영안정자금", "특례보증", "이차보전", "이자차액",
    "무이자", "저금리", "임대료", "월세", "배달비", "카드수수료",
    "전기요금", "에너지", "청년창업", "창업자금", "창업지원", "온누리상품권", "지역사랑상품권",
]

BIZ_BLACKLIST = [
    "수출", "해외", "바이어", "박람회", "R&D", "기술개발", "특허", "인증",
    "스마트공장", "AI인프라", "원자력", "항공우주", "조선업", "방위산업",
    "양식", "어업", "수산", "농업", "산림", "축산", "가축", "사료",
]


def filter_biz_items(all_items):
    result = []
    for item in all_items:
        title = item.get("title", "")
        desc = item.get("desc", "")
        combined = title + " " + desc
        if not any(kw in title for kw in BIZ_WHITELIST):
            continue
        if any(bk in combined for bk in BIZ_BLACKLIST):
            continue
        result.append(item)
    print(f"  사업자 필터링: 원본 {len(all_items)}건 → 정제후 {len(result)}건")
    return result


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 공공 API 수집 엔진
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def get_subsidies():
    print("\n[1] 정부 지원금/혜택 수집 중 (전체 동적 페이징)...")
    init_url = f"https://api.odcloud.kr/api/gov24/v3/serviceList?page=1&perPage=1&serviceKey={API_KEY_GOV}"
    init_data = fetch_json(init_url)

    total_count = 1000
    if init_data and "totalCount" in init_data:
        total_count = init_data["totalCount"]

    per_page = 100
    total_pages = math.ceil(total_count / per_page)
    print(f"  → 총 {total_count}건 ({total_pages}페이지)")

    all_items = []
    for page in range(1, total_pages + 1):
        url = f"https://api.odcloud.kr/api/gov24/v3/serviceList?page={page}&perPage={per_page}&serviceKey={API_KEY_GOV}"
        data = fetch_json(url)
        if not data or "data" not in data:
            print(f"  페이지 {page}: 실패, 중단")
            break
        items = data["data"]
        if not items:
            break
        all_items.extend(items)

    result = []
    for item in all_items:
        target = item.get("지원대상", "")
        org = item.get("소관기관명", "")
        region = extract_region(org)
        if region == "전국":
            region = extract_region(target)

        result.append({
            "id": item.get("서비스ID", ""),
            "name": item.get("서비스명", ""),
            "desc": item.get("서비스목적요약", ""),
            "org": org,
            "target": target,
            "how": item.get("신청방법", ""),
            "url": item.get("서비스상세URL", ""),
            "category": item.get("서비스분야", ""),
            "region": region,
        })

    print(f"  원본 {len(result)}건 확보")
    return result


BIZ_FIELDS = {
    "01": "금융", "02": "기술", "03": "인력",
    "04": "수출", "05": "내수", "06": "창업",
    "07": "경영", "09": "기타"
}


def get_business():
    if not BIZ_KEY:
        print("\n[2] 기업마당 — API 키 없음, 건너뜀")
        return []

    print("\n[2] 기업마당 수집 중...")
    all_items = []

    for field_code, field_name in BIZ_FIELDS.items():
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

    print(f"  원본 {len(all_items)}건 확보")
    return all_items


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 메인 파이프라인 실행 구역
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def main():
    print(f"===== 혜택존 자금 특화형 파이프라인 =====")
    print(f"시각: {NOW.strftime('%Y-%m-%d %H:%M:%S')} KST")

    # 1. 정부 지원금 수집 및 정제
    raw_subsidies = get_subsidies()
    if raw_subsidies:
        subsidies = filter_subsidy_items(raw_subsidies)
        save_json("subsidies.json", subsidies)
    else:
        subsidies = []
        print("  WARN: 지원금 수집 실패")

    # 2. 기업마당 사업자 자금 수집 및 정제
    raw_business = get_business()
    if raw_business:
        business = filter_biz_items(raw_business)
        save_json("business.json", business)
    else:
        business = []
        print("  WARN: 사업자 수집 실패")

    # 3. 데이터 현황 메타 파일 빌드 (축제 지표 완전 제외)
    meta = {
        "updated_at": NOW.strftime("%Y-%m-%d %H:%M:%S"),
        "timezone": "KST",
        "subsidies_count": len(subsidies),
        "business_count": len(business),
    }
    save_json("meta.json", meta)

    print(f"\n===== 정화 완료 =====")
    print(f"최종 적재 결과 -> 지원금: {len(subsidies)}건 | 소상공인 사업자 자금: {len(business)}건")


if __name__ == "__main__":
    main()
