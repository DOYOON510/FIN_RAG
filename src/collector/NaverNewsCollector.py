import random
import time
from datetime import datetime
import os

import requests
from dotenv import load_dotenv

from src.common.common_const import NewsCollectorConfig
from src.common.setup_log import SetupLogger
from src.collector.NewsPreprocessor import NewsPreprocessor
from src.collector.ArticleFetcher import ArticleFetcher
from src.database.postgres_common import PostgresInsert

# .env 파일 로드 (API 키 등)
load_dotenv()


class NaverNewsCollector:
    """
    네이버 뉴스 수집 전체 흐름을 담당하는 클래스

    역할:
    1. 네이버 API 호출
    2. 키워드별 뉴스 메타데이터 수집
    3. 언론사/날짜 필터링
    4. 기사 본문 수집
    5. DB insert용 데이터 생성
    """

    # 환경변수에서 API 키 로드
    CLIENT_ID = os.getenv("NAVER_CLIENT_ID")
    CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET")

    # API 요청 단위 및 최대 수집 개수
    DISPLAY_PER_CALL = 100
    MAX_ITEMS_PER_KEYWORD = 100

    def __init__(self, start_date: str, end_date: str):
        """
        수집 기간 설정 및 logger 초기화
        """
        self.start_date = start_date
        self.end_date = end_date
        self.logger = SetupLogger.get_logger()

        self.logger.info(f"네이버 뉴스 수집기 생성: {self.start_date} ~ {self.end_date}")

    # =========================
    # 1. API 호출
    # =========================
    def get_naver_news(self, query: str, start: int = 1, sort: str = "date") -> dict:
        """
        네이버 뉴스 검색 API 호출

        :param query: 검색 키워드
        :param start: 시작 index
        :param sort: 정렬 방식 (date / sim)
        :return: API 응답 JSON
        """

        url = "https://openapi.naver.com/v1/search/news.json"

        headers = {
            "X-Naver-Client-Id": self.CLIENT_ID,
            "X-Naver-Client-Secret": self.CLIENT_SECRET,
        }

        params = {
            "query": query,
            "display": self.DISPLAY_PER_CALL,
            "start": start,
            "sort": sort,
        }

        try:
            self.logger.debug(f"Naver API 요청: query={query}, start={start}, sort={sort}")

            response = requests.get(
                url,
                headers=headers,
                params=params,
                timeout=10
            )
            response.raise_for_status()

            return response.json()

        except Exception as e:
            self.logger.error(f"Naver API 요청 실패: query={query}, start={start} | {e}")
            return {}

    # =========================
    # 2. 키워드별 뉴스 수집
    # =========================
    def collect_naver_news(self, query: str, category: str) -> list[dict]:
        """
        특정 키워드에 대한 뉴스 메타데이터 수집

        :param query: 검색 키워드
        :param category: 카테고리
        :return: 뉴스 리스트 (본문 제외)
        """

        self.logger.debug(f"키워드 수집 시작: category={category}, keyword={query}")

        news_list = []
        start = 1

        # 최대 1000개 제한 + 설정한 최대 수집 개수 제한
        while start <= 1000 and len(news_list) < self.MAX_ITEMS_PER_KEYWORD:

            data = self.get_naver_news(query=query, start=start)
            items = data.get("items", [])

            # 결과 없으면 종료
            if not items:
                break

            for item in items:
                # 원본 링크 우선 사용
                final_link = item.get("originallink") or item.get("link")

                # 언론사 판별
                media = NewsPreprocessor.extract_media_name(final_link)

                # 뉴스 메타데이터 생성
                news = {
                    "media": media,
                    "title": NewsPreprocessor.clean_html(item.get("title", "")),
                    "link": final_link,
                    "published_at": NewsPreprocessor.convert_to_date(item.get("pubDate", "")),
                    "summary": NewsPreprocessor.clean_html(item.get("description", "")),
                    "collected_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "SOURCE_TYPE": "NAVER",
                    "keyword": query,
                    "category": category,
                }

                news_list.append(news)

                # 최대 개수 도달 시 종료
                if len(news_list) >= self.MAX_ITEMS_PER_KEYWORD:
                    break

            start += self.DISPLAY_PER_CALL
            time.sleep(random.uniform(0.2, 0.5))  # API 과부하 방지

        return news_list

    # =========================
    # 3. 전체 키워드 수집
    # =========================
    def collect_all_keywords(self, keywords_by_category: dict) -> list[dict]:
        """
        카테고리별 키워드 전체 수집 + 필터링

        :param keywords_by_category: {카테고리: [키워드]}
        :return: 필터링된 뉴스 리스트
        """

        results = []

        for category, keywords in keywords_by_category.items():
            self.logger.info(f"[{category}] 수집 시작")

            for keyword in keywords:
                self.logger.info(f"수집 중: category={category}, keyword={keyword}")

                news_list = self.collect_naver_news(keyword, category)

                # 결과 없으면 skip
                if not news_list:
                    self.logger.debug(f"수집 결과 없음: category={category}, keyword={keyword}")
                    continue

                # 언론사 필터
                media_filtered = [
                    news for news in news_list
                    if NewsPreprocessor.is_target_media(news.get("link"))
                ]

                # 날짜 필터
                date_filtered = [
                    news for news in media_filtered
                    if NewsPreprocessor.is_in_date_range(
                        news.get("published_at"),
                        self.start_date,
                        self.end_date
                    )
                ]

                self.logger.debug(
                    f"필터링 결과: category={category}, keyword={keyword}, "
                    f"원본={len(news_list)}건 → 언론사={len(media_filtered)}건 → 날짜={len(date_filtered)}건"
                )

                results.extend(date_filtered)

        # 중복 제거
        before = len(results)
        results = NewsPreprocessor.remove_duplicate_news(results)
        after = len(results)

        self.logger.debug(f"중복 제거: {before} → {after}")

        return results

    # =========================
    # 4. 본문 수집
    # =========================
    def collect_article_contents(self, news_list: list[dict]) -> list[dict]:
        """
        뉴스 링크를 기반으로 본문 수집

        :param news_list: 뉴스 메타데이터 리스트
        :return: 본문 포함된 뉴스 리스트
        """

        results = []

        self.logger.info(f"본문 수집 시작: 대상={len(news_list)}건")

        for idx, news in enumerate(news_list):
            url = news.get("link", "")
            media = news.get("media", "")

            self.logger.info(f"본문 수집: ({idx + 1}/{len(news_list)}) {media} | {url}")

            try:
                html = ArticleFetcher.fetch_html(url)
                content = ArticleFetcher.extract_article_text_by_media(media, html)

                # 너무 짧으면 제외
                if len(content) < 500:
                    self.logger.debug(f"본문 길이 부족 제외: {len(content)}")
                    continue

                results.append({
                    **news,
                    "content": content
                })

            except Exception as e:
                self.logger.error(f"본문 수집 실패: {url} | {e}")
                continue

            time.sleep(random.uniform(0.5, 1.5))  # 크롤링 부하 방지

        self.logger.info(f"본문 수집 완료: {len(results)}건")

        return results

    # =========================
    # 5. 최종 데이터 변환
    # =========================
    def build_data_list(self, articles: list[dict]) -> list[dict]:
        """
        DB insert용 데이터 형태로 변환

        :param articles: 본문 포함 뉴스 리스트
        :return: DB insert용 data_list
        """

        data_list = []

        for article in articles:
            # 날짜 보정
            published_date = NewsPreprocessor.convert_to_date(article.get("published_at"))

            if not published_date:
                collected_at = article.get("collected_at")
                published_date = (
                    NewsPreprocessor.convert_to_date(collected_at)
                    if collected_at else datetime.now().strftime("%Y-%m-%d")
                )

            data_list.append({
                "source_type": article.get("SOURCE_TYPE", "NAVER"),
                "news_title": article.get("title", ""),
                "publisher_name": NewsCollectorConfig.PUBLISHER_CODE_MAP.get(
                    article.get("media", ""),
                    article.get("media", "")
                ),
                "category": article.get("category", ""),
                "published_date": published_date,
                "contents": article.get("content", ""),
                "url": article.get("link", ""),
            })

        self.logger.info(f"DB insert용 데이터 변환 완료: {len(data_list)}건")

        return data_list

    # =========================
    # 6. 실행 함수
    # =========================
    def run(self, keywords_by_category: dict) -> list[dict]:
        """
        전체 수집 프로세스 실행

        :return: 최종 data_list
        """

        self.logger.info("네이버 뉴스 수집 시작")

        links = self.collect_all_keywords(keywords_by_category)
        self.logger.info(f"뉴스 링크 수집 완료: {len(links)}건")

        articles = self.collect_article_contents(links)
        data_list = self.build_data_list(articles)

        self.logger.info(f"네이버 뉴스 수집 완료: 최종 {len(data_list)}건")

        return data_list


# =========================
# 실행
# =========================
if __name__ == "__main__":
    collector = NaverNewsCollector(
        start_date="2026-04-25",
        end_date="2026-05-01"
    )

    data_list = collector.run(NewsCollectorConfig.KEYWORDS_BY_CATEGORY)

    postgres_insert = PostgresInsert()
    postgres_insert.insert_data_to_postgres("t_news_data", data_list, "BULK")

    logger = SetupLogger.get_logger()
    logger.info(f"DB INSERT 요청 완료: {len(data_list)}건")