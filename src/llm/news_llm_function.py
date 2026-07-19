from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

EMBEDDING_MODEL_NAME = "nlpai-lab/KURE-v1"

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:1.5b")
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "180"))
OLLAMA_NUM_PREDICT = int(os.getenv("OLLAMA_NUM_PREDICT", "768"))

# 여기만 바꿔서 테스트하면 됩니다.
USER_QUESTION = "삼성전자 AI 투자 관련 최근 뉴스 알려줘"
USER_LIMIT = 5
USER_MIN_SIMILARITY = None


@dataclass
class RetrievedNewsChunk:
    """
    벡터 DB에서 검색된 뉴스 청크 객체

    저장 내용:
    - 뉴스 제목
    - 본문 청크
    - 유사도
    - URL
    - 발행일
    """
    chunking_id: str
    news_id: str | None
    news_title: str | None
    category: str | None
    published_date: str | None
    url: str | None
    chunking_text: str
    similarity: float

    def to_context_dict(self) -> dict[str, Any]:
        """
        뉴스 청크를 Ollama 입력용 Dictionary로 변환

        처리 내용:
        1. 객체 → Dictionary 변환
        2. similarity 반올림
        3. LLM 입력용 데이터 생성

        :return: Dictionary 형태 뉴스 정보
        """
        return {
            "chunking_id": self.chunking_id,
            "news_id": self.news_id,
            "news_title": self.news_title,
            "category": self.category,
            "published_date": self.published_date,
            "url": self.url,
            "similarity": round(self.similarity, 4),
            "chunking_text": self.chunking_text,
        }


