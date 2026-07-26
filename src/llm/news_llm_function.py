from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from src.common.setup_log import SetupLogger

EMBEDDING_MODEL_NAME = "nlpai-lab/KURE-v1"
DEFAULT_LIMIT = 5


@dataclass
class RetrievedNewsChunk:
    """
    Vector DB에서 검색된 뉴스 청크.
    """

    chunking_id: str
    news_id: str | None
    news_title: str | None
    publisher_name: str | None
    category: str | None
    published_date: str | None
    url: str | None
    chunking_text: str
    similarity: float

    def to_json_dict(self) -> dict[str, Any]:
        # Tool Calling 결과와 Streamlit 화면에서 바로 사용할 수 있는 JSON 형태로 변환
        return {
            "chunking_id": self.chunking_id,
            "news_id": self.news_id,
            "news_title": self.news_title,
            "publisher_name": self.publisher_name,
            "category": self.category,
            "published_date": self.published_date,
            "url": self.url,
            "similarity": round(self.similarity, 4),
            "chunking_text": self.chunking_text,
        }


class NewsVectorRepository:
    """
    질문 임베딩과 유사한 뉴스 청크를 pgvector로 조회한다.
    """

    def __init__(self, db: Any | None = None):
        if db is None:
            from src.database.connect_postgres import PostgresDB

            db = PostgresDB()

        self.logger = SetupLogger.get_logger()
        self.db = db

    def search_similar_news(
        self,
        question_embedding: list[float],
        limit: int = DEFAULT_LIMIT,
        min_similarity: float | None = None,
    ) -> list[RetrievedNewsChunk]:
        from sqlalchemy import text

        # pgvector의 vector 타입으로 CAST할 수 있는 문자열 형태로 변환
        query_vector = self._to_pgvector_literal(question_embedding)

        # 질문 임베딩과 뉴스 청크 임베딩 간 cosine distance가 가까운 순서로 조회
        sql = """
            SELECT
                v.chunking_id,
                v.news_id,
                COALESCE(v.news_title, n.news_title) AS news_title,
                n.publisher_name,
                COALESCE(v.category, n.category) AS category,
                COALESCE(v.published_date, n.published_date) AS published_date,
                COALESCE(v.url, n.url) AS url,
                v.chunking_text,
                1 - (v.embedding_vector <=> CAST(:query_vector AS vector)) AS similarity
            FROM t_vector_data v
            LEFT JOIN t_news_data n
                ON v.news_id = n.news_id
            WHERE v.embedding_yn = TRUE
              AND v.embedding_vector IS NOT NULL
              AND v.embedding_model = :embedding_model
              AND COALESCE(v.del_yn, FALSE) = FALSE
              AND COALESCE(n.del_yn, FALSE) = FALSE
        """

        params: dict[str, Any] = {
            "query_vector": query_vector,
            "embedding_model": EMBEDDING_MODEL_NAME,
            "limit": limit,
        }

        if min_similarity is not None:
            # 최소 유사도가 지정된 경우 기준 미만 뉴스는 제외
            sql += """
              AND 1 - (v.embedding_vector <=> CAST(:query_vector AS vector)) >= :min_similarity
            """
            params["min_similarity"] = min_similarity

        sql += """
            ORDER BY v.embedding_vector <=> CAST(:query_vector AS vector)
            LIMIT :limit
        """

        self.logger.info(
            f"[뉴스 벡터 검색 시작] limit={limit}, "
            f"min_similarity={min_similarity}, model={EMBEDDING_MODEL_NAME}"
        )

        with self.db.get_postgres_db() as session:
            result = session.execute(text(sql), params)
            rows = [dict(row._mapping) for row in result]

        self.logger.info(f"[뉴스 벡터 검색 완료] 검색 결과 {len(rows)}건")

        # DB row를 내부 데이터 객체로 변환해서 이후 JSON 변환을 안정적으로 처리
        return [
            RetrievedNewsChunk(
                chunking_id=str(row["chunking_id"]),
                news_id=str(row["news_id"]) if row.get("news_id") is not None else None,
                news_title=row.get("news_title"),
                publisher_name=row.get("publisher_name"),
                category=row.get("category"),
                published_date=self._format_date(row.get("published_date")),
                url=row.get("url"),
                chunking_text=row.get("chunking_text") or "",
                similarity=float(row["similarity"]),
            )
            for row in rows
        ]

    @staticmethod
    def _to_pgvector_literal(vector: list[float]) -> str:
        # pgvector는 "[0.1,0.2,...]" 형식의 문자열을 vector로 캐스팅할 수 있음
        return "[" + ",".join(str(float(value)) for value in vector) + "]"

    @staticmethod
    def _format_date(value: Any) -> str | None:
        # date/datetime 타입은 JSON에 넣기 쉬운 YYYY-MM-DD 문자열로 변환
        if value is None:
            return None
        if hasattr(value, "strftime"):
            return value.strftime("%Y-%m-%d")
        return str(value)


