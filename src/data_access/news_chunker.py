import re
from sqlalchemy import text
from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.database.connect_postgres import PostgresDB
from src.common.setup_log import SetupLogger

from src.data_access.news_repository import QuizNewsCleaner


class NewsChunker:
    """
    t_news_data에서 뉴스를 조회하고 전처리 후 청킹하여
    t_vector_data에 저장하는 클래스
    """

    def __init__(self, db):
        self.db = db
        self.quiz_cleaner = QuizNewsCleaner()
        self.logger = SetupLogger.get_logger()

    def fetch_chunking_target_news(self) -> list[dict]:
        self.logger.info("청킹 대상 뉴스 조회 시작")

        with self.db.get_postgres_db() as session:
            query = text("""
                         SELECT
                             news_id,
                             news_title,
                             contents,
                             category,
                             published_date,
                             url
                         FROM t_news_data
                         WHERE del_yn = FALSE
                           AND chunking_yn = FALSE
                         """)

            result = session.execute(query)
            news_rows = [dict(row._mapping) for row in result]

            self.logger.info(f"청킹 대상 뉴스 조회 완료 - {len(news_rows)}건")

            return news_rows

    def update_del_yn_true(self, news_ids: list[int]) -> int:
        if not news_ids:
            self.logger.info("퀴즈 기사 없음 - del_yn 업데이트 생략")
            return 0

        with self.db.get_postgres_db() as session:
            query = text("""
                         UPDATE t_news_data
                         SET del_yn = TRUE
                         WHERE news_id = ANY(:news_ids)
                         """)

            result = session.execute(query, {"news_ids": news_ids})
            session.commit()

            updated_count = result.rowcount

            self.logger.info(f"퀴즈 기사 del_yn 업데이트 완료 - {updated_count}건")

            return updated_count

    def update_chunking_yn_true(self, news_ids: list[int]) -> int:
        if not news_ids:
            self.logger.info("청킹 완료 뉴스 없음 - chunking_yn 업데이트 생략")
            return 0

        with self.db.get_postgres_db() as session:
            query = text("""
                         UPDATE t_news_data
                         SET chunking_yn = TRUE
                         WHERE news_id = ANY(:news_ids)
                         """)

            result = session.execute(query, {"news_ids": news_ids})
            session.commit()

            updated_count = result.rowcount

            self.logger.info(f"chunking_yn 업데이트 완료 - {updated_count}건")

            return updated_count

    def clean_text(self, text_value) -> str:
        if text_value is None:
            return ""

        text_value = str(text_value)

        email_patterns = [
            r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
        ]

        image_patterns = [
            r"사진\s*=",
            r"사진\s*제공",
            r"자료사진",
            r"이미지\s*확대",
            r"사진\s*확대",
            r"화면\s*캡처",
            r"캡처\s*사진",
            r"그래픽\s*=",
            r"이미지\s*크게보기",
        ]

        reporter_patterns = [
            r"^[가-힣]{2,5}\s*기자$",
            r"^[가-힣]{2,5}\s*특파원$",
            r"^.*=\s*[가-힣]{2,5}\s*기자$",
        ]

        cleaned_lines = []

        for line in text_value.splitlines():
            line = line.strip()

            if not line:
                continue

            if any(re.search(pattern, line) for pattern in email_patterns):
                continue

            if any(re.search(pattern, line) for pattern in image_patterns):
                continue

            if any(re.search(pattern, line) for pattern in reporter_patterns):
                continue

            cleaned_lines.append(line)

        text_value = "\n".join(cleaned_lines)

        text_value = re.sub(r"[ \t]+", " ", text_value)
        text_value = re.sub(r"\n{3,}", "\n\n", text_value)

        return text_value.strip()

    def make_chunk_text(self, title, content_chunk: str) -> str:
        title = str(title or "").strip()

        if title:
            return f"제목: {title}\n\n{content_chunk}"

        return content_chunk

    def chunk_article(
            self,
            row: dict,
            splitter: RecursiveCharacterTextSplitter,
    ) -> list[dict]:

        news_id = row.get("news_id")
        title = row.get("news_title")
        content = row.get("contents")

        cleaned_content = self.clean_text(content)

        if not cleaned_content:
            self.logger.warning(f"본문 없음 또는 전처리 후 빈 본문 - news_id={news_id}")
            return []

        chunks = splitter.split_text(cleaned_content)

        result = []

        for idx, chunk in enumerate(chunks):
            chunk_text = self.make_chunk_text(title, chunk)

            result.append({
                "chunking_id": f"{news_id}{idx + 1:02d}",
                "chunking_index": idx + 1,
                "news_title": title,
                "category": row.get("category"),
                "published_date": row.get("published_date"),
                "url": row.get("url"),
                "chunking_text": chunk_text,
            })

        self.logger.debug(f"news_id={news_id} 청킹 완료 - {len(result)}개")

        return result

    def insert_vector_data(self, chunks: list[dict]) -> int:
        if not chunks:
            self.logger.info("저장할 청크 없음 - t_vector_data INSERT 생략")
            return 0

        with self.db.get_postgres_db() as session:
            query = text("""
                         INSERT INTO t_vector_data
                         (
                             chunking_id,
                             chunking_index,
                             news_title,
                             category,
                             published_date,
                             url,
                             chunking_text
                         )
                         VALUES
                             (
                                 :chunking_id,
                                 :chunking_index,
                                 :news_title,
                                 :category,
                                 :published_date,
                                 :url,
                                 :chunking_text
                             )
                         """)

            result = session.execute(query, chunks)
            session.commit()

            inserted_count = result.rowcount

            self.logger.info(f"t_vector_data INSERT 완료 - {inserted_count}건")

            return inserted_count

    def run(
            self,
            chunk_size: int,
            chunk_overlap: int,
    ) -> list[dict]:

        self.logger.info("===== 뉴스 청킹 작업 시작 =====")

        news_rows = self.fetch_chunking_target_news()

        self.logger.info("퀴즈 기사 판별 시작")
        quiz_news_ids = self.quiz_cleaner.find_quiz_news_ids(news_rows)

        deleted_count = self.update_del_yn_true(quiz_news_ids)

        quiz_news_id_set = set(quiz_news_ids)

        target_news_rows = [
            row for row in news_rows
            if row.get("news_id") not in quiz_news_id_set
        ]

        self.logger.info(f"퀴즈 제외 후 청킹 대상 뉴스 수 - {len(target_news_rows)}건")

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", ". ", " ", ""],
        )

        all_chunks = []
        chunked_news_ids = []

        self.logger.info("뉴스 청킹 시작")

        for row in target_news_rows:
            news_id = row.get("news_id")

            chunks = self.chunk_article(
                row=row,
                splitter=splitter,
            )

            if not chunks:
                continue

            all_chunks.extend(chunks)
            chunked_news_ids.append(news_id)

        self.logger.info("t_vector_data INSERT 시작")
        inserted_count = self.insert_vector_data(all_chunks)

        self.logger.info("chunking_yn 업데이트 시작")
        updated_chunking_count = self.update_chunking_yn_true(chunked_news_ids)

        self.logger.info(
            f"""
==================== 뉴스 청킹 작업 완료 ====================
전체 조회 뉴스 수          : {len(news_rows)}
삭제 기사 수              : {len(quiz_news_ids)}
삭제 del_yn 업데이트 수    : {deleted_count}
청킹 대상 뉴스 수          : {len(target_news_rows)}
생성된 청크 수             : {len(all_chunks)}
t_vector_data INSERT 수    : {inserted_count}
chunking_yn 업데이트 수    : {updated_chunking_count}
============================================================
"""
        )

        return all_chunks


def execute():
    """
    뉴스 청킹 전체 프로세스를 실행한다.
    """
    db = PostgresDB()

    chunker = NewsChunker(db=db)

    chunker.run(
        chunk_size=500,
        chunk_overlap=100,
    )


if __name__ == "__main__":
    execute()