import time
import unittest

# import pandas as pd
import csv
from sqlalchemy import text
from src.database.connect_postgres import PostgresDB
from src.common.setup_log import SetupLogger
from sentence_transformers import SentenceTransformer
from src.common.common_const import EbeddingTestQuery
from sklearn.metrics.pairwise import cosine_similarity

class TestEmbeddingModels:
    """
    임베딩 모델 테스트 클래스
    """

    def __init__(self):
        self.logger = SetupLogger.get_logger()
        self.db = PostgresDB()
        self.test_query_dict = EbeddingTestQuery.test_query_dict
        self.model_dict = {
            "BGE-M3": "BAAI/bge-m3",
            "KURE-v1": "nlpai-lab/KURE-v1",
            "Qwen3-0.6B": "Qwen/Qwen3-Embedding-0.6B",
        }

    def get_test_news_data(self):
        """
        테스트에 필요한 뉴스데이터 조회하는 함수
        :return:
        """
        with self.db.get_postgres_db() as session:
            try:
                query = text(f"""
                    SELECT news_id, news_title, contents
                    FROM t_news_data
                    ORDER BY created_dt DESC
                    LIMIT 1000;
                """)

                result = session.execute(query)
                rows = result.mappings().all()

                self.logger.info(f"t_news_data 조회 완료")
                return rows

            except Exception as e:
                session.rollback()
                self.logger.error(f"t_news_data 조회 실패 - Error: {str(e)}", exc_info=True, stack_info=True)
                raise e

    def make_documents(self, news_data):
        """
        뉴스 데이터를 임베딩용 문서 형태로 변환
        """
        documents = [
            f"제목: {news['news_title']}\n본문: {news['contents']}"
            for news in news_data
        ]

        return documents

    def run_model_test(self, model_name, model_path, news_data, documents):
        """
        단일 임베딩 모델 테스트
        """
        print(f"\n{'=' * 80}")
        print(f"모델 테스트 시작: {model_name}")
        print(f"{'=' * 80}")

        start_time = time.time()

        model = SentenceTransformer(model_path)

        embeddings = model.encode(
            documents,
            normalize_embeddings=True,
            show_progress_bar=True
        )

        result_rows = []

        for query_name, query in self.test_query_dict.items():

            query_embedding = model.encode(
                [query],
                normalize_embeddings=True
            )

            scores = cosine_similarity(
                query_embedding,
                embeddings
            )[0]

            top_indices = scores.argsort()[::-1][:5]

            print(f"\n[{model_name}] {query_name}: {query}")

            for rank, idx in enumerate(top_indices, start=1):
                news = news_data[idx]
                score = float(scores[idx])

                print(
                    f"{rank}. {score:.4f} | "
                    f"{news['news_id']} | "
                    f"{news['news_title']}"
                )

                result_rows.append({
                    "model_name": model_name,
                    "query_name": query_name,
                    "query": query,
                    "rank": rank,
                    "news_id": news["news_id"],
                    "news_title": news["news_title"],
                    "score": score,
                })

        elapsed_time = time.time() - start_time
        print(f"\n{model_name} 완료 - 소요시간: {elapsed_time:.2f}초")

        return result_rows

    def save_results_to_csv(self, result_rows, output_path):
        """
        결과 CSV 저장
        """

        fieldnames = [
            "model_name",
            "query_name",
            "query",
            "rank",
            "news_id",
            "news_title",
            "score",
        ]

        with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(result_rows)

        print(f"\n결과 저장 완료: {output_path}")

    def run_all_tests(self):
        """
        전체 모델 테스트 실행
        """

        news_data = self.get_test_news_data()
        documents = self.make_documents(news_data)

        all_result_rows = []

        for model_name, model_path in self.model_dict.items():
            result_rows = self.run_model_test(
                model_name=model_name,
                model_path=model_path,
                news_data=news_data,
                documents=documents
            )

            all_result_rows.extend(result_rows)

        self.save_results_to_csv(
            result_rows=all_result_rows,
            output_path="embedding_model_test_result.csv"
        )

if __name__ == "__main__":
    tester = TestEmbeddingModels()
    tester.run_all_tests()