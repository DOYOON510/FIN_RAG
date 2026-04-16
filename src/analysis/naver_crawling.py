import time
import re
from html import unescape
from urllib.parse import urlparse
from datetime import datetime
from dateutil import parser

import requests
import pandas as pd
from bs4 import BeautifulSoup

# =========================
# 1. 네이버 API 인증 정보
# =========================
CLIENT_ID = "FQa2GprHaQLln1rVSIJ6"
CLIENT_SECRET = "Z_hmTUfpPZ"

# =========================
# 2. 수집할 키워드 설정
#    category = 아래 주석 기준 그룹명
# =========================
KEYWORDS_BY_CATEGORY = {
    "경제": [
        "금리", "기준금리", "인플레이션", "CPI", "GDP",
        "경기침체", "고용지표", "실업률", "국채금리", "통화정책",
    ],

    "증권": [
        "코스피", "코스닥", "나스닥", "S&P500", "증시",
        "주가", "공매도", "IPO", "PER", "실적발표",
    ],

    "IT": [
        "AI", "반도체", "HBM", "파운드리", "클라우드",
        "데이터센터", "빅테크", "자율주행", "전기차", "2차전지",
    ],

    "부동산": [
        "부동산", "아파트", "주택시장", "전세", "월세",
        "정책", "분양", "청약", "재건축", "LTV",
    ],

    "정치": [
        "정부정책", "규제", "법안", "국회", "대통령", "정부",
        "선거", "정책발표", "세금", "예산안", "경제정책",
    ],

    "국제": [
        "경제", "미국", "환율", "원달러", "달러인덱스",
        "유가", "WTI", "무역", "관세", "공급망",
    ],

    "사회": [
        "고용시장", "물가상승", "가계부채", "출산율", "인구감소", "고용", "물가",
        "청년실업", "노동시장", "최저임금", "임금상승", "복지정책",
    ],

    "주요 기업": [
        "삼성전자", "SK하이닉스", "엔비디아", "애플", "마이크로소프트",
        "테슬라", "아마존", "구글", "TSMC", "현대차",
    ]
}

# =========================
# 3. 날짜 설정
# =========================
START_DATE = "2026-01-01"
END_DATE = "2026-04-15"

# =========================
# 4. 기사 수 설정
# =========================
DISPLAY_PER_CALL = 100 ## API 호출 제한
MAX_ITEMS_PER_KEYWORD = 300 ## 키워등 하나당 가져오는 기사 개수

# =========================
# 5. 필터링할 언론사 도메인 설정
# =========================
MEDIA_DOMAINS = {
    "매일경제": "mk.co.kr",
    "한국경제": "hankyung.com",
    "국민일보": "kmib.co.kr"
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )
}

# =========================
# 6. 공통 함수
# =========================
def clean_html(text: str) -> str:
    if not text:
        return ""
    text = unescape(text)
    text = re.sub(r"<.*?>", "", text)
    return text.strip()

def convert_to_datetime_format(date_str: str) -> str:
    if not date_str:
        return None
    try:
        dt = parser.parse(date_str)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return None

def extract_domain(url: str) -> str:
    if not url:
        return ""
    try:
        netloc = urlparse(url).netloc.lower()
        return netloc.replace("www.", "")
    except Exception:
        return ""

def extract_media_name(url: str) -> str:
    domain = extract_domain(url)
    for media_name, media_domain in MEDIA_DOMAINS.items():
        if media_domain in domain:
            return media_name
    return "기타"

def is_target_media(url: str) -> bool:
    domain = extract_domain(url)
    return any(media_domain in domain for media_domain in MEDIA_DOMAINS.values())

def fix_broken_text(text: str) -> str:
    """
    본문 인코딩 깨짐(모지바케) 완화용 후처리
    """
    if not text:
        return ""

    replacements = {
        "\xa0": " ",
        "\u200b": "",
        "\ufeff": "",
        "â": "'",
        "â": '"',
        "â": '"',
        "â": "-",
        "â": "-",
    }
    for bad, good in replacements.items():
        text = text.replace(bad, good)

    return text.strip()

