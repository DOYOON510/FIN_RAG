import time
import requests
import pandas as pd
from datetime import datetime, timedelta
from pykrx import stock

from sqlalchemy import text
from src.database.connect_postgres import PostgresDB
from src.common.setup_log import SetupLogger
from src.database.postgres_common import PostgresInsert

from HN.Stock.today_price import get_today_price
from src.common.common_const import StockConstant
from src.config.env_config import APIConstants



#todo Class 만들어서 test_sum2 + collect1000 합치고 주석 달기 (input + output) / 파일명 바꾸기 / 병렬 지우고 index로 해보기

class StockCollector:

    def __init__(self):
        self.logger = SetupLogger.get_logger()
        self.db = PostgresDB()
        self.postgres_insert = PostgresInsert()


    def get_access_token():
        url = StockConstant.stock_url
        data = {
            "grant_type": "client_credentials",
            "appkey": APIConstants.APP_KEY,
            "appsecret": APIConstants.APP_SECRET
        }
        res = requests.post(url, json=data)
        return res.json().get("access_token")

    TOKEN = get_access_token()

# 과거 6개월치 가져오는 값 가져오는 함수
    def get_past_6months(self,ticker):

        end = datetime.today().strftime("%Y%m%d") #20260504
        start = (datetime.today() - timedelta(days=300)).strftime("%Y%m%d")
        #timedelta : 기간의 차이를 나타낼 수 있음
        #start = 2026-05-04 - 200일 = 2024nnnn 로 변환 가능


        df = stock.get_market_ohlcv(start, end, ticker).reset_index()

        return df[['날짜', '시가', '고가', '저가', '종가', '거래량']]

# Column 값 계산

    def add_indicators(self, df):

        df = df.sort_values("날짜").reset_index(drop=True)

        # 🔥 안전장치 (혹시 모를 object 제거)
        df["종가"] = pd.to_numeric(df["종가"], errors="coerce")

        df['ma_20'] = df['종가'].rolling(20, min_periods=1).mean()
        # 이동평균 : 최근 20일 평균 가격
        # rolling : 최근 20개 데이터 묶음
        df['daily_change'] = df['종가'].pct_change()
        # 일일 수익률 : 어제 대비 오늘 가격 변화율
        # pct_change : 이전 값 대비 얼마나 변했는지 비율
        df['volatility'] = df['종가'].rolling(20, min_periods=1).std()
        # 변동성 : 최근 20일 가격의 흔들림 정도


        # 🔥 기준값 안전 처리
        base = df["종가"].dropna()
        if len(base) > 0:
            base = base.iloc[0]
            df['cum_return'] = (df['종가'] / base) - 1
        else:
            df['cum_return'] = None
            # 누적 수익률 : 처음 가격 대비 지금까지 얼마나 올랐는지
        df['dd_high'] = (df['종가'] / df['고가'].rolling(60, min_periods=1).max()) - 1
        df['dd_high'] = df['dd_high'].replace([float('inf'), float('-inf')], None)
        # 고점 대비 하락률 : 최근 60일 최고가 대비 얼마나 떨어졌는지

        df['ret_low'] = (df['종가'] / df['저가'].rolling(60, min_periods=1).min()) - 1
        df['ret_low'] = df['ret_low'].replace([float('inf'), float('-inf')], None)
        # 저점 대비 상승률 : 최근 60일 최저가 대비 얼마나 올랐는지

        return df

