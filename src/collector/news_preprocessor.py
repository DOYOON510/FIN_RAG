import re
from html import unescape
from urllib.parse import urlparse
from dateutil import parser

from src.common.common_const import NewsCollectorConfig


class NewsPreprocessor:
    """
    뉴스 데이터 전처리 관련 유틸 클래스

    역할:
    - HTML 태그 제거
    - 날짜 변환
    - 언론사 판별
    - 텍스트 정제
    - 중복 제거
    """

    @staticmethod
    def clean_html(text: str) -> str:
        """
        HTML 태그 및 특수문자를 제거하는 함수

        - HTML 엔티티(&amp; 등)를 일반 문자로 변환
        - <tag> 형태의 HTML 태그 제거
        - 양쪽 공백 제거

        :param text: HTML 포함 문자열
        :return: 정제된 문자열
        """
        if not text:
            return ""

        text = unescape(text)                  # HTML 엔티티 변환
        text = re.sub(r"<.*?>", "", text)      # HTML 태그 제거
        return text.strip()

    @staticmethod
    def convert_to_date(date_str: str) -> str | None:
        """
        다양한 날짜 형식을 'YYYY-MM-DD' 형태로 변환

        - dateutil.parser를 사용하여 유연하게 파싱
        - 실패 시 None 반환

        :param date_str: 원본 날짜 문자열
        :return: YYYY-MM-DD 문자열 또는 None
        """
        if not date_str:
            return None

        try:
            dt = parser.parse(date_str) #datetime 객체로 바꿔줌
            return dt.strftime("%Y-%m-%d")
        except Exception:
            return None

    @staticmethod
    def extract_domain(url: str) -> str:
        """
        URL에서 도메인만 추출하는 함수

        예:
        https://www.mk.co.kr/news → mk.co.kr

        :param url: URL 문자열
        :return: 도메인 문자열
        """
        if not url:
            return ""

        try:
            netloc = urlparse(url).netloc.lower()
            return netloc.replace("www.", "")
        except Exception:
            return ""

    @staticmethod
    def extract_media_name(url: str) -> str:
        """
        URL을 기반으로 언론사 이름을 판별

        - MEDIA_DOMAINS 설정값을 기준으로 매칭
        - 없으면 '기타' 반환

        :param url: 기사 URL
        :return: 언론사 이름
        """
        domain = NewsPreprocessor.extract_domain(url)

        for media_name, media_domain in NewsCollectorConfig.MEDIA_DOMAINS.items():
            if media_domain in domain:
                return media_name

        return "기타"

    @staticmethod
    def is_target_media(url: str) -> bool:
        """
        해당 URL이 수집 대상 언론사인지 확인

        :param url: 기사 URL
        :return: 대상 언론사 여부 (True/False)
        """
        domain = NewsPreprocessor.extract_domain(url)

        return any(
            media_domain in domain
            for media_domain in NewsCollectorConfig.MEDIA_DOMAINS.values()
        )

    @staticmethod
    def is_in_date_range(published_at: str, start_date: str, end_date: str) -> bool:
        """
        날짜가 지정된 범위 안에 포함되는지 확인

        :param published_at: 기사 날짜 (YYYY-MM-DD)
        :param start_date: 시작 날짜
        :param end_date: 종료 날짜
        :return: 범위 포함 여부
        """
        if not published_at:
            return False

        return start_date <= published_at <= end_date

    @staticmethod
    def clean_text(text: str) -> str:
        """
        기사 본문 텍스트 정제 함수

        처리 내용:
        - 줄 단위 공백 제거
        - 빈 줄 제거
        - 불필요 문구(광고, 공유, 댓글 등) 제거

        :param text: 원본 기사 텍스트
        :return: 정제된 텍스트
        """
        if not text:
            return ""

        # 줄 단위 정리
        lines = [line.strip() for line in text.splitlines()]
        lines = [line for line in lines if line]
        cleaned = "\n".join(lines)

        # 제거할 불필요 문구
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

    @staticmethod
    def remove_duplicate_news(news_list: list[dict]) -> list[dict]:
        """
        뉴스 리스트에서 중복 기사 제거

        기준:
        - (link, title) 조합이 동일하면 중복으로 판단

        :param news_list: 뉴스 dict 리스트
        :return: 중복 제거된 리스트
        """
        unique_news_list = []
        seen_keys = set()

        for news in news_list:
            key = (news.get("link", ""), news.get("title", ""))

            if key in seen_keys:
                continue

            seen_keys.add(key)
            unique_news_list.append(news)

        return unique_news_list