import re


class QuizNewsCleaner:
    """
    퀴즈 기사 여부를 판별하는 클래스

    역할:
    - DB 조회 안 함
    - DB 업데이트 안 함
    - 전달받은 뉴스 데이터에서 퀴즈 여부만 판단
    """

    def is_quiz_article(self, title: str, contents: str) -> bool:
        title = str(title or "")
        contents = str(contents or "")

        if "퀴즈" in title:
            return True

        if "[문제]" in contents and "[해설]" in contents:
            return True

        if "[문제]" in contents and "정답" in contents:
            return True

        question_count = len(re.findall(r"\n?\d+\.\s*", contents))
        choice_count = len(re.findall(r"[①②③④⑤]", contents))

        has_answer = bool(
            re.search(r"[▶▷]?\s*정답\s*[:：]?", contents)
            or re.search(r"정답\s*[①②③④⑤]", contents)
        )

        if question_count >= 3 and choice_count >= 8 and has_answer:
            return True

        return False

    def find_quiz_news_ids(self, news_rows: list[dict]) -> list[int]:
        """
        뉴스 리스트에서 퀴즈 기사 news_id만 추출한다.
        """
        quiz_news_ids = []

        for row in news_rows:
            news_id = row.get("news_id")
            title = row.get("news_title")
            contents = row.get("contents")

            if self.is_quiz_article(title, contents):
                quiz_news_ids.append(news_id)

        return quiz_news_ids