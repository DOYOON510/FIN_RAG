from logging import debug
from sqlalchemy import text
from datetime import datetime

from src.database.connect_postgres import PostgresDB
from src.common.common_utils import CommonUtilCodes
from src.common.common_const import CommonConstant

class PostgresInsert:
    def __init__(self):
        """
        Posegres DB
        """
        # self.logger = SetupLogger.get_logger()
        # self.common_util = CommonUtilCodes()
        self.db = PostgresDB()
        self.common_util = CommonUtilCodes()
        self.table_mapping_dict = CommonConstant().table_mapping_dict

    def generate_table_id(self, session, table_name, prefix_col, prefix_date):
        table_id = self.table_mapping_dict[table_name]["table_id"]
        table_code = self.table_mapping_dict[table_name]["table_code"]
        padding_n = self.table_mapping_dict[table_name]["padding_n"]

        query = text(f"""
            SELECT COALESCE(MAX(CAST(RIGHT({table_id}, {padding_n}) AS INT)), 0) + 1
            FROM {table_name}
            WHERE {table_id} LIKE :prefix
        """)

        id_prefix = f"{table_code}{prefix_col}{prefix_date}"
        like_prefix = f"{id_prefix}%"

        result = session.execute(query, {"table_id":table_id, "padding_n": padding_n, "table_name": table_name, "prefix": like_prefix})
        seq = result.scalar()
        new_table_id = f"{id_prefix}{str(seq).zfill(padding_n)}"

        return new_table_id

    def insert_data_to_postgres(self, table_name, data_list):
        """
        공통 INSERT 함수
        :param table_name: INSERT 할 테이블 이름 (str)
        :param data_list: INSERT 할 데이터 리스트
               - [{"collect_id": "C26040701", "data_type": "NEWS", ...},
                  {"collect_id": "C26040702", "data_type": "NEWS", ...}] 형식
        :return: 성공 여부 (bool)
        """
        data_list = self.common_util.check_and_make_list(data_list)
        if data_list is None:
            return False

        with self.db.get_postgres_db() as session:
            try:
                prefix_col_list = self.table_mapping_dict[table_name]["prefix_col_list"]
                prefix_date_col = self.table_mapping_dict[table_name]["prefix_date"]
                for data in data_list:
                    # session, table_name, prefix_col, prefix_date
                    if prefix_col_list:
                        prefix_str_list =[data[prefix_col][0] for prefix_col in prefix_col_list]
                        prefix_str_list = "".join(prefix_str_list)
                    else:
                        prefix_str_list = None
                    if prefix_date_col:
                        prefix_date = datetime.strptime(data[prefix_date_col], "%Y-%m-%d").strftime("%y%m%d")
                    else:
                        prefix_date = datetime.now().strftime("%y%m%d")
                    new_table_id = self.generate_table_id(session, table_name, prefix_str_list, prefix_date)
                    table_id = self.table_mapping_dict[table_name]["table_id"]
                    data[table_id] = new_table_id

                # 첫번째 데이터 리스트에서 컬럼명 뽑아오기 ("collect_id, data_type, ..." 형식)
                columns = ", ".join(data_list[0].keys())

                # 컬럼명 리스트에 해당 컬럼이 있으면 (":collect_id, :data_type", ...) 형식으로 연결
                # SQLAlchemy가 자동으로 :collect_id → "C26040701", :data_type → "NEWS" 이런식으로 매핑(session.execute)
                placeholders = ", ".join([f":{key}" for key in data_list[0].keys()])

                # insert 쿼리 생성
                query = text(f"""
                    INSERT INTO {table_name} ({columns})
                    VALUES ({placeholders})
                """)
                session.execute(query, data_list)
                session.commit()
                return True

            except Exception as e:
                session.rollback()
                raise e

    # def test_connection(self):
    #     with self.db.get_postgres_db() as session:
    #         result = session.execute(text("SELECT 1"))
    #         print(result.fetchone())

if __name__ == "__main__":
    from datetime import datetime

    from datetime import datetime

    data_list = [
        {
            "collect_id": "C26040701",
            "source_type": "NAVER",
            "news_title": "금리 인상 전망에 따른 국내 증시 변동성 확대",
            "publisher_name": "H",
            "category": "경제",
            "published_date": "2026-04-07",
            "contents": "한국은행의 금리 인상 가능성이 제기되면서 국내 증시에 변동성이 커지고 있다.",
            "url": "https://news.example.com/article1",
        },
        {
            "collect_id": "C26040701",
            "source_type": "RSS",
            "news_title": "AI 산업 성장 기대감에 IT 기업 주가 상승",
            "publisher_name": "M",
            "category": "IT",
            "published_date": "2026-04-07",
            "contents": "AI 관련 기술 발전으로 인해 IT 기업들의 주가가 상승세를 보이고 있다.",
            "url": "https://news.example.com/article2",

        }
    ]
    postgres_insert = PostgresInsert()
    postgres_insert.insert_data_to_postgres("t_news_data", data_list)


