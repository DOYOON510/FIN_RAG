import time
from sqlalchemy import text
from sentence_transformers import SentenceTransformer
from tqdm import tqdm
import math

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
                    WHERE embedding_yn = False
                """)

                result = session.execute(query)
                rows = result.mappings().all()

                self.logger.info(f"t_vector_data - 청킹 데이터 {len(rows)}건 조회 완료")
                return rows

            except Exception as e:
                session.rollback()
                self.logger.error(f"t_vector_data - 청킹 데이터 조회 실패 - Error: {str(e)}", exc_info=True, stack_info=True)
                raise e

    def run_embedding(self, model, news_chunk_data):
        """
        임베딩 모델 실행
        """
        start_time = time.time()
        embedding_result_list = []

        for chunking_data in tqdm(news_chunk_data):
            chunking_id = chunking_data["chunking_id"]
            chunking_text = chunking_data["chunking_text"]
            self.logger.debug(f"{chunking_id} - 임베딩 시작")

            # 임베딩 모델 실행
            embedding_vector = model.encode(
                chunking_text,
                normalize_embeddings=True,
                show_progress_bar=False
            ).tolist()

            # DB Update 함수의 input 형태로 data append
            embedding_result_list.append({
                chunking_id: {
                    "embedding_model": self.model_name,
                    "embedding_vector": embedding_vector,
                    "embedding_yn": True
                }
            })

        # t_vector_data 테이블 Update
        self.postgres_update.update_data_to_postgres("t_vector_data", embedding_result_list)

        elapsed_time = time.time() - start_time
        self.logger.info(f"\n 임베딩 완료 - 소요시간: {elapsed_time:.2f}초")

        return True

    def run(self, batch_size):
        """
        임베딩 배치 실행 코드
        """
        news_chunk_data = self.get_news_chunk_data()

        if not news_chunk_data:
            self.logger.warning("임베딩 대상 데이터가 없습니다.")
            return True

        self.logger.info(f"임베딩 모델 로드 및 시작: {self.model_name}")
        model = SentenceTransformer(self.model_name)

        total_count = len(news_chunk_data)
        total_batch = math.ceil(total_count / batch_size)

        # 조회한 데이터를 batch_size 단위로 나누어 순차적으로 임베딩 수행
        for batch_no, start_index in enumerate(range(0, total_count, batch_size), start=1):
            batch_data = news_chunk_data[
                         start_index:start_index + batch_size
                         ]

            end_index = min(start_index + len(batch_data), total_count)

            self.logger.info(
                f"임베딩 배치 시작 ({batch_no}/{total_batch}) "
                f"- {start_index + 1} ~ {end_index} / {total_count}건"
            )

            self.run_embedding(model, batch_data)

            self.logger.info(
                f"임베딩 배치 완료 ({batch_no}/{total_batch})"
            )

        return True


if __name__ == "__main__":
    embedding_news_data = EmbeddingNewsData()
    embedding_news_data.run(500)