import time
import requests
from datetime import datetime

from src.common.common_const import StockConstant
from src.config.env_config import APIConstants
from src.collector.origin_stock_collector import OriginStockCollector

from src.common.setup_log import SetupLogger

from src.database.connect_postgres import PostgresDB
from src.database.postgres_common import PostgresInsert
from src.database.postgres_common import PostgresUpdate


class TodayStockCollector:
    """
    KIS API 기반 '실시간 현재가' 수집 클래스

    전체 흐름:
    1. Access Token 발급
    2. t_ticker_info 기준 ticker 목록 조회
    3. 종목별 현재가 API 호출 및 데이터 수집
    4. 수집 결과 DB insert
    """

    def __init__(self):
        """
        초기 설정

        구성 요소:
        param stock_collector: ticker 목록 조회 재사용 (OriginStockCollector)
        param token_url      : KIS 토큰 발급 URL
        param stock_url      : KIS 현재가 조회 URL
        param api_key        : KIS API appkey
        param api_secret     : KIS API appsecret

        """

        self.logger = SetupLogger.get_logger()
        self.db = PostgresDB()
        self.postgres_insert = PostgresInsert()
        self.postgres_update = PostgresUpdate()

        self.stock_collector = OriginStockCollector()

        # API URL
        self.token_url = StockConstant.token_url
        self.stock_url = StockConstant.stock_url

        # API Key
        self.api_key = APIConstants.API_KEY
        self.api_secret = APIConstants.API_SECRET



    # =========================
    # 1. Access Token 발급
    # =========================
    def get_access_token(self):
        """
        KIS API access token 발급

        흐름:
        1. 한국투자증권 API 사용하여 호출
        2. HTTP status 200 여부 검증 (실패 시 예외 발생)
        3. 응답 JSON에서 access_token 추출 후 반환

        return : access_token
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
    def get_today_price(self, access_token, ticker_sno ,ticker_code, ticker_name):
        """
        단일 종목 현재가 조회

        흐름:
        1. KIS API 호출
        2. 응답 검증
        3. 필요한 가격 데이터 추출
        4. dict 형태로 변환

        :param access_token: get_access_token()으로 발급받은 인증 토큰
        :param ticker_sno: t_ticker_info PK 값
        :param ticker_code : 종목 코드 (예시: "005930")
        :param ticker_name : 종목명 (예시: "삼성전자")

        :return            : DB insert용 현재가 데이터 1건

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

        high_price = int(output.get("stck_hgpr", 0))
        low_price = int(output.get("stck_lwpr", 0))

        if high_price == 0 or low_price == 0:
            self.logger.warning(
                f"[{ticker_code}] {ticker_name} 비정상 데이터 발견 - "
                f"시가: {int(output.get('stck_oprc', 0))} | "
                f"고가: {high_price} | "
                f"저가: {low_price} | "
                f"종가: {int(output.get('stck_prpr', 0))} | "
                f"거래량: {int(output.get('acml_vol', 0))}"
            )

            self.postgres_update.update_data_to_postgres(
                "t_ticker_info",
                "use_yn",
                ticker_sno,
                False
            )

            self.logger.info(
                f"[{ticker_code}] {ticker_name} "
                f"use_yn=False 처리 완료"
            )

            return []

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
        단일 종목 현재가 조회 (KIS API)

        흐름:
        1. 현재가 API GET 호출
        2. HTTP status 200 여부 검증 (실패 시 예외 발생)
        3. 응답 rt_cd 검증 (0: 성공, 그 외: 실패 → 예외 발생)
        4. output 필드에서 가격 데이터 추출 후 dict 리스트로 반환

        """

        ticker_list = self.stock_collector.get_ticker_info()
        access_token = self.get_access_token()

        self.logger.info(f"총 {len(ticker_list)} 종목 현재가 수집 시작")

        success_count = 0
        fail_list = []

        # 전체 결과 누적 (batch insert용)
        all_result = []

        for idx, ticker_info in enumerate(ticker_list):

            time.sleep(0.2)  # API rate limit 방지

            ticker_sno = ticker_info["ticker_sno"]
            ticker_code = ticker_info["ticker_code"]
            ticker_name = ticker_info["ticker_name"]

            self.logger.info(
                f"[{idx + 1}/{len(ticker_list)}] "
                f"{ticker_code} {ticker_name} 현재가 수집 중"
            )

            try:
                result = self.get_today_price(
                    access_token,
                    ticker_sno,
                    ticker_code,
                    ticker_name
                )
                if result:
                    all_result.extend(result)
                    success_count += 1

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
            f"성공: {success_count}건 / "
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