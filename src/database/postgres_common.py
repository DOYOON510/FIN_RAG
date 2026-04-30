from logging import debug
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
        table_id = self.table_mapping_dict[table_name]["table_id"]
        table_code = self.table_mapping_dict[table_name]["table_code"]
        padding_n = self.table_mapping_dict[table_name]["padding_n"]

        query = text(f"""
            SELECT COALESCE(MAX(CAST(RIGHT({table_id}, {padding_n}) AS INT)), 0) + 1
            FROM {table_name}
            WHERE {table_id} LIKE :prefix
        """)

        id_prefix = f"{table_code}{prefix_str_list}{prefix_date}"
        like_prefix = f"{id_prefix}%"

        result = session.execute(query, {"table_id": table_id, "padding_n": padding_n, "table_name": table_name, "prefix": like_prefix})
        seq = result.scalar()
        id_sno = str(seq).zfill(padding_n)
        new_table_id = f"{id_prefix}{id_sno}"
        self.logger.debug(f"테이블 ID 생성 완료 - prefix_str: {prefix_str_list}, prefix_date: {prefix_date}, id_sno: {id_sno}")
        return new_table_id

    def insert_data_to_postgres(self, table_name, data_list, collect_type):
        """
        공통 INSERT 함수
        :param table_name: INSERT 할 테이블 이름 (str)
        :param data_list: INSERT 할 데이터 리스트
               - [{"collect_id": "C26040701", "data_type": "NEWS", ...},
                  {"collect_id": "C26040702", "data_type": "NEWS", ...}] 형식
        :param collect_type: 데이터 수집 타입 ("BULK" or "INCR")
        :return: 성공 여부 (bool)
        """
        data_list = self.common_util.check_and_make_list(data_list)

        if data_list is None:
            return False

        with self.db.get_postgres_db() as session:
            try:
                # insert에 필요한 테이블 매핑 정보 추출
                table_id = self.table_mapping_dict[table_name]["table_id"]
                prefix_col_list = self.table_mapping_dict[table_name]["prefix_col_list"]
                prefix_date_col = self.table_mapping_dict[table_name]["prefix_date"]

                # collect_id 채번 쿼리
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

                insert_cnt = 0

                for data in data_list:

                    # prefix 문자열 생성
                    if prefix_col_list:
                        prefix_str_list =[data[prefix_col][0] for prefix_col in prefix_col_list]
                        prefix_str_list = "".join(prefix_str_list)
                    else:
                        prefix_str_list = ""

                    # prefix 날짜 생성
                    if prefix_date_col:
                        prefix_date = datetime.strptime(data[prefix_date_col], "%Y-%m-%d").strftime("%y%m%d")
                    else:
                        prefix_date = datetime.now().strftime("%y%m%d")

                    # PK ID 생성 후 data에 추가
                    new_table_id = self.generate_table_id(session, table_name, prefix_str_list, prefix_date)

                    data["collect_id"] = new_collect_id
                    data[table_id] = new_table_id

                    # 현재 data 기준으로 컬럼/placeholder 생성
                    columns = ", ".join(data.keys())  # ("collect_id, data_type, ..." 형식)

                    # 컬럼명 리스트에 해당 컬럼이 있으면 (":collect_id, :data_type", ...) 형식으로 연결
                    # SQLAlchemy가 자동으로 :collect_id → "C26040701", :data_type → "NEWS" 이런식으로 매핑(session.execute)
                    placeholders = ", ".join([f":{key}" for key in data.keys()])

                    # insert 쿼리 생성
                    query = text(f"""
                        INSERT INTO {table_name} ({columns})
                        VALUES ({placeholders})
                    """)

                    self.logger.debug(f"insert 쿼리 = {query}")
                    self.logger.debug(f"insert 데이터 = {data}")

                    # 한 건씩 insert
                    session.execute(query, data)
                    insert_cnt += 1

                self.logger.info(f"{table_name} - 총 {insert_cnt}건 insert 완료")

                # t_data_collect_log insert
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

                session.commit()
                self.logger.info(f"t_data_collect_log insert 완료 - collect_id: {new_collect_id}")
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

    def update_data_to_postgres(self, table_name, update_col_nm, data_id, data):
        """
        공통 UPDATE 함수 (단일 데이터 업데이트)
        :param table_name: UPDATE 할 테이블 이름 (str)
        :param update_col_nm: UPDATE 할 컬럼 이름 (str)
        :param data_id: UPDATE 할 데이터 row의 ID (str)
        :param data: UPDATE 할 데이터 (str)
        :return: 성공 여부 (bool)
        """
        with self.db.get_postgres_db() as session:
            try:
                # 업데이트 할 테이블의 키 값이 되는 컬럼 이름 추출
                key_column = self.table_mapping_dict[table_name]["table_id"]

                # update 쿼리 생성
                query = text(f"""
                    UPDATE {table_name}
                    SET {update_col_nm} = :data,
                        update_dt = NOW()
                    WHERE {key_column} = :data_id
                """)

                session.execute(query, {
                    "data": data,
                    "data_id": data_id
                })

                session.commit()
                self.logger.info(f"{key_column}={data_id} - {update_col_nm} 업데이트 완료)")
                return True

            except Exception as e:
                session.rollback()
                self.logger.error(f"{key_column}={data_id} - {update_col_nm} 업데이트 실패 - Error: {str(e)}",
                                  exc_info=True, stack_info=True)
                raise e