class NewsVectorRepository:
    """
    뉴스 벡터 DB 조회를 담당하는 클래스

    처리 내용:
    1. PostgreSQL 연결
    2. 질문과 유사한 뉴스 검색
    3. 검색 결과 객체 변환
    """
    def __init__(self, db: Any | None = None):
        """
        Repository 초기화

        처리 내용:
        1. PostgreSQL 연결 객체 생성
        2. DB 객체 저장

        :param db: PostgreSQL 연결 객체
        """
        if db is None:
            from src.database.connect_postgres import PostgresDB

            db = PostgresDB()

        self.db = db

    def search_similar_news(
            self,
            question_embedding: list[float],
            limit: int = 5,
            min_similarity: float | None = None,
    ) -> list[RetrievedNewsChunk]:
        """
        질문과 유사한 뉴스 검색

        처리 흐름:
        1. 질문 임베딩을 pgvector 형식으로 변환
        2. 벡터 유사도 검색
        3. 유사도 순 정렬
        4. 검색 결과 반환

        :param question_embedding: 질문 임베딩 벡터
        :param limit: 검색할 뉴스 개수
        :param min_similarity: 최소 유사도
        :return: 검색된 뉴스 리스트
        """
        from sqlalchemy import text

        query_vector = self._to_pgvector_literal(question_embedding)

        sql = """
              SELECT chunking_id,
                     news_id,
                     news_title,
                     category,
                     published_date,
                     url,
                     chunking_text,
                     1 - (embedding_vector <=> CAST(:query_vector AS vector)) AS similarity
              FROM t_vector_data
              WHERE embedding_yn = TRUE
                AND embedding_vector IS NOT NULL
                AND embedding_model = :embedding_model
                AND COALESCE(del_yn, FALSE) = FALSE 
              """

        params: dict[str, Any] = {
            "query_vector": query_vector,
            "embedding_model": EMBEDDING_MODEL_NAME,
            "limit": limit,
        }

        if min_similarity is not None:
            sql += """
              AND 1 - (embedding_vector <=> CAST(:query_vector AS vector)) >= :min_similarity
            """
            params["min_similarity"] = min_similarity

        sql += """
            ORDER BY embedding_vector <=> CAST(:query_vector AS vector)
            LIMIT :limit
        """

        with self.db.get_postgres_db() as session:
            result = session.execute(text(sql), params)
            rows = [dict(row._mapping) for row in result]

        return [
            RetrievedNewsChunk(
                chunking_id=str(row["chunking_id"]),
                news_id=str(row["news_id"]) if row.get("news_id") is not None else None,
                news_title=row.get("news_title"),
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
        """
        Python 리스트를 pgvector 문자열로 변환

        처리 내용:
        1. float 리스트를 문자열로 변환
        2. pgvector 형식([1,2,3]) 생성

        :param vector: 임베딩 벡터
        :return: pgvector 문자열
        """
        return "[" + ",".join(str(float(value)) for value in vector) + "]"

    @staticmethod
    def _format_date(value: Any) -> str | None:
        """
        날짜 데이터를 문자열로 변환

        처리 내용:
        1. None 처리
        2. datetime → YYYY-MM-DD 변환
        3. 문자열 반환

        :param value: 날짜 데이터
        :return: 날짜 문자열
        """
        if value is None:
            return None
        if hasattr(value, "strftime"):
            return value.strftime("%Y-%m-%d")
        return str(value)


class NewsRagAnswerService:
    """
    뉴스 RAG 전체 실행을 담당하는 서비스 클래스

    처리 내용:
    1. 임베딩 모델 로드
    2. 사용자 질문 임베딩
    3. 유사 뉴스 검색
    4. Ollama 기반 답변 생성
    """
    def __init__(
            self,
            repository: NewsVectorRepository | None = None,
            embedding_model_name: str = EMBEDDING_MODEL_NAME,
    ):
        """
        뉴스 RAG 서비스 초기화

        처리 내용:
        1. 뉴스 Repository 생성
        2. 임베딩 모델명 저장
        3. SentenceTransformer 모델 로드

        :param repository: 뉴스 벡터 조회 객체
        :param embedding_model_name: 사용할 임베딩 모델명
        """
        from sentence_transformers import SentenceTransformer

        self.repository = repository or NewsVectorRepository()
        self.embedding_model_name = embedding_model_name
        self.embedding_model = SentenceTransformer(embedding_model_name)

    def embed_question(self, question: str) -> list[float]:
        """
        사용자 질문을 임베딩 벡터로 변환

        처리 흐름:
        1. 질문 문자열 입력
        2. SentenceTransformer 임베딩 수행
        3. 정규화된 벡터 반환

        :param question: 사용자 질문
        :return: 질문 임베딩 벡터
        """
        return self.embedding_model.encode(
            question,
            normalize_embeddings=True,  ## 백터 길이 정규화
            show_progress_bar=False,    ## 진행 바 표시x
        ).tolist()

    def retrieve_news(
            self,
            question: str,
            limit: int = 5,
            min_similarity: float | None = None,
    ) -> list[RetrievedNewsChunk]:
        """
        질문과 유사한 뉴스 검색

        처리 흐름:
        1. 사용자 질문 임베딩
        2. 벡터 DB 유사도 검색
        3. 검색된 뉴스 리스트 반환

        :param question: 사용자 질문
        :param limit: 검색할 뉴스 개수
        :param min_similarity: 최소 유사도
        :return: 검색된 뉴스 리스트
        """
        question_embedding = self.embed_question(question)
        return self.repository.search_similar_news(
            question_embedding=question_embedding,
            limit=limit,
            min_similarity=min_similarity,
        )

    def answer_question(
            self,
            question: str,
            limit: int = 5,
            min_similarity: float | None = None,
    ) -> dict[str, Any]:
        """
        뉴스 데이터를 기반으로 사용자 질문에 답변

        처리 흐름:
        1. 질문과 관련된 뉴스 검색
        2. 검색 결과 존재 여부 확인
        3. 검색된 뉴스를 Ollama에 전달
        4. 답변과 근거 뉴스 반환

        :param question: 사용자 질문
        :param limit: 검색할 뉴스 개수
        :param min_similarity: 최소 유사도
        :return: 질문, 답변, 검색 뉴스 정보
        """
        retrieved_news = self.retrieve_news(
            question=question,
            limit=limit,
            min_similarity=min_similarity,
        )

        if not retrieved_news:
            return {
                "question": question,
                "answer": "관련도가 충분한 뉴스 데이터를 찾지 못했습니다.",
                "retrieved_news": [],
            }

        answer = call_ollama_for_news_answer(question, retrieved_news)

        return {
            "question": question,
            "answer": answer,
            "retrieved_news": [
                news_chunk.to_context_dict()
                for news_chunk in retrieved_news
            ],
        }


def call_ollama_for_news_answer(
        question: str,
        retrieved_news: list[RetrievedNewsChunk],
) -> str:
    import requests

    system_prompt = """
너는 금융 뉴스 RAG 답변을 작성하는 한국어 어시스턴트다.
반드시 제공된 뉴스 컨텍스트만 근거로 답한다.
확인되지 않은 사실, 투자 추천, 수익 보장 표현은 하지 않는다.
답변은 다음 형식을 지킨다.

1. 핵심 답변: 질문에 직접 답하는 2~4문장
2. 근거 뉴스: 관련 뉴스 제목과 날짜를 짧게 정리
3. 참고: 데이터만으로 확정하기 어려운 부분
""".strip()

    context = [
        news_chunk.to_context_dict()
        for news_chunk in retrieved_news
    ]

    user_prompt = f"""
사용자 질문:
{question}

검색된 뉴스 컨텍스트:
{json.dumps(context, ensure_ascii=False, indent=2)}

위 뉴스 컨텍스트만 근거로 질문에 답해줘.
""".strip()

    payload = {
        "model": OLLAMA_MODEL,
        "stream": False,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "options": {
            "temperature": 0.2, #창의성(거의 사실 위주)
            "num_predict": OLLAMA_NUM_PREDICT,  #최대 생성 토큰
        },
    }

    try:
        response = requests.post(
            f"{OLLAMA_HOST}/api/chat",
            json=payload,
            timeout=OLLAMA_TIMEOUT,
        )
    except requests.exceptions.ReadTimeout as exc:
        raise RuntimeError(
            f"Ollama answer timed out after {OLLAMA_TIMEOUT} seconds. "
            "Try a smaller model or increase OLLAMA_TIMEOUT."
        ) from exc

    if response.status_code == 404:
        response = requests.post(
            f"{OLLAMA_HOST}/api/generate",
            json={
                "model": OLLAMA_MODEL,
                "stream": False,
                "prompt": f"{system_prompt}\n\n{user_prompt}",
                "options": {
                    "temperature": 0.2,
                    "num_predict": OLLAMA_NUM_PREDICT,
                },
            },
            timeout=OLLAMA_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()["response"].strip()

    response.raise_for_status()
    return response.json()["message"]["content"].strip()


def main() -> None:
    question = USER_QUESTION.strip()

    if not question:
        raise ValueError("USER_QUESTION에 질문을 입력해주세요.")

    print(f"[question] {question}")
    print(f"[embedding] model={EMBEDDING_MODEL_NAME}")
    print(f"[ollama] host={OLLAMA_HOST}, model={OLLAMA_MODEL}")

    service = NewsRagAnswerService()
    result = service.answer_question(
        question=question,
        limit=USER_LIMIT,
        min_similarity=USER_MIN_SIMILARITY,
    )

    print("[answer]")
    print(result["answer"])

    print("[retrieved_news]")
    for news_chunk in result["retrieved_news"]:
        print(
            "- "
            f"similarity={news_chunk['similarity']} | "
            f"{news_chunk['published_date']} | "
            f"{news_chunk['news_title']} | "
            f"{news_chunk['url']}"
        )


if __name__ == "__main__":
    main()
