from sqlalchemy import text
from datetime import datetime

from src.database.connect_postgres import PostgresDB
from src.common.common_utils import CommonUtilCodes
from src.common.common_const import CommonConstant
from src.common.setup_log import SetupLogger


class PostgresInsert:
    def __init__(self):
        """
        Posegres DB
        """
        self.logger = SetupLogger.get_logger()
        self.db = PostgresDB()
        self.common_util = CommonUtilCodes()
        self.table_mapping_dict = CommonConstant().table_mapping_dict

    def generate_table_id(self, session, table_name, prefix_str_list, prefix_date):
        """
        테이블 아이디 생성 함수
        :param session: DB 조회/실행을 위한 SQLAlchemy session 객체
        :param table_name: ID를 생성할 대상 테이블명
        :param prefix_str_list: ID 중간에 붙일 구분 문자열
        :param prefix_date: ID에 포함할 날짜 문자열
        :return: 새로 생성된 테이블 ID 문자열
        """
        # table_mapping_dict에서 대상 테이블의 ID 컬럼명 조회 (ex. "news_id", "error_id" 등)
        table_id = self.table_mapping_dict[table_name]["table_id"]

        # table_mapping_dict에서 대상 테이블의 코드값 조회 (ex. "NEWS", "ERR" 등)
        table_code = self.table_mapping_dict[table_name]["table_code"]

        # 순번 자리수 조회 (ex. padding_n=5이면 1 → "00001" 형태로 생성)
        padding_n = self.table_mapping_dict[table_name]["padding_n"]

        # 조회 쿼리 생성
        query = text(f"""
            SELECT COALESCE(MAX(CAST(RIGHT({table_id}, {padding_n}) AS INT)), 0) + 1
            FROM {table_name}
            WHERE {table_id} LIKE :prefix
        """)

        # ID 앞부분 생성 (ex. "NEWSECON20260706")
        id_prefix = f"{table_code}{prefix_str_list}{prefix_date}"

        # LIKE 검색용 prefix 생성 (ex. "NEWSECON20260706%" 같은 prefix로 시작하는 기존 ID를 찾기 위해 사용)
        like_prefix = f"{id_prefix}%"

        # SQL 실행 - prefix만 바인딩 파라미터로 넘김
        result = session.execute(query, {"prefix": like_prefix})

        # 조회 결과에서 다음 순번 값만 가져옴 (ex. 기존 최대 순번이 12이면 seq = 13)
        seq = result.scalar()

        # 최종 ID 생성
        id_sno = str(seq).zfill(padding_n)
        new_table_id = f"{id_prefix}{id_sno}"

        self.logger.debug(f"테이블 ID 생성 완료 - prefix_str: {prefix_str_list}, prefix_date: {prefix_date}, id_sno: {id_sno}")

        return new_table_id

    def insert_data_to_postgres(self, table_name, data_list, collect_type=None):
        """
        공통 INSERT 함수
        :param table_name: INSERT 할 테이블 이름 (str)
        :param data_list: INSERT 할 데이터 리스트
               - [{"collect_id": "C26040701", "data_type": "NEWS", ...},
                  {"collect_id": "C26040702", "data_type": "NEWS", ...}] 형식
        :param collect_type: 데이터 수집 타입 ("BULK" or "INCR"), 기본값 None
        :return: 성공 여부 (bool)
        """
        data_list = self.common_util.check_and_make_list(data_list)

        if data_list is None:
            return False

        with self.db.get_postgres_db() as session:
            try:
                # insert에 필요한 테이블 매핑 정보 추출
                table_id = self.table_mapping_dict[table_name]["table_id"]
                need_collect_id = self.table_mapping_dict[table_name]["need_collect_id"]
                need_table_id = self.table_mapping_dict[table_name]["need_table_id"]
                prefix_col_list = self.table_mapping_dict[table_name].get("prefix_col_list")
                prefix_date_col = self.table_mapping_dict[table_name].get("prefix_date")

                # collect_id 채번이 필요한 경우
                if need_collect_id == "Y":

                    # 최신 collect_id 채번 쿼리 생성
                    collect_id_prefix = f"C{datetime.today().strftime('%y%m%d')}"

                    query = text(f"""
                        SELECT COALESCE(MAX(CAST(RIGHT(collect_id, 2) AS INT)), 0)
                        FROM t_data_collect_log
                        WHERE collect_id LIKE :collect_id_prefix
                    """)

                    result = session.execute(query, {"collect_id_prefix": f"{collect_id_prefix}%"})
                    max_seq = result.scalar()

                    # 새로운 collect_id 생성
                    new_seq = max_seq + 1
                    new_collect_id = f"{collect_id_prefix}{str(new_seq).zfill(2)}"

                    self.logger.info(f"collect_id 생성: {new_collect_id}")

                    self.logger.info(f"{table_name} 데이터 insert 시작")

                else:
                    new_collect_id = None

                insert_cnt = 0

                for data in data_list:
                    # table id 생성에 필요한 경우, 관련 정보 추출
                    if need_table_id == "Y":

                        # 1) prefix 문자열 생성 (ex. news_id는 수집소스(N/R) + 언론사(M/H/K) 정보 사용)
                        if prefix_col_list:
                            prefix_str_list =[data[prefix_col][0] for prefix_col in prefix_col_list]
                            prefix_str_list = "".join(prefix_str_list)
                        else:
                            prefix_str_list = ""

                        # 2) prefix 날짜 생성 (ex. news_id는 발행일자 정보 사용)
                        if prefix_date_col:
                            prefix_date = datetime.strptime(data[prefix_date_col], "%Y-%m-%d").strftime("%y%m%d")
                        else:
                            prefix_date = datetime.now().strftime("%y%m%d")

                        # PK ID 생성 후 data에 추가
                        new_table_id = self.generate_table_id(session, table_name, prefix_str_list, prefix_date)
                        data[table_id] = new_table_id

                        # 새로 생성된 collect_id가 있을 경우, data에 추가
                        if new_collect_id is not None:
                            data["collect_id"] = new_collect_id


                    # 현재 data 기준으로 컬럼/placeholder 생성
                    columns = ", ".join(data.keys())  # ("collect_id, data_type, ..." 형식)

                    # 컬럼명 리스트에 해당 컬럼이 있으면 (":collect_id, :data_type", ...) 형식으로 연결
                    # SQLAlchemy가 자동으로 :collect_id → "C26040701", :data_type → "NEWS" 이런식으로 매핑(session.execute)
                    placeholders = ", ".join([f":{key}" for key in data.keys()])

                    # insert 쿼리 생성
                    # - t_news_data 테이블은 conflict_query 추가
                    conflict_query = ""

                    if table_name == "t_news_data":
                        conflict_query = "ON CONFLICT (url) DO NOTHING"

                    query = text(f"""
                    INSERT INTO {table_name} ({columns})
                    VALUES ({placeholders})
                            {conflict_query} 
                    """)

                    self.logger.debug(f"insert 쿼리 = {query}")
                    self.logger.debug(f"insert 데이터 = {data}")

                    # 한 건씩 insert
                    session.execute(query, data)
                    insert_cnt += 1

                self.logger.info(f"{table_name} - 총 {insert_cnt}건 insert 완료")

                # 새로 생성된 collect_id가 있을 경우, t_data_collect_log 테이블에 수집 정보를 insert
                if new_collect_id is not None:
                    collect_log_insert_query = text("""
                        INSERT INTO t_data_collect_log (
                            collect_id,
                            data_type,
                            collect_date,
                            collect_type,
                            collect_tot_cnt
                        )
                        VALUES (
                            :collect_id,
                            :data_type,
                            :collect_date,
                            :collect_type,
                            :collect_tot_cnt
                        )
                    """)

                    session.execute(collect_log_insert_query, {
                        "collect_id": new_collect_id,
                        "data_type": table_id.split("_")[0].upper(),
                        "collect_date": datetime.today().strftime("%Y-%m-%d"),
                        "collect_type": collect_type,
                        "collect_tot_cnt": insert_cnt
                    })

                    self.logger.info(f"t_data_collect_log insert 완료 - collect_id: {new_collect_id}")

                session.commit()
                return True

            except Exception as e:
                session.rollback()
                self.logger.error(f"{table_name}- 데이터 insert 실패 - Error: {str(e)}", exc_info=True, stack_info=True)
                raise e

