import time
import pandas as pd
from datetime import datetime
from pykrx import stock

from sqlalchemy import text
from src.database.connect_postgres import PostgresDB
from src.common.setup_log import SetupLogger
from src.database.postgres_common import PostgresInsert


class OriginStockCollector:
    """
    =====================================
    주식 일봉 데이터 수집 및 DB 적재 클래스
    =====================================

    전체 흐름:
    1. ticker 목록 조회 (t_ticker_info 기준)
    2. pykrx에서 월별(2026년 1월 ~ 5월 19일) OHLCV 데이터 수집
    3. 데이터 전처리 (타입 변환 / 컬럼 rename / 메타데이터 추가)
    4. batch 단위로 DB 적재
    """

    def __init__(self):
        """
        logger + DB + insert 객체 초기화
        """
        self.logger = SetupLogger.get_logger()
        self.db = PostgresDB()
        self.postgres_insert = PostgresInsert()

    # ==========================================
    # 1 & 2. pykrx API 조회 및 전처리 (기존 두 메서드 통합)
    # ==========================================
    def get_pykrx_monthly_data(self, start, end, ticker):

        df = stock.get_market_ohlcv(start, end, ticker).reset_index()

        if df is None or df.empty:
            self.logger.warning(f"[{ticker}] {start} ~ {end} 기간에 수집된 데이터가 없습니다.")
            return []

        num_cols = ["시가", "고가", "저가", "종가", "거래량","등락률"]
        for col in num_cols:
            df[col] = pd.to_numeric(df[col])
            #to_numeric : 데이터를 숫자형 (정수 / 실수)로 바꿔줌


        # DB 저장용 컬럼명으로 변경
        df = df.rename(columns={
            "날짜": "trade_date",
            "시가": "open_price",
            "고가": "high_price",
            "저가": "low_price",
            "종가": "close_price",
            "거래량": "volume",
            "등락률" : "daily_change"
        })

        # 날짜 포맷 문자열로 변경
        df["trade_date"] = df["trade_date"].dt.strftime("%Y-%m-%d")

        return df.to_dict("records")
    #to_dict : 한 행을 하나의 딕셔너리로 만들어서 리스트에 담음

    # =========================
    # 3. ticker 리스트 조회
    # =========================
    def get_ticker_info(self):
            """
            DB에서 ticker 목록 조회
            :return: list[dict] [{'ticker_name': '...', 'ticker_code': '...'}]
            """
            with self.db.get_postgres_db() as session:

                query = text("""
                    SELECT ticker_name, ticker_code
                    FROM t_ticker_info
                    WHERE use_yn = True
                    ORDER BY ticker_sno ASC
                """)

                # DB에 쿼리문 실행
                result = session.execute(query)

                ticker_list = [
                    {"ticker_name": row[0], "ticker_code": row[1]}
                    for row in result
                ]

                return ticker_list

    # =========================
    # 4. 전체 실행 (핵심 파이프라인)
    # =========================
    def insert_stock_data(self):
        """
        전체 주식 데이터 수집 및 DB 적재 실행 함수
        2026년 1월 ~ 5월 19일까지 월별로 루프를 돌며 수집
        """
        start_time = time.time()
        ticker_list = self.get_ticker_info()[:1]

        self.logger.info(f"총 {len(ticker_list)}개 종목 수집을 시작합니다.")

        # 2026년 1월 ~ 5월 19일까지의 월별 기간 정의
        target_periods = [
            ("20260101", "20260131"),
            ("20260201", "20260228"),
            ("20260301", "20260331"),
            ("20260401", "20260430"),
            ("20260501", "20260519")  # 5월은 19일까지 지정
        ]

        success_list = []
        fail_list = []

        batch_size = 100
        batch_result = []
        #enumerate : 순서까지 꺼내주는 함수
        for idx, ticker_info in enumerate(ticker_list):
            ticker_code = ticker_info['ticker_code']
            ticker_name = ticker_info['ticker_name']

            self.logger.info(
                f"[{idx + 1}/{len(ticker_list)}] {ticker_code} ({ticker_name}) 수집 중..."
            )

            ticker_all_months_data = []
            has_error = False
            error_msg = ""

            # 월별로 데이터 수집 루프 분할
            for start_date, end_date in target_periods:
                try:
                    monthly_result = self.get_pykrx_monthly_data(start_date, end_date, ticker_code)

                    if not monthly_result:
                        continue

                    processed_rows = [
                        {
                            **row,
                            "ticker_code": ticker_code,
                            "ticker_name": ticker_name,
                            "source_type": "PYKRX"
                        }
                        for row in monthly_result
                    ]

                    ticker_all_months_data.extend(processed_rows) #extend : 리스트를 이어 붙이는 함수
                    #[1월데이터,2월데이터,3월데이터,4월데이터,5월데이터]가 모아지는 리스트
                    time.sleep(0.2)  # 월별 API 호출 간격 단기 차단 방지 방어 코드

                except Exception as e:
                    has_error = True # 에러 발생함
                    error_msg = str(e) # 에러 내용을 문자열로 변환
                    break  # 한 달이라도 에러 나면 해당 종목은 실패 처리 후 다음 종목으로

            if has_error:
                self.logger.error(f"[{ticker_code}] 수집 실패 - 사유: {error_msg}")
                fail_list.append({
                    "ticker_code": ticker_code,
                    "ticker_name": ticker_name,
                    "reason": error_msg
                })
                continue

            if not ticker_all_months_data:
                fail_list.append({
                    "ticker_code": ticker_code,
                    "ticker_name": ticker_name,
                    "reason": "해당 기간 데이터 없음"
                })
                continue

            # 정상 수집된 데이터 batch에 누적
            batch_result.extend(ticker_all_months_data)
            success_list.append({
                "ticker_code": ticker_code,
                "ticker_name": ticker_name
            })

            # ==========================================
            # batch insert (100개 종목 단위로 누적 데이터 처리)
            # ==========================================
            if len(success_list) % batch_size == 0: #나머지 값
                self.logger.info(f"=== 데이터 삽입 진행 ({len(batch_result)} 행) ===")
                self.postgres_insert.insert_data_to_postgres(
                    "t_stock_original_price_data",
                    batch_result,
                    "BULK"
                )
                batch_result = []  # 배치 초기화

        # =========================
        # 남은 데이터 최종 insert
        # =========================
        if batch_result:
            self.logger.info(f"=== 최종 잔여 데이터 삽입 진행 ({len(batch_result)} 행) ===")
            self.postgres_insert.insert_data_to_postgres(
                "t_stock_original_price_data",
                batch_result,
                "BULK"
            )

        total_time = time.time() - start_time
        self.logger.info(f"======= 수집 완료 | 소요 시간: {total_time:.2f}초 =======")
        self.logger.info(f"성공 종목 수: {len(success_list)} / 실패 종목 수: {len(fail_list)}")
        if fail_list:
            self.logger.debug(f"실패 세부 리스트: {fail_list}")


# =========================
# 실행 코드
# =========================
if __name__ == "__main__":
    print("수집 프로세스를 시작합니다.")
    stock_collector = OriginStockCollector()
    stock_collector.insert_stock_data()