import requests
from bs4 import BeautifulSoup

from src.common.common_const import NewsCollectorConfig
from src.collector.NewsPreprocessor import NewsPreprocessor


class ArticleFetcher:
    """
    기사 HTML을 가져오고, 언론사별로 본문을 추출하는 클래스
    """

    @staticmethod
    def fetch_html(url: str, timeout: int = 15) -> str:
        """
        주어진 URL의 HTML을 요청하여 문자열로 반환하는 함수

        - requests를 사용하여 웹 페이지 요청
        - 인코딩 문제 발생 시 여러 인코딩으로 재시도하여 깨짐 보정
        - 실패 시 빈 문자열 반환

        :param url: 요청할 기사 URL
        :param timeout: 요청 타임아웃 (초)
        :return: HTML 문자열
        """
        try:
            # HTTP GET 요청
            res = requests.get(
                url,
                headers=NewsCollectorConfig.HEADERS,
                timeout=timeout
            )
            res.raise_for_status()

            # 자동 인코딩 설정
            if res.apparent_encoding:
                res.encoding = res.apparent_encoding

            html = res.text

            # 깨진 문자 패턴 체크
            broken_signs = ["���", "�", "Ã", "Â", "â"]

            # 깨짐이 감지되면 다양한 인코딩으로 재시도
            if any(sign in html for sign in broken_signs):
                for enc in [res.apparent_encoding, "utf-8", "cp949", "euc-kr"]:
                    if not enc:
                        continue

                    try:
                        html2 = res.content.decode(enc, errors="replace")

                        # 더 덜 깨진 결과를 채택
                        if html2.count("�") < html.count("�"):
                            html = html2
                    except Exception:
                        pass

            return html

        except Exception as e:
            print(f"[HTML 요청 실패] {url} | {e}")
            return ""

    @staticmethod
    def extract_article_text_by_media(media: str, html: str) -> str:
        """
        HTML에서 언론사별로 기사 본문을 추출하는 함수

        처리 순서:
        1. script/style 등 불필요한 태그 제거
        2. 언론사별 CSS selector로 본문 추출 시도
        3. 실패 시 <article> 태그 사용
        4. 그래도 실패 시 가장 긴 div 텍스트 선택

        :param media: 언론사 이름 (매일경제, 한국경제 등)
        :param html: 기사 HTML
        :return: 정제된 기사 본문 텍스트
        """

        # HTML이 없으면 종료
        if not html:
            return ""

        soup = BeautifulSoup(html, "html.parser")

        # 불필요한 태그 제거
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()

        # 언론사별 본문 selector 정의
        selectors = NewsCollectorConfig.ARTICLE_SELECTORS

        # 1차: 언론사별 selector로 본문 추출
        for selector in selectors.get(media, []):
            node = soup.select_one(selector)

            if node:
                text = node.get_text("\n", strip=True)
                text = NewsPreprocessor.clean_text(text)

                # 일정 길이 이상이면 정상 본문으로 판단
                if len(text) > 100:
                    return text

        # 2차: article 태그 활용
        article_tag = soup.find("article")

        if article_tag:
            text = article_tag.get_text("\n", strip=True)
            text = NewsPreprocessor.clean_text(text)

            if len(text) > 100:
                return text

        # 3차: 모든 div 중 가장 긴 텍스트 선택
        candidates = []

        for div in soup.find_all("div"):
            text = div.get_text(" ", strip=True)
            text = NewsPreprocessor.clean_text(text)

            if len(text) > 200:
                candidates.append(text)

        # 가장 긴 텍스트 반환
        if candidates:
            candidates = sorted(candidates, key=len, reverse=True)
            return candidates[0]

        # 실패 시 빈 문자열 반환
        return ""