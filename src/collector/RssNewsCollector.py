import time
import random
from datetime import datetime
import requests

import feedparser

from src.common.common_const import NewsCollectorConfig
from src.common.setup_log import SetupLogger
from src.collector.NewsPreprocessor import NewsPreprocessor
from src.collector.ArticleFetcher import ArticleFetcher
from src.database.postgres_common import PostgresInsert


class RssNewsCollector:
    """
    RSS 기반 뉴스 수집 전체 흐름을 담당하는 클래스

    전체 흐름:
    RSS 메타데이터 수집 → 본문 수집 → DB insert용 데이터 생성
    """

    def __init__(self, sleep_sec: float = 0.5, max_items_per_feed: int = 1):
        """
        수집 설정 초기화

        :param sleep_sec: 요청 간 대기 시간 (크롤링 부하 방지)
        :param max_items_per_feed: RSS 피드당 가져올 기사 개수
        """
        self.sleep_sec = sleep_sec
        self.max_items_per_feed = max_items_per_feed
        self.logger = SetupLogger.get_logger()

        self.logger.info(
            f"RSS 뉴스 수집기 생성: sleep_sec={self.sleep_sec}, "
            f"max_items_per_feed={self.max_items_per_feed}"
        )

    # =========================
    # 1. RSS 기사 링크 수집
    # =========================
    def collect_rss_links(self, rss_feeds: dict) -> list[dict]:
        """
        RSS 피드에서 뉴스 메타데이터 수집

        처리 흐름:
        1. 언론사 → 카테고리 순회
        2. RSS URL 파싱 (feedparser)
        3. 기사 정보(title, link, published_at 등) 추출
        4. 중복 제거

        :param rss_feeds: {언론사: {카테고리: RSS URL}}
        :return: 뉴스 메타데이터 리스트 (본문 제외)
        """
        results = []

        for media, categories in rss_feeds.items():
            self.logger.info(f"[{media}] RSS 수집 시작")

            for category, url in categories.items():
                self.logger.info(f"RSS 수집 중: media={media}, category={category}")

                try:
                    # RSS 파싱
                    res = requests.get(
                        url,
                        headers=NewsCollectorConfig.HEADERS,
                        timeout=10
                    )
                    res.raise_for_status()

                    feed = feedparser.parse(res.content)    # xml -> 파이썬 객체로 변환
                    entries = feed.entries[:self.max_items_per_feed]    # 최대 개수 제한해서 가져옴.

                    if not entries:
                        self.logger.debug(
                            f"RSS 결과 없음: media={media}, category={category}, url={url}"
                        )
                        continue

                    # 각 기사 데이터 생성
                    for entry in entries:
                        news = {
                            "media": media,
                            "category": category,
                            "title": NewsPreprocessor.clean_html(entry.get("title", "")),
                            "link": entry.get("link", ""),
                            "published_at": NewsPreprocessor.convert_to_date(
                                entry.get("published", "")
                            ),
                            "summary": NewsPreprocessor.clean_html(entry.get("summary", "")),
                            "collected_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "SOURCE_TYPE": "RSS",
                        }

                        results.append(news)

                except Exception as e:
                    # RSS 자체 실패
                    self.logger.error(
                        f"RSS 수집 실패: media={media}, category={category}, url={url} | {e}"
                    )
                    continue

        # 중복 제거 (link + title 기준)
        before_count = len(results)
        results = NewsPreprocessor.remove_duplicate_news(results)
        after_count = len(results)

        self.logger.debug(
            f"RSS 중복 제거 완료: 제거 전={before_count}건, 제거 후={after_count}건"
        )

        return results

    # =========================
    # 2. 기사 본문 수집
    # =========================
    def collect_article_contents(self, news_list: list[dict]) -> list[dict]:
        """
        기사 링크를 기반으로 본문 수집

        처리 흐름:
        1. URL 요청 → HTML 가져오기
        2. HTML 파싱 → 본문 추출
        3. 본문 길이 필터 (500자 이상)
        4. content 추가

        :param news_list: 메타데이터 리스트
        :return: 본문 포함 뉴스 리스트
        """
        results = []

        self.logger.info(f"RSS 본문 수집 시작: 대상={len(news_list)}건")

        for idx, news in enumerate(news_list):
            media = news.get("media", "")
            url = news.get("link", "")

            self.logger.info(f"본문 수집: ({idx + 1}/{len(news_list)}) {media} | {url}")

            try:
                # HTML 가져오기
                html = ArticleFetcher.fetch_html(url)

                # 본문 추출
                content = ArticleFetcher.extract_article_text_by_media(media, html)

                # 너무 짧으면 제외
                if len(content) < 500:
                    self.logger.debug(
                        f"본문 길이 부족 제외: length={len(content)}, media={media}, url={url}"
                    )
                    continue

                results.append({
                    **news,
                    "content": content
                })

            except Exception as e:
                # 본문 수집 실패
                self.logger.error(f"RSS 본문 수집 실패: media={media}, url={url} | {e}")
                continue

            # 요청 간 랜덤 대기 (서버 부하 방지)
            time.sleep(random.uniform(self.sleep_sec, self.sleep_sec + 1.0))

        self.logger.info(f"RSS 본문 수집 완료: 성공={len(results)}건")

        return results

    # =========================
    # 3. DB insert용 데이터 변환
    # =========================
    def build_data_list(self, articles: list[dict]) -> list[dict]:
        """
        DB insert용 데이터 형태로 변환

        처리 내용:
        - 날짜 보정
        - 컬럼명 변환
        - publisher 코드 매핑

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

            # DB 스키마에 맞게 변환
            data_list.append({
                "source_type": article.get("SOURCE_TYPE", "RSS"),
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

        self.logger.info(f"RSS DB insert용 데이터 변환 완료: {len(data_list)}건")

        return data_list

    # =========================
    # 4. 실행 함수
    # =========================
    def run(self, rss_feeds: dict) -> list[dict]:
        """
        RSS 뉴스 수집 전체 프로세스 실행

        흐름:
        1. RSS 메타데이터 수집
        2. 본문 수집
        3. DB용 데이터 변환

        :param rss_feeds: RSS URL 정보
        :return: 최종 data_list
        """
        self.logger.info("RSS 뉴스 수집 시작")

        # 1. 링크 수집
        links = self.collect_rss_links(rss_feeds=rss_feeds)
        self.logger.info(f"RSS 링크 수집 완료: {len(links)}건")

        # 2. 본문 수집
        articles = self.collect_article_contents(links)

        # 3. DB 데이터 변환
        data_list = self.build_data_list(articles)

        self.logger.info(f"RSS 뉴스 수집 완료: 최종 {len(data_list)}건")

        return data_list


# =========================
# 실행
# =========================
if __name__ == "__main__":

    collector = RssNewsCollector(
        sleep_sec=0.5,
        max_items_per_feed=50    # rss feed당 가져올 기사 개수
    )

    data_list = collector.run(
        rss_feeds=NewsCollectorConfig.RSS_FEEDS
    )

    postgres_insert = PostgresInsert()
    postgres_insert.insert_data_to_postgres("t_news_data", data_list, "INCR")

    logger = SetupLogger.get_logger()
    logger.info(f"RSS DB INSERT 요청 완료: {len(data_list)}건")