# 최종 과거+ 현재 값 합치는 함수
    def get_kis_6months(self, ticker):

        past_df = self.get_past_6months(ticker)
        today_df = pd.DataFrame(get_today_price(ticker))

        past_df["날짜"] = pd.to_datetime(past_df["날짜"])
        today_df["날짜"] = pd.to_datetime(today_df["날짜"])

        df = pd.concat([past_df, today_df], ignore_index=True)
        df["날짜"] = pd.to_datetime(df["날짜"])

        df = df.sort_values("날짜").reset_index(drop=True)

        # 🔥 cutoff 먼저 정의
        end = datetime.today()
        start = end - timedelta(days=180)

        df = self.add_indicators(df)

        df = df[(df["날짜"] >= start) & (df["날짜"] <= end)]

        if df.empty:
            return []

        df = df.rename(columns={
            "날짜": "trade_date",
            "시가": "open_price",
            "고가": "high_price",
            "저가": "low_price",
            "종가": "close_price",
            "거래량": "volume",
        })

        df["trade_date"] = df["trade_date"].dt.strftime("%Y-%m-%d")
        df = df.where(pd.notnull(df), None)

        return df.to_dict("records")

    # ticker 조회 함수
    def get_ticker_info(self):
        with self.db.get_postgres_db() as session:
            query = text("""
                SELECT ticker_name, ticker_code
                FROM t_ticker_info
                WHERE use_yn = True
            """)
            return session.execute(query).mappings().all()

    # 단일 ticker 수집
    def fetch_one_ticker(self, ticker_info):

        ticker_code = ticker_info["ticker_code"]
        ticker_name = ticker_info["ticker_name"]

        try:
            past_df = self.get_past_6months(ticker_code)
            today_df = pd.DataFrame(get_today_price(ticker_code))

            past_df["날짜"] = pd.to_datetime(past_df["날짜"])
            today_df["날짜"] = pd.to_datetime(today_df["날짜"])

            df = pd.concat([past_df, today_df], ignore_index=True)

            df = self.add_indicators(df)

            df = df.rename(columns={
                "날짜": "trade_date",
                "시가": "open_price",
                "고가": "high_price",
                "저가": "low_price",
                "종가": "close_price",
                "거래량": "volume",
            })

            df["trade_date"] = df["trade_date"].dt.strftime("%Y-%m-%d")
            df = df.where(pd.notnull(df), None)

            data_list_raw = df.to_dict("records")

            result = []
            for row in data_list_raw:
                result.append({
                    "trade_date": row["trade_date"],
                    "ticker_name": ticker_name,
                    "ticker_code": ticker_code,
                    "open_price": row["open_price"],
                    "high_price": row["high_price"],
                    "low_price": row["low_price"],
                    "close_price": row["close_price"],
                    "volume": row["volume"],
                    "ma_20": row.get("ma_20"),
                    "daily_change": row.get("daily_change"),
                    "volatility": row.get("volatility"),
                    "cum_return": row.get("cum_return"),
                    "dd_high": row.get("dd_high"),
                    "ret_low": row.get("ret_low"),
                })

            self.logger.info(f"{ticker_code} 수집 완료")
            return result

        except Exception as e:
            self.logger.error(f"{ticker_code} 실패 - {str(e)}")
            return []

    # db에 데이터 넣기
    def insert_stock_data(self):

        start_time = time.time()
        ticker_list = self.get_ticker_info()

        self.logger.info(f"총 {len(ticker_list)} 종목 시작")

        postgres_insert = PostgresInsert()

        success_list = []  # ✅ 성공 종목
        fail_list = []  # ✅ 실패 종목

        for idx, ticker in enumerate(ticker_list):
            ticker_code = ticker['ticker_code']
            ticker_name = ticker['ticker_name']

            self.logger.info(f"[{idx + 1}/{len(ticker_list)}] {ticker_code} {ticker_name} 수집 중")

            result = self.fetch_one_ticker(ticker)

            if not result:
                self.logger.warning(f"{ticker_code} {ticker_name} - 수집 데이터 없음")
                fail_list.append({"ticker_code": ticker_code, "ticker_name": ticker_name, "reason": "수집 데이터 없음"})
                continue

            for row in result:
                row["source_type"] = "PYKRX"

            try:
                postgres_insert.insert_data_to_postgres("t_stock_price_data", result, "BULK")
                success_list.append({"ticker_code": ticker_code, "ticker_name": ticker_name})
            except Exception as e:
                self.logger.error(f"{ticker_code} {ticker_name} INSERT 실패 - {str(e)}")
                fail_list.append({"ticker_code": ticker_code, "ticker_name": ticker_name, "reason": str(e)})
                continue

        # ✅ 최종 결과 요약
        total_time = time.time() - start_time
        self.logger.info(f"======= 수집 완료 | {total_time:.2f}s =======")
        self.logger.info(f"성공: {len(success_list)}건 / 실패: {len(fail_list)}건 / 전체: {len(ticker_list)}건")

        if fail_list:
            self.logger.warning("====== 실패 종목 목록 ======")
            for fail in fail_list:
                self.logger.warning(f"  ❌ {fail['ticker_code']} {fail['ticker_name']} - {fail['reason']}")

# 실행
if __name__ == "__main__":
    print(" 실행 시작")

    stock_collector = StockCollector()
    stock_collector.insert_stock_data()