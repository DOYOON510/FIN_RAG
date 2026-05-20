import time
import requests
from datetime import datetime

from src.common.common_const import StockConstant
from src.config.env_config import APIConstants
from src.collector.origin_stock_collector import OriginStockCollector

from src.common.setup_log import SetupLogger

from src.database.connect_postgres import PostgresDB
from src.database.postgres_common import PostgresInsert


class TodayStockCollector:
    """
    KIS API 기반 '실시간 현재가' 수집 클래스

    역할:
    1. Access Token 발급
    2. 종목별 현재가 조회
    3. 전체 종목 수집
    4. DB 저장 (batch insert)
    """

    def __init__(self):
        """
        초기 설정

        구성 요소:
        - logger: 로그 관리
        - db: DB 커넥션
        - postgres_insert: insert 유틸
        - stock_collector: 기존 ticker 리스트 재사용
        - token: KIS API 인증 토큰
        """

        self.logger = SetupLogger.get_logger()
        self.db = PostgresDB()
        self.postgres_insert = PostgresInsert()

        # 기존 ticker 조회 로직 재사용 (t_ticker_info 기준)
        self.stock_collector = OriginStockCollector()

        # API URL
        self.token_url = StockConstant.token_url
        self.stock_url = StockConstant.stock_url

        # API Key
        self.api_key = APIConstants.API_KEY
        self.api_secret = APIConstants.API_SECRET

        # Access Token (초기 1회 발급)
        self.token = self.get_access_token()

    # =========================
    # 1. Access Token 발급
    # =========================
    def get_access_token(self):
        """
        KIS API access token 발급

        Input:
            - appkey / appsecret

        Output:
            - access_token (str)

        흐름:
        1. token API 호출
        2. 응답 검증
        3. access_token 반환
        """

        data = {
            "grant_type": "client_credentials",
            "appkey": self.api_key,
            "appsecret": self.api_secret
        }

        res = requests.post(
            url=self.token_url,
            headers={"content-type": "application/json"},
            json=data
        )

        if res.status_code != 200:
            raise Exception(f"토큰 발급 실패 - {res.text}")

        result = res.json()
        access_token = result.get("access_token")

        self.logger.info("access token 발급 완료")

        return access_token

    # =========================
    # 2. 종목 현재가 조회
    # =========================
    def get_today_price(self, access_token, ticker_code, ticker_name):
        """
        단일 종목 현재가 조회

        Input:
            - ticker_code: 종목 코드
            - ticker_name: 종목명

        Output:
            - 현재가 데이터 리스트 (DB insert용 1 row)

        흐름:
        1. KIS API 호출
        2. 응답 검증
        3. 필요한 가격 데이터 추출
        4. dict 형태로 변환
        """

        headers = {
            "content-type": "application/json; charset=utf-8",
            "authorization": f"Bearer {access_token}",
            "appkey": self.api_key,
            "appsecret": self.api_secret,
            "tr_id": "FHKST01010100",
            "custtype": "P"
        }

        params = {
            "fid_cond_mrkt_div_code": "J",
            "fid_input_iscd": ticker_code
        }

        res = requests.get(
            url=self.stock_url,
            headers=headers,
            params=params
        )

        if res.status_code != 200: #성공이 아니라면
            raise Exception(f"현재가 조회 실패 - {res.text}") #실패하면 예외를 발생시켜서 except로 넘기는 구조

        result = res.json()

        rt_cd = result.get("rt_cd")
        msg1 = result.get("msg1")

        if rt_cd != "0": # 0이 아니라면 -> 실패라면
            self.logger.error(f"[현재가 조회 실패] {ticker_code} {ticker_name} | msg={msg1}")


            raise Exception(f"{ticker_code} {ticker_name} 현재가 조회 실패 - {msg1}")

        #result 구조 : {"rt_cd": "0", 응답 상태 코드 0: 성공 그외 : 실패
        #              "msg_cd": "AP00000", 메시지 코드
        #              "msg1": "정상처리되었습니다",
        #              "output": { ... }}

        output = result.get("output", {})

        return [{
            "trade_date": datetime.today().strftime("%Y-%m-%d"),
            "ticker_code": ticker_code,
            "ticker_name": ticker_name,
            "open_price": int(output.get("stck_oprc", 0)),
            "high_price": int(output.get("stck_hgpr", 0)),
            "low_price": int(output.get("stck_lwpr", 0)),
            "close_price": int(output.get("stck_prpr", 0)),
            "volume": int(output.get("acml_vol", 0)),
            "source_type": "KIS"
        }]

    # =========================
    # 3. 전체 종목 현재가 수집 + INSERT
    # =========================
    def insert_today_stock_data(self):
        """
        전체 종목 현재가 수집 후 DB 저장

        흐름:
        1. ticker 목록 조회
        2. 종목별 API 호출
        3. 결과 누적 (all_result)
        4. 실패/성공 분리
        5. 마지막에 bulk insert
        """

        ticker_list = self.stock_collector.get_ticker_info()
        access_token = self.token

        self.logger.info(f"총 {len(ticker_list)} 종목 현재가 수집 시작")

        success_list = []
        fail_list = []

        # 전체 결과 누적 (batch insert용)
        all_result = []

        for idx, ticker_info in enumerate(ticker_list):

            time.sleep(0.2)  # API rate limit 방지

            ticker_code = ticker_info["ticker_code"]
            ticker_name = ticker_info["ticker_name"]

            self.logger.info(
                f"[{idx + 1}/{len(ticker_list)}] "
                f"{ticker_code} {ticker_name} 현재가 수집 중"
            )

            try:
                result = self.get_today_price(
                    access_token,
                    ticker_code,
                    ticker_name
                )

                all_result.extend(result)

                success_list.append({
                    "ticker_code": ticker_code,
                    "ticker_name": ticker_name
                })

            except Exception as e:

                self.logger.error(
                    f"[현재가 수집 실패] {ticker_code} {ticker_name} | error={e}"
                )

                fail_list.append({
                    "ticker_code": ticker_code,
                    "ticker_name": ticker_name,
                    "reason": str(e)
                })



        # =========================
        # DB INSERT (한 번에 bulk)
        # =========================
        if all_result:

            self.postgres_insert.insert_data_to_postgres(
                "t_stock_original_price_data",
                all_result,
                "INCR"
            )

            self.logger.info(f"총 {len(all_result)}건 INSERT 완료")

        # =========================
        # 최종 결과 로그
        # =========================
        self.logger.info("========== 현재가 수집 완료 ==========")

        self.logger.info(
            f"성공: {len(success_list)}건 / "
            f"실패: {len(fail_list)}건 / "
            f"전체: {len(ticker_list)}건"
        )


# =========================
# 실행
# =========================
if __name__ == "__main__":

    print("현재 주가 전체 수집 시작")

    today_stock_collector = TodayStockCollector()
    today_stock_collector.insert_today_stock_data()