class NewsRagAnswerService:
    """
    Tool Calling에서 넘어온 사용자 질문을 임베딩하고 관련 뉴스 JSON을 반환한다.
    """

    def __init__(
        self,
        repository: NewsVectorRepository | None = None,
        embedding_model_name: str = EMBEDDING_MODEL_NAME,
    ):
        from sentence_transformers import SentenceTransformer

        self.logger = SetupLogger.get_logger()
        self.repository = repository or NewsVectorRepository()
        self.embedding_model_name = embedding_model_name

        self.logger.info(f"[뉴스 임베딩 모델 로드 시작] model={embedding_model_name}")
        self.embedding_model = SentenceTransformer(embedding_model_name)
        self.logger.info("[뉴스 임베딩 모델 로드 완료]")

    def embed_question(self, question: str) -> list[float]:
        # llm_tool_calling에서 넘어온 원문 질문을 그대로 임베딩
        self.logger.info(f"[질문 임베딩 시작] question={question}")
        return self.embedding_model.encode(
            question,
            normalize_embeddings=True,
            show_progress_bar=False,
        ).tolist()

    def retrieve_news(
        self,
        question: str,
        limit: int = DEFAULT_LIMIT,
        min_similarity: float | None = None,
    ) -> list[RetrievedNewsChunk]:
        # 질문을 먼저 임베딩한 뒤, 유사도 높은 뉴스 청크를 DB에서 조회
        question_embedding = self.embed_question(question)
        news_chunks = self.repository.search_similar_news(
            question_embedding=question_embedding,
            limit=limit,
            min_similarity=min_similarity,
        )
        self.logger.info(f"[관련 뉴스 조회 완료] question={question}, count={len(news_chunks)}")
        return news_chunks

    def ask(
        self,
        question: str,
        limit: int = DEFAULT_LIMIT,
        min_similarity: float | None = None,
    ) -> list[dict[str, Any]]:
        """
        공개 API. stock_llm_analysis.ask()처럼 JSON 직렬화 가능한 list[dict]만 반환한다.
        """
        if not question or not question.strip():
            self.logger.warning("[뉴스 조회 생략] 빈 질문이 입력됨")
            return []

        # Tool Calling에서 호출되는 진입점: 질문 기반 검색 결과만 JSON list로 반환
        news_chunks = self.retrieve_news(
            question=question.strip(),
            limit=limit,
            min_similarity=min_similarity,
        )
        news_data = [news_chunk.to_json_dict() for news_chunk in news_chunks]

        if not news_data:
            self.logger.warning(f"[관련 뉴스 없음] question={question}")
        else:
            self.logger.info(f"[뉴스 JSON 변환 완료] count={len(news_data)}")

        return news_data

    def answer_question(
        self,
        question: str,
        limit: int = DEFAULT_LIMIT,
        min_similarity: float | None = None,
    ) -> dict[str, Any]:
        """
        기존 호출부 호환용. 별도 LLM 답변 생성 없이 검색 결과만 JSON으로 반환한다.
        """
        # 예전 answer_question 호출부가 깨지지 않도록 동일한 검색 결과를 감싸서 반환
        news_data = self.ask(
            question=question,
            limit=limit,
            min_similarity=min_similarity,
        )
        return {
            "question": question,
            "answer": "",
            "retrieved_news": news_data,
        }


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stdin.reconfigure(encoding="utf-8")

    service = NewsRagAnswerService()

    while True:
        try:
            # 단독 테스트용 입력. 실제 서비스 흐름에서는 llm_tool_calling에서 질문이 넘어옴
            question = input("\n질문> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n종료합니다.")
            break

        if not question:
            print("종료합니다.")
            break

        news_data = service.ask(question)
        print(json.dumps(news_data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
