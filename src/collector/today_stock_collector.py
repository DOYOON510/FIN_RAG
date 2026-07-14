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
        param api_key        : KIS API apikey
        param api_secret     : KIS API apisecret

        """

        self.logger = SetupLogger.get_logger()
        self.db = PostgresDB()
        self.postgres_insert = PostgresInsert()
        self.postgres_update = PostgresUpdate()

        self.stock_collector = OriginStockCollector()

        # API URL
        self.token_url = StockConstant.token_url
        self.stock_url = StockConstant.stock_url
        self.holiday_url = StockConstant.holiday_url

        # API Key
        self.api_key = APIConstants.API_KEY
        self.api_secret = APIConstants.API_SECRET

        # 발급받은 access token 캐시 (중복 발급 방지 - KIS는 1분당 1회 제한)
        self.access_token = None



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

        # 이미 발급받은 토큰이 있으면 재사용 (KIS 1분당 1회 발급 제한 회피)
        if self.access_token:
            return self.access_token

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
            error_list = [{"error_type": "HTTP 오류",
                           "error_dtl": f"HTTP {res.status_code} | {res.text}","request_url": self.token_url}]
            self.postgres_insert.insert_data_to_postgres("t_error_log", error_list)
            raise Exception(f"토큰 발급 실패 - {res.text}")

        result = res.json()
        access_token = result.get("access_token")

        # 캐시에 저장 → 같은 인스턴스에서 재호출 시 재발급 안 함
        self.access_token = access_token

        self.logger.info("access token 발급 완료")

        return access_token

    # =========================
    # 2. 개장일(영업일) 여부 확인
    # =========================
    def is_market_open(self, access_token, base_date=None):
        """
        오늘이 증시 개장일인지 확인 (KIS 국내휴장일조회 API)

        주말/공휴일/임시휴장일이면 개장하지 않으므로 수집을 건너뛰기 위한 사전 체크.

        흐름:
        1. KIS 휴장일 조회 API(CTCA0903R) 호출
        2. 응답 output 목록에서 기준일자(base_date)의 개장일여부(opnd_yn) 확인
        3. "Y"이면 개장일(True), 그 외이면 휴장일(False) 반환

        :param access_token: get_access_token()으로 발급받은 인증 토큰
        :param base_date   : 확인할 기준일자 (YYYYMMDD). 미지정 시 오늘 날짜
        :return            : 개장일이면 True, 휴장일이면 False
        """

        if base_date is None:
            base_date = datetime.today().strftime("%Y%m%d")

        headers = {
            "content-type": "application/json; charset=utf-8",
            "authorization": f"Bearer {access_token}",
            "appkey": self.api_key,
            "appsecret": self.api_secret,
            "tr_id": "CTCA0903R",
            "custtype": "P"
        }

        params = {
            "BASS_DT": base_date,
            "CTX_AREA_NK": "",
            "CTX_AREA_FK": ""
        }

        res = requests.get(
            url=self.holiday_url,
            headers=headers,
            params=params
        )

        if res.status_code != 200:
            error_list = [{"error_type": "HTTP 오류",
                           "error_dtl": f"휴장일 조회 실패 | HTTP {res.status_code} | {res.text}",
                           "request_url": self.holiday_url}]
            self.postgres_insert.insert_data_to_postgres("t_error_log", error_list)
            raise Exception(f"휴장일 조회 실패 - {res.text}")

        result = res.json()

        rt_cd = result.get("rt_cd")
        msg1 = result.get("msg1")

        if rt_cd != "0":
            error_list = [{"error_type": "휴장일 조회 오류",
                           "error_dtl": f"rt_cd={rt_cd} | msg={msg1}",
                           "request_url": self.holiday_url}]
            self.postgres_insert.insert_data_to_postgres("t_error_log", error_list)
            raise Exception(f"휴장일 조회 실패 - {msg1}")

        # output: 기준일자부터의 일자별 개장 정보 목록
        # opnd_yn = 개장일여부 (Y: 개장, N: 휴장)
        output = result.get("output", [])

        for day_info in output:
            if day_info.get("bass_dt") == base_date:
                return day_info.get("opnd_yn") == "Y"

        # 기준일자 정보를 찾지 못한 경우 안전하게 휴장 처리
        self.logger.warning(f"휴장일 조회 응답에서 {base_date} 정보를 찾지 못함 - 원본: {output}")
        return False

    # =========================
    # 3. 종목 현재가 조회
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

        if res.status_code != 200:
            error_list = [{"error_type": "HTTP 오류",
                           "error_dtl": f"[{ticker_code}] {ticker_name} | HTTP {res.status_code} | {res.text}",
                           "request_url": self.stock_url}]
            self.postgres_insert.insert_data_to_postgres("t_error_log", error_list)
            raise Exception(f"현재가 조회 실패 - {res.text}")



        result = res.json()

        rt_cd = result.get("rt_cd")
        msg1 = result.get("msg1")

        if rt_cd != "0":
            error_list = [
                {"error_type": " HTTP 오류", "error_dtl": f"[{ticker_code}] {ticker_name} | rt_cd={rt_cd} | msg={msg1}",
                 "request_url": self.stock_url}]
            self.postgres_insert.insert_data_to_postgres("t_error_log", error_list)
            raise Exception(f"{ticker_code} {ticker_name} 현재가 조회 실패 - {msg1}")

        #result 구조 : {"rt_cd": "0", 응답 상태 코드 0: 성공 그외 : 실패
        #              "msg_cd": "AP00000", 메시지 코드
        #              "msg1": "정상처리되었습니다",
        #              "output": { ... }}

        output = result.get("output", {})

        # 주말/휴장일 방어는 수집 시작 전 is_market_open() 에서 처리하므로
        # 여기서는 개별 종목의 비정상 데이터(고가/저가 0)만 방어한다.
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
                ticker_sno,
                "use_yn",
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
    # 4. 전체 종목 현재가 수집 + INSERT
    # =========================
    def insert_today_stock_data(self,base_date = None):
        """
        단일 종목 현재가 조회 (KIS API)

        흐름:
        1. 현재가 API GET 호출
        2. HTTP status 200 여부 검증 (실패 시 예외 발생)
        3. 응답 rt_cd 검증 (0: 성공, 그 외: 실패 → 예외 발생)
        4. output 필드에서 가격 데이터 추출 후 dict 리스트로 반환

        """

        access_token = self.get_access_token()

        # 개장일 여부 사전 확인 (주말/공휴일이면 수집 전체 스킵)
        if not self.is_market_open(access_token, base_date):
            self.logger.info(
                f"{base_date or datetime.today().strftime('%Y%m%d')} 은(는) 증시 휴장일 - 현재가 수집 스킵"
            )
            return []

        ticker_list = self.stock_collector.get_ticker_info()

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

                error_list = [{"error_type": "현재가 수집 오류", "error_dtl": f"[{ticker_code}] {ticker_name} | {str(e)}",
                               "request_url": self.stock_url}]
                self.postgres_insert.insert_data_to_postgres("t_error_log", error_list)
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

        return fail_list


# =========================
# 실행
# =========================

if __name__ == "__main__":

    print("현재 주가 전체 수집 시작")

    today_stock_collector = TodayStockCollector()
    fail_list = today_stock_collector.insert_today_stock_data()