"""
--------------------------------------------------클래스 구분선-----------------------------------------------------------
"""

class PostgresUpdate:
    def __init__(self):
        """
        Posegres DB
        """
        self.logger = SetupLogger.get_logger()
        self.db = PostgresDB()
        self.common_util = CommonUtilCodes()
        self.table_mapping_dict = CommonConstant().table_mapping_dict

    def update_data_to_postgres(self, table_name, data_list, update_col_nm=None, update_value=None):
        """
        공통 UPDATE 함수

        사용 예시 1) 여러 column 동시 업데이트
            data_list = [
                {"NRM260706000101": {"embedding_yn": "1"}},
                {"NRM260706000102": {"embedding_yn": "1"}}
            ]

        사용 예시 2) 단일 column 동일 값 업데이트
            update_col_nm = "del_yn"
            update_value = "1"
            data_list = ["NRM260706000101", "NRM260706000102"]

        :param table_name: UPDATE 할 테이블 이름 (str)
        :param data_list: UPDATE 할 데이터 (str)
        :param update_col_nm: UPDATE 할 컬럼 이름 (None)
        :param update_value: UPDATE 할 값 (None)
        :return: 성공 여부 (bool)
        """
        data_list = self.common_util.check_and_make_list(data_list)

        if data_list is None:
            return False

        with self.db.get_postgres_db() as session:
            try:
                # 업데이트 할 테이블의 키 값이 되는 컬럼 이름 추출
                key_column = self.table_mapping_dict[table_name]["table_id"]

                for data in data_list:

                    # case 1. update_col_nm, update_value의 값이 None이 아닐 경우, 단일 컬럼 업데이트 방식으로 동작
                    if update_col_nm and update_value is not None:
                        primary_key = data
                        update_data = {update_col_nm: update_value}

                    # case 2. 여러 컬럼 동시 업데이트 방식으로 동작
                    else:
                        primary_key = list(data.keys())[0]
                        update_data = data[primary_key]

                    # SET 절 생성
                    set_clause = ", ".join([
                        f"{col} = :{col}" for col in update_data.keys()
                    ])
                    set_clause += ", updated_dt = NOW()"

                    query = text(f"""
                        UPDATE {table_name}
                        SET {set_clause}
                        WHERE {key_column} = :data_id
                    """)

                    params = update_data.copy()
                    params["data_id"] = primary_key

                    result = session.execute(query, params)

                    if result.rowcount == 0:
                        self.logger.warning(f"{primary_key} 데이터가 존재하지 않습니다.")

                session.commit()
                self.logger.info(f"{table_name}  업데이트 완료)")
                return True

            except Exception as e:
                session.rollback()
                self.logger.error(f"{table_name} 업데이트 실패 - Error: {str(e)}",
                                  exc_info=True, stack_info=True)
                raise e

    def update_vector_to_postgres(self, table_name, chunking_id, update_data):
        """
        공통 UPDATE 함수 (단일 row의 여러 컬럼 동시 업데이트)
        :param table_name: UPDATE 할 테이블 이름 (str)
        :param chunking_id: UPDATE 할 데이터 row의 ID (str)
        :param update_data: UPDATE 할 컬럼-값 딕셔너리 (dict)
               - {"embedding_model": "KURE-v1",
                  "embedding_vector": "[0.123, 0.456, ...]",
                  "embedding_yn": True} 형식
        :return: 성공 여부 (bool)
        """
        if not update_data:
            self.logger.warning("업데이트할 데이터가 없습니다.")
            return False

        with self.db.get_postgres_db() as session:
            try:
                # 업데이트 할 테이블의 키 값이 되는 컬럼 이름 추출
                key_column = self.table_mapping_dict[table_name]["table_id"]

                # SET절 생성 ("embedding_model = :embedding_model, ..." 형식)
                set_clause = ", ".join([f"{col} = :{col}" for col in update_data.keys()])

                # update 쿼리 생성
                query = text(f"""
                      UPDATE {table_name}
                      SET {set_clause},
                          updated_dt = NOW()
                      WHERE {key_column} = :chunking_id
                  """)

                # 쿼리 파라미터 생성 (update_data + data_id)
                params = dict(update_data)
                params["chunking_id"] = chunking_id

                result = session.execute(query, params)

                # 업데이트 대상 row가 없는 경우 경고
                if result.rowcount == 0:
                    self.logger.warning(f"{key_column}={chunking_id} - 업데이트 대상 없음")

                session.commit()
                self.logger.info(f"{key_column}={chunking_id} - {list(update_data.keys())} 업데이트 완료")
                return True

            except Exception as e:
                session.rollback()
                self.logger.error(f"{key_column}={chunking_id} - 업데이트 실패 - Error: {str(e)}",
                exc_info = True, stack_info = True)
                raise e



if __name__ == "__main__":
    data_list = [{"NRM260627005104":{"embedding_yn":"1", "embedding_model": "test"}},
                 {"NRM260627005103":{"embedding_yn":"1", "embedding_model": "test"}}]

    # data_list = ["NRM260627005104", "NRM260627005103"]

    # data_list = [
    #     {'chunking_id': 'NRM260706000101',
    #      'chunking_index': 1,
    #      "news_title":'은지美·이란 2차협상 낙관론에...美증시 전쟁낙폭 만회 [월가월부]',
    #      "category": '경제',
    #      'published_date': '2026-04-15',
    #      'url': 'https://www.mk.co.kr/article/12017153',
    #      'chunking_text': "메타·엔비디아 등 기술주 반등 견인\n협상 기대감에 브렌트·WTI 급락\n이번주 파키스탄서 2차 협상 전망\nPPI 소폭 상승에 인플레 부담 완화"}
    # ]
    postgres_update = PostgresUpdate()
    postgres_update.update_data_to_postgres("t_vector_data", data_list)
