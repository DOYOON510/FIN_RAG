from src.database.connect_postgres import PostgresDB
from src.common.common_utils import CommonUtilCodes
from src.common.setup_log import SetupLogger
from sqlalchemy import text

class PostgresInsert:

    def __init__(self):
        self.db = PostgresDB()
        self.logger = SetupLogger.get_logger()
        self.common_util = CommonUtilCodes()

    def insert_vector_data(self, data_list):
        """
        벡터 데이터 INSERT
        """

        data_list = self.common_util.check_and_make_list(data_list)

        if not data_list:
            self.logger.warning("INSERT 대상 벡터 데이터 없음")
            return False

        try:
            with self.db.get_postgres_db() as session:

                insert_cnt = 0

                for data in data_list:

                    columns = ", ".join(data.keys())
                    placeholders = ", ".join(
                        [f":{key}" for key in data.keys()]
                    )

                    insert_query = text(f"""
                        INSERT INTO t_vector_data
                        ({columns})
                        VALUES
                        ({placeholders})
                    """)

                    session.execute(insert_query, data)

                    insert_cnt += 1

                self.logger.info(
                    f"t_vector_data 총 {insert_cnt}건 INSERT 완료"
                )

                return True

        except Exception as e:
            self.logger.error(
                f"t_vector_data INSERT 실패 - {str(e)}",
                exc_info=True
            )
            raise


if __name__ == "__main__":

    postgres_insert = PostgresInsert()

    # 테스트용 임베딩 벡터 (1024차원)
    sample_vector = [0.1] * 1024

    test_data = {
        "chunking_id": "TEST_1",
        "chunking_index": 0,
        "news_title": "테스트 뉴스",
        "category": "IT",
        "published_date": "2026-06-25",
        "url": "https://test.com",
        "chunking_text": "벡터 저장 테스트",
        "embedding_model": "BAAI/bge-m3",
        "embedding_vector": sample_vector,
        "embedding_yn": True,
        "del_yn": False
    }

    postgres_insert.insert_vector_data(test_data)

    print("테스트 완료")