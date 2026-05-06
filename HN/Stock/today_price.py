import requests
from datetime import datetime
from src.common.common_const import StockConstant
from src.config.env_config import APIConstants

# 토큰 가져오기
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

# 현재 데이터
def get_today_price(ticker):

    url = "https://openapi.koreainvestment.com:9443/uapi/domestic-stock/v1/quotations/inquire-price"

    headers = {
        "authorization": f"Bearer {TOKEN}",
         "appkey": APIConstants.APP_KEY,
    "appsecret": APIConstants.APP_SECRET,
        "tr_id": "FHKST01010100"
    }

    params = {
        "fid_cond_mrkt_div_code": "J",
        "fid_input_iscd": ticker
    }

    res = requests.get(url, headers=headers, params=params)
    output = res.json().get("output", {})

    return [{
        '날짜': datetime.today().strftime("%Y%m%d"),
        '시가': int(output.get("stck_oprc", 0)),
        '고가': int(output.get("stck_hgpr", 0)),
        '저가': int(output.get("stck_lwpr", 0)),
        '종가': int(output.get("stck_prpr", 0)),
        '거래량': int(output.get("acml_vol", 0))
    }]


# if __name__ == "__main__":
#     df = get_today_price("005930")  # 삼성전자
#     print(df)