def clean_text(text: str) -> str:
    if not text:
        return ""

    text = fix_broken_text(text)

    lines = [line.strip() for line in text.splitlines()]
    lines = [line for line in lines if line]
    cleaned = "\n".join(lines)

    garbage_patterns = [
        "무단 전재",
        "재배포 금지",
        "구독",
        "앱에서 읽기",
        "공유",
        "댓글",
    ]

    filtered_lines = []
    for line in cleaned.splitlines():
        if not any(g in line for g in garbage_patterns):
            filtered_lines.append(line)

    return "\n".join(filtered_lines).strip()

def filter_by_date_range(df: pd.DataFrame, start_date: str, end_date: str) -> pd.DataFrame:
    if df.empty:
        return df

    temp = df.copy()
    temp["published_at_dt"] = pd.to_datetime(temp["published_at"], errors="coerce")

    start_dt = pd.to_datetime(start_date)
    end_dt = pd.to_datetime(end_date) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)

    temp = temp[
        (temp["published_at_dt"].notna()) &
        (temp["published_at_dt"] >= start_dt) &
        (temp["published_at_dt"] <= end_dt)
    ].copy()

    temp = temp.drop(columns=["published_at_dt"])
    temp = temp.reset_index(drop=True)
    return temp

# =========================
# 7. HTML 가져오기 (인코딩 보강)
# =========================
def fetch_html(url: str, timeout: int = 15) -> str:
    try:
        res = requests.get(url, headers=HEADERS, timeout=timeout)
        res.raise_for_status()

        # 1차: requests가 추정한 인코딩 사용
        if res.apparent_encoding:
            res.encoding = res.apparent_encoding

        html = res.text

        # 2차: 한글 깨짐 흔적이 보이면 content 기반 재디코딩 시도
        broken_signs = ["���", "�", "Ã", "Â", "â"]
        if any(sign in html for sign in broken_signs):
            for enc in [res.apparent_encoding, "utf-8", "cp949", "euc-kr"]:
                if not enc:
                    continue
                try:
                    html2 = res.content.decode(enc, errors="replace")
                    if html2.count("�") < html.count("�"):
                        html = html2
                except Exception:
                    pass

        return html

    except Exception as e:
        print(f"[HTML 요청 실패] {url} | {e}")
        return ""

# =========================
# 8. 언론사별 본문 추출
# =========================
def extract_article_text_by_media(media: str, html: str) -> str:
    if not html:
        return ""

    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    selectors = {
        "매일경제": [
            "div.news_cnt_detail_wrap",
            "div.art_txt",
            "div.news_detail_wrap",
            "section.news_cnt_detail_wrap",
        ],
        "한국경제": [
            "div.article-body",
            "div#articletxt",
            "div.articleBody",
            "div.view-content",
        ],
        "국민일보": [
            "div#articleBody",
            "div.article_body",
            "div#article_body",
            "div.article-body",
        ],
    }

    for selector in selectors.get(media, []):
        node = soup.select_one(selector)
        if node:
            text = node.get_text("\n", strip=True)
            text = clean_text(text)
            if len(text) > 100:
                return text

    article_tag = soup.find("article")
    if article_tag:
        text = article_tag.get_text("\n", strip=True)
        text = clean_text(text)
        if len(text) > 100:
            return text

    candidates = []
    for div in soup.find_all("div"):
        text = div.get_text(" ", strip=True)
        text = clean_text(text)
        if len(text) > 200:
            candidates.append(text)

    if candidates:
        candidates = sorted(candidates, key=len, reverse=True)
        return candidates[0]

    return ""

# =========================
# 9. 네이버 뉴스 API 호출 함수
# =========================
def get_naver_news(query: str, display: int = DISPLAY_PER_CALL, start: int = 1, sort: str = "date") -> dict:
    url = "https://openapi.naver.com/v1/search/news.json"

    headers = {
        "X-Naver-Client-Id": CLIENT_ID,
        "X-Naver-Client-Secret": CLIENT_SECRET,
    }

    params = {
        "query": query,
        "display": display,
        "start": start,
        "sort": sort,
    }

    response = requests.get(url, headers=headers, params=params, timeout=10)
    response.raise_for_status()
    return response.json()

