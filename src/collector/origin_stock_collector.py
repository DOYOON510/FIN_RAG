import time
import pandas as pd
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

    def __init__(self, start_date: str, end_date: str):
        """
                logger + DB + insert 객체 초기화
        """
        self.logger = SetupLogger.get_logger()
        self.db = PostgresDB()
        self.postgres_insert = PostgresInsert()
        self.start_date = start_date
        self.end_date = end_date
        """
        (수정)
        날짜 지정
        """

    def get_pykrx_monthly_data(self, ticker: str):

        df = stock.get_market_ohlcv(self.start_date, self.end_date, ticker).reset_index()

        if df is None or df.empty:
            self.logger.warning(f"[{ticker}] {self.start_date} ~ {self.end_date} 기간에 수집된 데이터가 없습니다.")
            return []

        num_cols = ["시가", "고가", "저가", "종가", "거래량"]
        for col in num_cols:
            df[col] = pd.to_numeric(df[col])

        df = df.rename(columns={
            "날짜": "trade_date",
            "시가": "open_price",
            "고가": "high_price",
            "저가": "low_price",
            "종가": "close_price",
            "거래량": "volume",
        })

        df = df[["trade_date", "open_price", "high_price", "low_price", "close_price", "volume"]]
        df["trade_date"] = df["trade_date"].dt.strftime("%Y-%m-%d")

        return df.to_dict("records")
    """
    (수정)
    get_market_ohlcv 라이브러리는 [날짜,시가,고가,저가,종가,거래량,등락률] 컬럼 나오는 것 확인됨
    그래서 아래에 따로 ticker_code와 ticker_name source_type 넣는 것 유지
    """

    #ticker 리스트 조회
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
            result = session.execute(query)
            return [
                {"ticker_name": row[0], "ticker_code": row[1]}
                for row in result
            ]

    def insert_stock_data(self):
        """
        전체 주식 데이터 수집 및 DB 적재 실행 함수
        """
        start_time = time.time()
        ticker_list = self.get_ticker_info()[:1]
        self.logger.info(f"총 {len(ticker_list)}개 종목 수집을 시작합니다.")

        success_count = 0
        """
        (수정)
        success_list가 아니라 success_count로 변경
        has_error와 err_msg도 없애고 오류 발생시 except Exception as e로 넘어가 에러 로그 찍힘
        """
        fail_list = []
        batch_result = []
        batch_size = 100

        """
        (수정)
        기존: 월별(1월, 2월 ... 5월)로 나눠서 API 호출 및 삽입하는 방식
            → 특정 월 누락 케이스를 대비한 예외처리 필요
            
        변경: start_date ~ end_date 날짜 범위를 한번에 지정하는 방식
            → 종목 단위 성공/실패만 체크하면 되므로 예외처리 단순화
        """

        for idx, ticker_info in enumerate(ticker_list):
            ticker_code = ticker_info['ticker_code']
            ticker_name = ticker_info['ticker_name']

            self.logger.info(f"[{idx + 1}/{len(ticker_list)}] {ticker_code} ({ticker_name}) 수집 중...")

            try:
                stock_result = self.get_pykrx_monthly_data(ticker_code)
            except Exception as e:
                self.logger.error(f"[{ticker_code}] {ticker_name} 수집 실패 - 사유: {str(e)}")
                fail_list.append({
                    "ticker_code": ticker_code,
                    "ticker_name": ticker_name,
                    "reason": str(e)
                })
                continue
            time.sleep(0.2)

            if not stock_result:
                self.logger.warning(f"[{ticker_code}] {ticker_name} - 해당 기간 데이터 없음")
                fail_list.append({
                    "ticker_code": ticker_code,
                    "ticker_name": ticker_name,
                    "reason": "데이터 없음"
                })
                continue

            processed_rows = [
                {
                    **row,
                    "ticker_code": ticker_code,
                    "ticker_name": ticker_name,
                    "source_type": "PYKRX"
                }
                for row in stock_result
            ]

            batch_result.extend(processed_rows)
            success_count += 1

            if success_count % batch_size == 0:
                self.logger.info(f"=== 배치 삽입 진행 ({len(batch_result)} 행) ===")
                self.postgres_insert.insert_data_to_postgres(
                    "t_stock_original_price_data",
                    batch_result,
                    "BULK"
                )
                batch_result = []

        if batch_result:
            self.logger.info(f"=== 최종 잔여 데이터 삽입 ({len(batch_result)} 행) ===")
            self.postgres_insert.insert_data_to_postgres(
                "t_stock_original_price_data",
                batch_result,
                "BULK"
            )

        total_time = time.time() - start_time
        self.logger.info(f"======= 수집 완료 | 소요 시간: {total_time:.2f}초 =======")
        self.logger.info(f"성공: {success_count}개 / 실패: {len(fail_list)}개")
        if fail_list:
            self.logger.error(f"실패 종목 수: {len(fail_list)}개")
            for fail in fail_list:
                self.logger.error(
                    f"[실패] 종목코드: {fail['ticker_code']} | 종목명: {fail['ticker_name']} | 사유: {fail['reason']}"
                )


if __name__ == "__main__":
    collector = OriginStockCollector(start_date="20251201", end_date="20260520")
    collector.insert_stock_data()