# if __name__ == "__main__":
#     data_list = [
#         {'source_type': 'NAVER', 'news_title': '은지美·이란 2차협상 낙관론에...美증시 전쟁낙폭 만회 [월가월부]',
#          'publisher_name': 'M', 'category': '경제', 'published_date': '2026-04-15',
#          'contents': '메타·엔비디아 등 기술주 반등 견인\n협상 기대감에 브렌트·WTI 급락\n이번주 파키스탄서 2차 협상 전망\nPPI 소폭 상승에 인플레 부담 완화\n사진 확대\n뉴욕증권거래소\n미국과 이란이 2차 협상에 나설 것이라는 전망이 나오면서 국제유가가 급락하고 뉴욕증시가 일제히 상승했다.\n14일(현지시간) 뉴욕증권거래소에 따르면 대형주 중심의 S&P500 지수는 전장보다 1.18% 오른 6967.38에, 기술주 중심의 나스닥 종합지수는 1.96% 급등한 2만 3639.08에 마감했다. 다우존스30 산업평균지수도 0.66% 오른 4만 8535.99에 거래를 마쳤다. 특히 S&P500지수와 나스닥지수는 전쟁이 발발했던 지난 2월 28일 이전 수준을 모두 회복했다. 나스닥은 10일 연속 상승세를 이어갔다.\n메타(4.41%), 테슬라(3.33%), 엔비디아(3.78%) 등 기술주들이 시장 반등을 이끌었다. 반도체지수도 2.04% 상승했다.\n도널드 트럼프 미 대통령은 이날 뉴욕포스트와의 인터뷰에서 이란과의 종전 협상에 대해 “향후 이틀 안에 뭔가 일어날 수도 있고 우리가 그곳으로 갈 가능성이 더 커졌다”면서 재개 가능성을 시사했다.\n앞서 1차 협상이 결렬된 뒤 미국은 이란의 호르무즈 해협 봉쇄에 맞서 이란의 원유 수출 차단을 위한 해협봉쇄 맞불 전략으로 긴장감이 고조된바 있다.\n이날 브렌트유 선물 종가는 전장보다 4.6% 내린 배럴당 94.79달러를 기록했다. 미국산 서부텍사스산원유(WTI) 선물 종가는 91.28달러로 7.9% 급락했다.\n3월 생산자물가지수(PPI)가 전달대비 0.5% 상승하며 시장 전망치를 크게 밑돌아 인플레이션 우려가 약화된 것도 매수세로 이어졌다. 앞서 3월 소비자물가지수(CPI)가 전년 대비 3.3% 오르며 인플레이션 불안감이 확산됐지만 PPI 안도감에 시장의 우려도 다소 해소됐다.\n마이크 윌슨 모건스탠리 최고투자책임자(CIO)는 “시장이 다시 낙관론으로 돌아가고 있고 올해 하반기에는 상황이 건설적으로 해결될 것”이라고 분석했다.',
#          'url': 'https://www.mk.co.kr/article/12017153'}
#     ,
#     {'source_type': 'NAVER', 'news_title': '은지美 3월 PPI, 월간 0.5%p,연 4.0%↑…예상보단 적게 올라',
#      'publisher_name': 'H', 'category': '경제', 'published_date': '2026-04-24',
#      'contents': '사진=AFP\n이란전쟁이 시작된 시점인 3월 미국의 생산자물가(PPI)는 예상보다는 낮은 월간 0.5% 상승한 것으로 집계됐다. 그러나 에너지 가격 상승이 또 다른 인플레이션 급등에 대한 우려를 불러 일으켰다.\n14일(현지시간) 미국 노동통계국은 3월중 최종 수요 재화 및 서비스의 생산 과정 비용을 측정하는 생산자물가지수가 계절 조정 후 전월 대비 0.5% 상승했으며 연간으로 종합 PPI는 4.0% 상승했다고 발표했다. 월간 상승치 0.5%는 경제학자들이 예상한 1.1%를 크게 밑돈다.\n3월에 에너지 비용은 한 달간 8.5% 상승했다. 그러나 식품과 에너지를 제외한 근원 생산자물가지수는 예상치인 0.5%에 미치지 못하는 0.1% 상승에 그쳤다.\n전년 대비 종합 PPI는 4% 상승해 2023년 2월 이후 최대 12개월 상승폭을 기록했다. 근원 PPI는 전년 대비 3.8% 상승했다. 식품, 에너지 및 무역 서비스를 제외한 PPI는 전월 대비 0.2%, 전년 대비 3.6% 상승했다.\n생산자 가격 상승률은 지난 주 발표된 소비자물가지수(CPI)가 월간 0.9% 상승한 것에 비하면 완만한 흐름을 보였다.\n김정아 객원기자 kja@hankyung.com',
#      'url': 'https://www.hankyung.com/article/202604140991i'}
#
#     ]
#     postgres_insert = PostgresInsert()
#     postgres_insert.insert_data_to_postgres("t_news_data", data_list, "INCR")
