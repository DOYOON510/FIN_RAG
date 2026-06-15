import time
import pandas as pd
from pykrx import stock
from sqlalchemy import text
from src.database.connect_postgres import PostgresDB
from src.common.setup_log import SetupLogger
from src.database.postgres_common import PostgresInsert
from src.database.postgres_common import PostgresUpdate



class OriginStockCollector:
    """
    주식 데이터 수집 및 DB 적재 클래스

    전체 흐름:
    1. ticker 목록 조회 (t_ticker_info 기준)
    2. pykrx에서 2025년 12월 ~ 5월 22일 OHLCV 데이터 수집
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


    def get_pykrx_monthly_data(self, ticker: str,start_date: str, end_date: str):

        """
        pykrx에서 특정 ticker의 OHLCV 데이터를 수집하고 전처리하여 반환

        처리 흐름:
        1. pykrx API 호출 → OHLCV 데이터 수집
        2. 숫자형 변환 (시가, 고가, 저가, 종가, 거래량)
        3. 고가 또는 저가가 0인 비정상 데이터 제거 (경고 로그 출력)
        4. 컬럼명 한글 → 영문 rename
        5. 날짜 포맷 변환 (datetime → "YYYY-MM-DD" 문자열)
        6. dict 리스트로 변환하여 반환

        param ticker: 종목 코드 (예: "005930")
        param start_date: 수집 시작일 (예: "20251201")
        param end_date:   수집 종료일 (예: "20260520")

        return: list[dict] 형태의 전처리된 OHLCV 데이터. 실패 또는 데이터 없을 시 []
        """

        try:
            df = stock.get_market_ohlcv(start_date, end_date, ticker).reset_index()
        except Exception as e:
            self.logger.error(f"[{ticker}] API 호출 실패 - 사유: {str(e)}")
            return []

        if df is None or df.empty:
            self.logger.warning(f"[{ticker}] {start_date} ~ {end_date} 기간에 수집된 데이터가 없습니다.")
            return []

        num_cols = ["시가", "고가", "저가", "종가", "거래량"]
        for col in num_cols:
            df[col] = pd.to_numeric(df[col])

        # 고가 또는 저가가 0인 행 확인
        invalid_rows = df[(df["고가"] == 0) | (df["저가"] == 0)]

        if not invalid_rows.empty:
            self.logger.warning(
                f"[{ticker}] 비정상 데이터 {len(invalid_rows)}건 발견 → 고가/저가 NULL 처리"
            )

            mask = (df["고가"] == 0) | (df["저가"] == 0)

            df.loc[mask, "고가"] = None
            df.loc[mask, "저가"] = None

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

    #ticker 리스트 조회
    def get_ticker_info(self):
        """
        DB에서 수집 대상 ticker 목록 조회

        처리 흐름:
        1. t_ticker_info 테이블에서 ticker_code , ticker_name 종목 조회
        2. ticker_sno 기준 오름차순 정렬
        3. ticker_name, ticker_code 반환

        :return: ticker_name 과 ticker_code가 담긴 리스트
        """
        with self.db.get_postgres_db() as session:
            query = text("""
                SELECT ticker_sno, ticker_name, ticker_code
                FROM t_ticker_info
                WHERE use_yn = True
                ORDER BY ticker_sno ASC
            """)
            result = session.execute(query)
            return [
                {"ticker_sno": row[0], "ticker_name": row[1], "ticker_code": row[2]}
                for row in result
            ]

    def insert_stock_data(self, start_date: str, end_date: str):

        """
        전체 주식 데이터 수집 및 DB insert 실행 함수

        처리 흐름:
        1. DB에서 ticker 목록 조회
        2. ticker별 OHLCV 데이터 수집
        3. ticker_code, ticker_name, source_type 메타데이터 추가
        4. batch_size(100)마다 DB bulk insert
        5. 잔여 데이터 최종 insert

        """

        start_time = time.time()
        ticker_list = self.get_ticker_info()
        self.logger.info(f"총 {len(ticker_list)}개 종목 수집을 시작합니다.")

        success_count = 0
        fail_list = []
        batch_result = []
        batch_size = 100

        for idx, ticker_info in enumerate(ticker_list):
            ticker_code = ticker_info['ticker_code']
            ticker_name = ticker_info['ticker_name']

            self.logger.info(f"[{idx + 1}/{len(ticker_list)}] {ticker_code} ({ticker_name}) 수집 중...")

            stock_result = self.get_pykrx_monthly_data(ticker_code, start_date, end_date)

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

    def check_invalid_data(self, start_date: str, end_date: str):
        """
          비정상 OHLCV 데이터(고가=0 또는 저가=0) 검사 및 종목 사용 여부 업데이트

          처리 흐름:
          1. DB에서 수집 대상 ticker 목록 조회
          2. pykrx에서 기간별 OHLCV 데이터 조회
          3. 고가 또는 저가가 0인 비정상 데이터 탐색
          4. 비정상 데이터 발생 날짜 및 건수 저장
          5. 전체 기간이 모두 비정상 데이터인 경우 use_yn=False 업데이트
          6. 검사 결과 로그 출력 및 업데이트된 종목 반환

          return:
              list[dict]
              use_yn=False 처리된 종목 정보 목록

          """
        ticker_list = self.get_ticker_info()
        self.logger.info(f"총 {len(ticker_list)}개 종목 비정상 데이터 검사 시작")

        updater = PostgresUpdate()

        invalid_ticker_summary = []
        updated_tickers = []

        for idx, ticker_info in enumerate(ticker_list):
            ticker_code = ticker_info['ticker_code']
            ticker_name = ticker_info['ticker_name']
            ticker_sno = ticker_info['ticker_sno']

            self.logger.info(
                f"[{idx + 1}/{len(ticker_list)}] "
                f"{ticker_code} ({ticker_name}) 검사 중..."
            )

            try:
                df = stock.get_market_ohlcv(
                    start_date,
                    end_date,
                    ticker_code
                ).reset_index()

            except Exception as e:
                self.logger.error(
                    f"[{ticker_code}] API 호출 실패 - {str(e)}"
                )
                continue

            if df is None or df.empty:
                continue

            num_cols = ["시가", "고가", "저가", "종가", "거래량"]

            for col in num_cols:
                df[col] = pd.to_numeric(df[col])

            invalid_rows = df[(df["고가"] == 0) | (df["저가"] == 0)]

            if not invalid_rows.empty:

                dates = (
                    invalid_rows["날짜"]
                    .dt.strftime("%Y-%m-%d")
                    .tolist()
                )

                invalid_ticker_summary.append({
                    "ticker_code": ticker_code,
                    "ticker_name": ticker_name,
                    "count": len(invalid_rows),
                    "dates": dates
                })

                if len(invalid_rows) == len(df):
                    updater.update_data_to_postgres(
                        "t_ticker_info",
                        "use_yn",
                        ticker_sno,
                        False
                    )

                    updated_tickers.append({
                        "ticker_sno": ticker_sno,
                        "ticker_code": ticker_code,
                        "ticker_name": ticker_name
                    })

                    self.logger.info(
                        f"[{ticker_code}] {ticker_name} "
                        f"- 전체 기간 비정상 → use_yn=False 처리 완료"
                    )

            time.sleep(0.2)

        self.logger.info("======= 비정상 데이터 종목 요약 =======")
        self.logger.info(
            f"총 {len(invalid_ticker_summary)}개 종목에서 비정상 데이터 발견"
        )

        for item in invalid_ticker_summary:
            self.logger.debug(
                f"[{item['ticker_code']}] "
                f"{item['ticker_name']} | "
                f"날짜 수: {item['count']}일 | "
                f"날짜: {', '.join(item['dates'])}"
            )

        self.logger.info("======= use_yn=False 업데이트 결과 =======")
        self.logger.info(f"총 {len(updated_tickers)}개 종목 업데이트")

        for item in updated_tickers:
            self.logger.info(
                f"ticker_sno={item['ticker_sno']} | "
                f"ticker_code={item['ticker_code']} | "
                f"ticker_name={item['ticker_name']}"
            )

        return updated_tickers

if __name__ == "__main__":
    collector = OriginStockCollector()

    collector.check_invalid_data(
        start_date="20251201",
        end_date="20260605"
    )

    collector.insert_stock_data(
        start_date="20251201",
        end_date="20260605"
    )