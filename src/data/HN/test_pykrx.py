import requests
import pandas as pd
from datetime import datetime, timedelta
from pykrx import stock

# =========================
# 0️⃣ Pandas 옵션
# =========================
pd.set_option('display.max_columns', None)
pd.set_option('display.width', 200)
pd.set_option('display.float_format', '{:.2f}'.format)

# =========================
# 1️⃣ 한국투자증권 API 토큰 발급
# =========================
APP_KEY = "PSZQN8JA68rxeL7oZtOk738QwNdgn96JSxKf"
APP_SECRET = "r3DBY5AJYrsbNrinK90LF/Nvo2zkN7dp09s3nxAcXI5YYhvuc+l2bNlcdWKfLPdRD5zWLBhB5S60ICShftQlid+sF8uw4Rfc6/7wRipjl1y/D8Mdyy0Frys757dsMTXMNCzib78Rck523uVg/CxHhqJE5dRA6o6GSuAGNLG3hibhirNc0bg="


def get_access_token():
    url = "https://openapi.koreainvestment.com:9443/oauth2/tokenP"
    data = {
        "grant_type": "client_credentials",
        "appkey": APP_KEY,
        "appsecret": APP_SECRET
    }
    res = requests.post(url, json=data)
    token = res.json().get("access_token")

    if token is None:
        raise ValueError(f"토큰 발급 실패: {res.json()}")

    return token


TOKEN = get_access_token()

# =========================
# 2️⃣ 오늘 주가 조회 함수
# =========================
def get_today_price(ticker):
    url = "https://openapi.koreainvestment.com:9443/uapi/domestic-stock/v1/quotations/inquire-price"

    headers = {
        "Content-Type": "application/json",
        "authorization": f"Bearer {TOKEN}",
        "appkey": APP_KEY,
        "appsecret": APP_SECRET,
        "tr_id": "FHKST01010100"
    }

    params = {
        "fid_cond_mrkt_div_code": "J",
        "fid_input_iscd": ticker
    }

    res = requests.get(url, headers=headers, params=params)
    output = res.json().get("output", {})

    today_df = pd.DataFrame([{
        '날짜': datetime.today(),
        '시가': int(output.get("stck_oprc", 0)),
        '고가': int(output.get("stck_hgpr", 0)),
        '저가': int(output.get("stck_lwpr", 0)),
        '종가': int(output.get("stck_prpr", 0)),
        '거래량': int(output.get("acml_vol", 0))
    }])

    return today_df


# =========================
# 3️⃣ 과거 1년 데이터 조회 (🔥 핵심 수정)
# =========================
def get_past_6months(ticker):
    end = datetime.today().strftime("%Y%m%d")
    start = (datetime.today() - timedelta(days=365)).strftime("%Y%m%d")  # 🔥 1년

    df = stock.get_market_ohlcv(start, end, ticker).reset_index()

    df = df[['날짜', '시가', '고가', '저가', '종가', '거래량']]

    return df


# =========================
# 4️⃣ 지표 계산
# =========================
def add_indicators(df):
    df = df.sort_values("날짜").reset_index(drop=True)

    # 🔥 이동평균 (정확한 계산)
    df['이동평균'] = df['종가'].rolling(20).mean()

    # 일간 등락률
    df['일간등락률(%)'] = df['종가'].pct_change() * 100

    # 변동성 (20일)
    df['변동성'] = df['종가'].rolling(20).std()

    # 누적수익률
    df['누적수익률(%)'] = (df['종가'] / df['종가'].iloc[0] - 1) * 100

    # 최고/최저 대비
    df['최고가대비(%)'] = (df['종가'] / df['고가'].rolling(180).max() - 1) * 100
    df['최저가대비(%)'] = (df['종가'] / df['저가'].rolling(180).min() - 1) * 100

    return df


# =========================
# 5️⃣ 통합 함수
# =========================
def show_stock_history(ticker):
    past_df = get_past_6months(ticker)
    today_df = get_today_price(ticker)

    # 🔥 날짜 타입 통일
    past_df['날짜'] = pd.to_datetime(past_df['날짜'])
    today_df['날짜'] = pd.to_datetime(today_df['날짜'])

    combined_df = pd.concat([past_df, today_df], ignore_index=True)

    combined_df = add_indicators(combined_df)

    # 🔥 6개월만 필터링
    cutoff = datetime.today() - timedelta(days=180)
    combined_df = combined_df[combined_df['날짜'] >= cutoff]

    # 컬럼 순서 유지
    combined_df = combined_df[['날짜', '시가', '고가', '저가', '종가', '거래량',
                               '이동평균', '일간등락률(%)', '변동성', '누적수익률(%)',
                               '최고가대비(%)', '최저가대비(%)']]

    return combined_df


# =========================
# 6️⃣ 실행
# =========================
ticker = "005930"  # 삼성전자
df = show_stock_history(ticker)

print(df.tail(10))


# =========================
# 7️⃣ 엑셀 저장
# =========================
df.to_excel("삼성전자_6개월_데이터.xlsx", index=False)

print("엑셀 저장 완료")