# =========================
# 10. 키워드별 뉴스 메타데이터 수집
# =========================
def collect_naver_news(
    query: str,
    category: str,
    max_items: int = MAX_ITEMS_PER_KEYWORD,
    sort: str = "date"
) -> pd.DataFrame:
    all_rows = []
    display = DISPLAY_PER_CALL
    start = 1

    while start <= 1000 and len(all_rows) < max_items:
        data = get_naver_news(query=query, display=display, start=start, sort=sort)
        items = data.get("items", [])

        if not items:
            break

        for item in items:
            originallink = item.get("originallink", "")
            naver_link = item.get("link", "")
            final_link = originallink if originallink else naver_link
            media = extract_media_name(final_link)

            row = {
                "media": media,
                "title": clean_html(item.get("title", "")),
                "link": final_link,
                "published_at": convert_to_datetime_format(item.get("pubDate", "")),
                "summary": clean_html(item.get("description", "")),
                "collected_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "SOURCE_TYPE": "NAVER_API",
                "keyword": query,
                "category": category,   # 주석 그룹명(경제/증권/IT...)
            }
            all_rows.append(row)

            if len(all_rows) >= max_items:
                break

        start += display
        time.sleep(0.2)

    return pd.DataFrame(all_rows)

# =========================
# 11. 전체 키워드 수집 + 언론사 필터링 + 날짜 필터링
# =========================
def collect_all_keywords(
    keywords_by_category: dict[str, list[str]],
    max_items_per_keyword: int = MAX_ITEMS_PER_KEYWORD,
    start_date: str = START_DATE,
    end_date: str = END_DATE
) -> pd.DataFrame:
    results = []

    for category, keywords in keywords_by_category.items():
        print(f"\n===== [{category}] 수집 시작 =====")

        for keyword in keywords:
            print(f"[수집 중] category={category}, keyword={keyword}")
            df = collect_naver_news(
                query=keyword,
                category=category,
                max_items=max_items_per_keyword,
                sort="date"
            )

            if df.empty:
                print("  -> 결과 없음")
                continue

            # 1) 언론사 필터링
            df = df[df["link"].apply(is_target_media)].copy()

            # 2) 날짜 필터링
            before_cnt = len(df)
            df = filter_by_date_range(df, start_date, end_date)
            after_cnt = len(df)

            print(f"  -> 언론사 필터 후 {before_cnt}건 / 날짜 필터 후 {after_cnt}건")
            results.append(df)

    if not results:
        return pd.DataFrame(columns=[
            "media", "title", "link", "published_at", "summary",
            "collected_at", "SOURCE_TYPE", "keyword", "category"
        ])

    final_df = pd.concat(results, ignore_index=True)
    final_df = final_df.drop_duplicates(subset=["link", "title"]).reset_index(drop=True)
    return final_df

# =========================
# 12. 본문 수집
# =========================
def collect_article_contents(df_links: pd.DataFrame, sleep_sec: float = 0.5) -> pd.DataFrame:
    results = []

    for idx, row in df_links.iterrows():
        media = row["media"]
        url = row["link"]

        print(f"[본문 수집] ({idx+1}/{len(df_links)}) {media} | {url}")

        html = fetch_html(url)
        article_text = extract_article_text_by_media(media, html)

        results.append({
            **row.to_dict(),
            "content": article_text,
            "content_length": len(article_text),
        })

        time.sleep(sleep_sec)

    df = pd.DataFrame(results)
    df = df[df["content_length"] >= 500].reset_index(drop=True)
    return df

# =========================
# 13. 실행
# =========================
if __name__ == "__main__":
    df_links = collect_all_keywords(
        keywords_by_category=KEYWORDS_BY_CATEGORY,
        max_items_per_keyword=MAX_ITEMS_PER_KEYWORD,
        start_date=START_DATE,
        end_date=END_DATE
    )

    print("\n===== 메타데이터 수집 완료 =====")
    print(df_links.head())
    print(f"메타데이터 기사 수: {len(df_links)}")

    df_articles = collect_article_contents(df_links, sleep_sec=0.5)

    print("\n===== 본문 수집 완료 =====")
    print(df_articles.head())
    print(f"최종 기사 수: {len(df_articles)}")

    final_columns = [
        "media",
        "title",
        "link",
        "published_at",
        "summary",
        "collected_at",
        "SOURCE_TYPE",
        "keyword",
        "content",
        "content_length",
        "category",   # 마지막 컬럼
    ]
    df_articles = df_articles[final_columns]

    output_file = "../../dy_test/naver_news_with_content.xlsx"
    df_articles.to_excel(output_file, index=False)
    print(f"엑셀 저장 완료: {output_file}")