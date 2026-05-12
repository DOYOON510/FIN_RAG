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
    2. pykrx에서 6개월 OHLCV 데이터 수집
    3. 데이터 전처리 (정렬 / 타입 변환 / 컬럼 rename)
    4. ticker 단위 데이터 생성
    5. batch 단위로 DB 적재
    """

    def __init__(self):
        """
        logger + DB + insert 객체 초기화
        """
        self.logger = SetupLogger.get_logger()
        self.db = PostgresDB()
        self.postgres_insert = PostgresInsert()

    # =========================
    # 1. 과거 6개월 데이터 조회 (pykrx API)
    # =========================
    def get_past_6months(self, ticker):
        """
        특정 종목의 6개월 OHLCV 데이터를 pykrx API로 조회

        처리 흐름:
        1. 시작일 / 종료일 기준 설정
        2. pykrx API 호출
        3. OHLCV 데이터 반환

        :param ticker: 종목 코드 (str)
        :return: pandas DataFrame (날짜, 시가, 고가, 저가, 종가, 거래량)
        """

        end = "20260511"
        start = "20251101"

        df = stock.get_market_ohlcv(start, end, ticker).reset_index()

        return df[['날짜', '시가', '고가', '저가', '종가', '거래량']]

    # =========================
    # 2. ticker 1개 데이터 전처리
    # =========================
    def get_pykrx_6months(self, ticker):
        """
        ticker 1개 기준 데이터 전처리

        처리 과정:
        - 날짜 datetime 변환
        - 날짜 기준 정렬
        - 숫자형 변환 (OHLCV)
        - 컬럼명 DB 스키마 기준으로 변경
        - dict 형태로 변환 (DB insert용)

        param ticker: 종목 코드 (str)

        return: list :
         [
                {
                    "trade_date": "2026-01-01",
                    "open_price": ...,
                    "high_price": ...,
                    "low_price": ...,
                    "close_price": ...,
                    "volume": ...,
                }
            ]
        """

        df = self.get_past_6months(ticker)

        if df is None or df.empty:
            return []

        # 날짜 타입 변환 + 정렬
        df["날짜"] = pd.to_datetime(df["날짜"], errors="coerce")
        df = df.sort_values("날짜").reset_index(drop=True)

        # 숫자형 강제 변환 (문자/결측 방지)
        num_cols = ["시가", "고가", "저가", "종가", "거래량"]
        for col in num_cols:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        # DB 저장용 컬럼명으로 변경
        df = df.rename(columns={
            "날짜": "trade_date",
            "시가": "open_price",
            "고가": "high_price",
            "저가": "low_price",
            "종가": "close_price",
            "거래량": "volume",
        })

        # 날짜 포맷 문자열로 변경 (DB insert 안정성)
        df["trade_date"] = df["trade_date"].dt.strftime("%Y-%m-%d")

        return df.to_dict("records")

    # =========================
    # 3. ticker 리스트 조회 (순서 중요)
    # =========================
    def get_ticker_info(self):
        """
         DB에서 ticker 목록 조회

        처리 흐름:
        1. t_ticker_info 테이블 조회
        2. use_yn = True 필터링
        3. ticker_sno 기준 정렬 (중요: 수집 순서 유지)

        :return: list[dict]
            [
                {
                    "ticker_name": "삼성전자",
                    "ticker_code": "005930"
                }
            ]
        """

        with self.db.get_postgres_db() as session:

            query = text("""
                SELECT ticker_name, ticker_code
                FROM t_ticker_info
                WHERE use_yn = True
                ORDER BY ticker_sno ASC
            """)

            return session.execute(query).mappings().all()

    # =========================
    # 4. 전체 실행 (핵심 파이프라인)
    # =========================
    def insert_stock_data(self):
        """
        전체 주식 데이터 수집 및 DB 적재 실행 함수

        처리 흐름:
        1. ticker 리스트 조회 (정렬된 순서 유지)
        2. ticker 하나씩 반복 처리
        3. pykrx 데이터 수집
        4. ticker 메타정보 추가 (code, name, source)
        5. ticker 내부 날짜 정렬
        6. batch 리스트에 누적
        7. 100종목 단위로 bulk insert
        8. 남은 데이터 최종 insert

        batch 전략:
        - 100 ticker 단위로 DB insert 수행
        - 메모리 과부하 방지

        :return: None
        """

        start_time = time.time()

        ticker_list = self.get_ticker_info()

        self.logger.info(f"총 {len(ticker_list)} 종목 시작")

        success_list = []
        fail_list = []

        # =========================
        # batch 설정 (100종목 단위 insert)
        # =========================
        batch_size = 100
        batch_result = []

        for idx, ticker_info in enumerate(ticker_list):

            ticker_code = ticker_info['ticker_code']
            ticker_name = ticker_info['ticker_name']

            self.logger.info(
                f"[{idx + 1}/{len(ticker_list)}] {ticker_code} {ticker_name} 수집"
            )

            try:
                # 1. ticker 데이터 수집
                result = self.get_pykrx_6months(ticker_code)

                if not result:
                    fail_list.append({
                        "ticker_code": ticker_code,
                        "ticker_name": ticker_name,
                        "reason": "no data"
                    })
                    continue

                # 2. ticker 정보 추가 (DB 저장용 metadata)
                for row in result:
                    row["ticker_code"] = ticker_code
                    row["ticker_name"] = ticker_name
                    row["source_type"] = "PYKRX"

                # 3. ticker 내부 정렬 (날짜 기준)
                result.sort(key=lambda x: x["trade_date"])

                # 4. batch 누적
                batch_result.extend(result)

                success_list.append({
                    "ticker_code": ticker_code,
                    "ticker_name": ticker_name
                })

                # =========================
                # 5. batch insert (100 ticker 단위)
                # =========================
                if len(success_list) % batch_size == 0:

                    self.logger.info(
                        f"=== BATCH INSERT ({len(batch_result)} rows) ==="
                    )



                    self.postgres_insert.insert_data_to_postgres(
                        "t_stock_original_price_data",
                        batch_result,
                        "BULK"
                    )

                    # batch 초기화
                    batch_result = []

                time.sleep(0.2)

            except Exception as e:

                self.logger.error(f"{ticker_code} 실패 - {str(e)}")

                fail_list.append({
                    "ticker_code": ticker_code,
                    "ticker_name": ticker_name,
                    "reason": str(e)
                })

        # =========================
        # 6. 남은 데이터 최종 insert
        # =========================
        if batch_result:
            self.logger.info(f"=== FINAL BATCH INSERT ({len(batch_result)} rows) ===")

            self.postgres_insert.insert_data_to_postgres(
                "t_stock_original_price_data",
                batch_result,
                "BULK"
            )

        total_time = time.time() - start_time

        self.logger.info(f"======= 완료 | {total_time:.2f}s =======")
        self.logger.info(f"성공: {len(success_list)} / 실패: {len(fail_list)}")


# =========================
# 실행 코드
# =========================
if __name__ == "__main__":

    print("실행 시작")

    stock_collector = OriginStockCollector()
    stock_collector.insert_stock_data()