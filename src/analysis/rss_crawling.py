## 설치 라이브러리
# pip install feedparser
# pip install feedparser requests beautifulsoup4
# pip install requests beautifulsoup4 feedparser


import time
import feedparser
import requests
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime
from dateutil import parser

# =========================
# 1. 전체 RSS만 구성
# =========================
RSS_FEEDS = {
    "매일경제": {
        "경제": "https://www.mk.co.kr/rss/30100041/",
        "정치": "https://www.mk.co.kr/rss/30200030/",
        "사회": "https://www.mk.co.kr/rss/50400012/",
        "국제": "https://www.mk.co.kr/rss/30300018/",
        "증권": "https://www.mk.co.kr/rss/50200011/",
        "부동산": "https://www.mk.co.kr/rss/50300009/",
    },

    "한국경제": {
        "증권": "https://www.hankyung.com/feed/finance",
        "경제": "https://www.hankyung.com/feed/economy",
        "부동산": "https://www.hankyung.com/feed/realestate",
        "IT": "https://www.hankyung.com/feed/it",
        "정치": "https://www.hankyung.com/feed/politics",
        "국제": "https://www.hankyung.com/feed/international",
        "사회": "https://www.hankyung.com/feed/society",
    },

    "국민일보": {
        "경제": "https://www.kmib.co.kr/rss/data/kmibEcoRss.xml",
        "정치": "https://www.kmib.co.kr/rss/data/kmibPolRss.xml",
        "국제": "https://www.kmib.co.kr/rss/data/kmibIntRss.xml",
        "사회": "https://www.kmib.co.kr/rss/data/kmibSocRss.xml",
    }
    }

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )
}


# =========================
# 2. RSS에서 기사 목록 수집
# =========================
def convert_to_datetime_format(date_str: str) -> str:
    """
    RSS published 날짜를 collected_at 과 동일한 형식으로 변환
    """
    try:
        dt = parser.parse(date_str)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except:
        return None

def collect_rss_links(rss_feeds: dict, max_items_per_feed: int = 10) -> pd.DataFrame:
    rows = []

    for media, categories in rss_feeds.items():
        for category, url in categories.items():
            print(f"[RSS 수집] {media} - {category} - {url}")
            feed = feedparser.parse(url)

            entries = feed.entries[:max_items_per_feed]

            for entry in entries:
                rows.append({
                    "media": media,
                    "category": category,
                    "title": entry.get("title", ""),
                    "link": entry.get("link", ""),
                    # published → collected_at 형식으로 변환
                    "published_at": convert_to_datetime_format(entry.get("published", "")),
                    "summary": entry.get("summary", ""),
                    "collected_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    # RSS 여부 컬럼 추가
                    "SOURCE_TYPE": "RSS"
                })

    df = pd.DataFrame(rows)
    df = df.drop_duplicates(subset=["link"]).reset_index(drop=True)
    return df


# =========================
# 3. HTML 가져오기
# =========================
def fetch_html(url: str, timeout: int = 15) -> str:
    try:
        res = requests.get(url, headers=HEADERS, timeout=timeout)
        res.raise_for_status()
        return res.text
    except Exception as e:
        print(f"[HTML 요청 실패] {url} | {e}")
        return ""


# =========================
# 4. 언론사별 본문 추출
# =========================
def extract_article_text_by_media(media: str, html: str) -> str:
    if not html:
        return ""

    soup = BeautifulSoup(html, "html.parser")

    # script/style 제거
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


    # 1) 언론사별 selector 우선 시도
    for selector in selectors.get(media, []):
        node = soup.select_one(selector)
        if node:
            text = node.get_text("\n", strip=True)
            text = clean_text(text)
            if len(text) > 100:
                return text

    # 2) article 태그 fallback
    article_tag = soup.find("article")
    if article_tag:
        text = article_tag.get_text("\n", strip=True)
        text = clean_text(text)
        if len(text) > 100:
            return text

    # 3) 본문 길어 보이는 div fallback
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


def clean_text(text: str) -> str:
    if not text:
        return ""

    lines = [line.strip() for line in text.splitlines()]
    lines = [line for line in lines if line]

    cleaned = "\n".join(lines)

    # 너무 흔한 불필요 문구 제거
    garbage_patterns = [
        "무단 전재",
        "재배포 금지",
        "구독",
        "기자",
        "앱에서 읽기",
        "공유",
        "댓글",
    ]

    filtered_lines = []
    for line in cleaned.splitlines():
        if not any(g in line for g in garbage_patterns):
            filtered_lines.append(line)

    return "\n".join(filtered_lines).strip()


# =========================
# 5. 기사 본문 수집
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

    # 🔥 content_length 500 미만 제거
    df = df[df["content_length"] >= 500].reset_index(drop=True)

    return df


# =========================
# 6. 실행
# =========================
if __name__ == "__main__":
    # RSS에서 기사 링크만 우선 수집
    df_links = collect_rss_links(RSS_FEEDS, max_items_per_feed=3) ## max_items_per_feed 로 가져올 기사 수 세팅 가능
    print (df_links)
    print("\n[RSS 링크 수집 결과]")
    print(df_links[["media", "category", "title", "link", "published_at"]].head().to_string())

    # 기사 링크 들어가서 본문 수집
    df_articles = collect_article_contents(df_links, sleep_sec=0.5)

    print("\n[본문 수집 결과]")
    print(df_articles[["media", "title", "content_length"]].head().to_string())

    # 엑셀 저장
    df_articles.to_excel("rss_articles_with_content.xlsx", index=False)
    print("\n저장 완료: rss_articles_with_content.xlsx")