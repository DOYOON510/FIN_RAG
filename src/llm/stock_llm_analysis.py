# -*- coding: utf-8 -*-
"""
DB(t_stock_original_price_data)에서 주가 데이터를 가져와
Ollama 로컬 LLM으로 해석 리포트를 생성하는 테스트 스크립트.

사전 준비:
  1. Ollama 설치 후 모델 다운로드:  ollama pull exaone3.5
  2. pip install psycopg2-binary ollama
실행:
  python stock_llm_analysis.py            # 기본 종목(첫 번째 종목)
  python stock_llm_analysis.py 3S         # 종목명 지정
"""
import sys

import psycopg2
import psycopg2.extras
import ollama

DB_CONFIG = dict(
    host="183.100.185.138",
    port=5433,
    dbname="vectordb",
    user="aidev",
    password="dev00",
)

OLLAMA_MODEL = "exaone3.5"  # 설치한 모델명으로 변경 가능 (예: qwen2.5:7b)
DAYS = 10  # 최근 며칠치 데이터를 분석할지


def fetch_price_data(ticker_name=None):

    """
       종목의 최근 주가 데이터를 DB에서 조회

       처리 흐름:
       1. DB 접속 및 커서 생성 (RealDictCursor → 결과를 컬럼명으로 접근)
       2. 종목명 미지정 시 이름순 첫 번째 종목 자동 선택
       3. 해당 종목의 최근 N일(DAYS) OHLCV 데이터 조회 후 날짜 오름차순 정렬
       4. DB 연결 종료 후 결과 반환

       param ticker_name: 종목명 (예: "경농"). None이면 DB에서 첫 번째 종목 자동 선택

       return: (ticker_name, prices) 튜플
               ticker_name(str)   - 실제 조회된 종목명
               prices(list[dict]) - 날짜 오름차순 주가 데이터
    """

    conn = psycopg2.connect(**DB_CONFIG, connect_timeout=10)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    if ticker_name is None:
        cur.execute(
            "SELECT ticker_name FROM t_stock_original_price_data "
            "WHERE del_yn = false ORDER BY ticker_name LIMIT 1"
        )
        ticker_name = cur.fetchone()["ticker_name"] #한줄 조회

    cur.execute(
        """
        SELECT trade_date, ticker_name, ticker_code,
               open_price, high_price, low_price, close_price, volume
        FROM t_stock_original_price_data
        WHERE ticker_name = %s AND del_yn = false
        ORDER BY trade_date DESC
        LIMIT %s
        """,
        (ticker_name, DAYS),
    )
    prices = cur.fetchall()[::-1]  #여러 줄 조회

    conn.close()
    return ticker_name, prices


def build_price_table(prices):

    """
        LLM에 넘길 주가 표를 파이썬에서 확정 문자열로 생성 (숫자 오염 방지)

        처리 흐름:
        1. 표 헤더 행 생성
        2. 각 행마다 전일 종가 대비 등락률을 코드에서 직접 계산
           (첫 행은 이전 값이 없으므로 "-" 표시)
        3. 시가/고가/저가/종가는 천 단위 콤마, 등락률은 부호 포함 소수 2자리로 서식화
        4. 모든 행을 줄바꿈으로 이어 붙여 하나의 문자열로 반환

        param prices: fetch_price_data가 반환한 주가 데이터 리스트(list[dict])

        return: str - 파이프(|)로 구분된 주가 표 문자열. LLM 프롬프트에 그대로 삽입됨
    """

    lines = ["날짜 | 시가 | 고가 | 저가 | 종가 | 거래량 | 전일대비"]
    prev_close = None
    for p in prices:
        close = float(p["close_price"])
        if prev_close:
            change = (close - prev_close) / prev_close * 100
            change_str = f"{change:+.2f}%"
        else:
            change_str = "-"
        lines.append(
            f"{p['trade_date']} | {float(p['open_price']):,.0f} | "
            f"{float(p['high_price']):,.0f} | {float(p['low_price']):,.0f} | "
            f"{close:,.0f} | {p['volume']:,} | {change_str}"
        )
        prev_close = close
    return "\n".join(lines)


def analyze_with_llm(ticker_name, price_table):

    """
        확정된 주가 표를 프롬프트로 묶어 로컬 LLM에 해석 요청

        처리 흐름:
        1. 애널리스트 역할 부여 + 주가 표로 프롬프트 구성
           (표에 없는 숫자를 만들지 말라는 환각 억제 지시 포함)
        2. ollama.chat으로 로컬 모델 호출
        3. 응답 본문 텍스트만 반환

        param ticker_name: 종목명(str)
        param price_table: build_price_table가 만든 주가 표 문자열(str)

        return: str - LLM이 생성한 해석 리포트 텍스트
    """

    prompt = f"""당신은 증권 애널리스트입니다. 아래 데이터를 바탕으로 '{ticker_name}' 종목의 최근 흐름을 분석해 주세요.

[주가 데이터]
{price_table}

다음 형식으로 한국어로 작성해 주세요:
1. 최근 주가 흐름 요약 (2~3문장)
2. 거래량 특이사항
3. 종합 의견 (1~2문장)

주의: 표에 없는 숫자를 만들어내지 말고, 표에 있는 값만 인용하세요."""

    response = ollama.chat(
        model=OLLAMA_MODEL,
        messages=[{"role": "user", "content": prompt}],
    )
    return response["message"]["content"]


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ticker_arg = sys.argv[1] if len(sys.argv) > 1 else None

    print("DB에서 데이터 조회 중...")
    ticker_name, prices = fetch_price_data(ticker_arg)
    if not prices:
        print(f"'{ticker_arg}' 종목 데이터가 없습니다.")
        return

    price_table = build_price_table(prices)
    print(f"\n=== {ticker_name} 최근 {len(prices)}일 주가 ===")
    print(price_table)

    print(f"\nLLM({OLLAMA_MODEL}) 분석 중... (로컬 모델이라 수십 초 걸릴 수 있어요)")
    result = analyze_with_llm(ticker_name, price_table)
    print("\n=== LLM 분석 결과 ===")
    print(result)


if __name__ == "__main__":
    main()
