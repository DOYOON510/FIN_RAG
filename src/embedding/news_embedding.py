import time
from sqlalchemy import text
from sentence_transformers import SentenceTransformer

from src.database.connect_postgres import PostgresDB
from src.common.setup_log import SetupLogger
from src.database.postgres_common import PostgresUpdate

class EmbeddingNewsData:
    """
    뉴스 데이터 임베딩 클래스
    """

    def __init__(self):
        self.logger = SetupLogger.get_logger()
        self.db = PostgresDB()
        self.postgres_update = PostgresUpdate()
        self.model_name = "nlpai-lab/KURE-v1"

    def get_news_chunk_data(self):
        """
        임베딩이 필요한 뉴스 청킹 데이터를 조회하는 함수
        :return:
        """
        with self.db.get_postgres_db() as session:
            try:
                query = text(f"""
                    SELECT chunking_id, chunking_text
                    FROM t_vector_data
                """)

                result = session.execute(query)
                rows = result.mappings().all()
                rows = rows[:100]

                self.logger.info(f"t_vector_data - 청킹 데이터 {len(rows)}건 조회 완료")
                return rows

            except Exception as e:
                session.rollback()
                self.logger.error(f"t_vector_data - 청킹 데이터 조회 실패 - Error: {str(e)}", exc_info=True, stack_info=True)
                raise e

    def run_embedding(self, news_chunk_data):
        """
        임베딩
        """
        print(f"\n{'=' * 80}")
        print(f"임베딩 모델 로드: {self.model_name}")
        print(f"{'=' * 80}")

        start_time = time.time()

        model = SentenceTransformer(self.model_name)

        embedding_result_list = []
        for chunking_data in news_chunk_data:
            chunking_id = chunking_data["chunking_id"]
            chunking_text = chunking_data["chunking_text"]

            embedding_vector = model.encode(
                chunking_text,
                normalize_embeddings=True,
                show_progress_bar=True
            ).tolist()

            embedding_result_list.append({
                chunking_id: {
                    "embedding_model": self.model_name,
                    "embedding_vector": embedding_vector,
                    "embedding_yn": True
                }
            })

            print(embedding_result_list)

        self.postgres_update.update_data_to_postgres("t_vector_data", embedding_result_list)

        elapsed_time = time.time() - start_time
        print(f"\n 완료 - 소요시간: {elapsed_time:.2f}초")

        # return embeddings

    def run(self):
        """
        전체 모델 테스트 실행
        """

        news_chunk_data = self.get_news_chunk_data()

        self.run_embedding(news_chunk_data)

if __name__ == "__main__":
    embedding_news_data = EmbeddingNewsData()
    embedding_news_data.run()