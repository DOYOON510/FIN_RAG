"""
Ollama + Qwen natural-language stock query smoke test.

Goal:
1. Ask a local Ollama model to convert a Korean stock question into SQL.
2. Run the generated SELECT query against t_stock_price_data.
3. Ask the model to answer the original question using the fetched rows.

Example:
    python src/analysis/ollama_stock_query_test.py
    python src/analysis/ollama_stock_query_test.py "삼성전자 주가 알려줘"
    python src/analysis/ollama_stock_query_test.py "2026-07-01~2026-07-11까지의 삼성전자 주가 알려줘"

Before running:
    ollama pull qwen2.5:1.5b
    ollama serve
    pip install requests sqlalchemy psycopg2-binary

Optional environment variables:
    OLLAMA_HOST=http://localhost:11434
    OLLAMA_MODEL=qwen2.5:1.5b
    OLLAMA_TIMEOUT=180
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import requests
from sqlalchemy import text


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from src.database.connect_postgres import PostgresDB


OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:1.5b")
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "180"))
OLLAMA_NUM_PREDICT = int(os.getenv("OLLAMA_NUM_PREDICT", "256"))
OPENAI_COMPAT_API_KEY = os.getenv("OPENAI_COMPAT_API_KEY", "ollama")

SAMSUNG_ELECTRONICS_KR = "\uc0bc\uc131\uc804\uc790"

# Keep Korean text escaped in the source to avoid Windows console/editor
# encoding issues while still running the user's Korean smoke-test question.
DEFAULT_QUESTION = f"{SAMSUNG_ELECTRONICS_KR} \uc8fc\uac00 \uc54c\ub824\uc918"

ALLOWED_TABLES = ("public.t_stock_price_data", "t_stock_price_data")
BLOCKED_SQL_PATTERN = re.compile(
    r"\b(insert|update|delete|drop|alter|truncate|create|grant|revoke|copy|merge)\b",
    re.IGNORECASE,
)


def call_ollama_for_sql(question: str) -> dict[str, Any]:
    today = datetime.now().strftime("%Y-%m-%d")
    system_prompt = f"""
너는 한국어 주식 질문을 PostgreSQL SELECT SQL로 바꾸는 도우미다.
반드시 JSON만 반환한다. markdown, 설명 문장, 코드블록은 쓰지 않는다.

오늘 날짜: {today}

사용 가능한 테이블:
public.t_stock_price_data

컬럼:
- trade_date: text, format YYYY-MM-DD. 날짜 비교, 정렬, interval 계산에는 trade_date::date를 사용한다.
- ticker_name: text
- ticker_code: text
- open_price: numeric
- high_price: numeric
- low_price: numeric
- close_price: numeric
- volume: numeric
- daily_change: numeric
- ma_20: numeric
- volatility: numeric
- dd_high: numeric
- ret_low: numeric

반환 JSON 형식:
{{
  "sql": "SELECT ...",
  "params": {{"ticker_code": "005930", "limit": 10}},
  "reason": "짧은 한국어 설명"
}}

규칙:
- SQL은 SELECT 하나만 생성한다.
- public.t_stock_price_data만 사용한다.
- SELECT * 금지. 필요한 컬럼만 명시한다.
- 출력 컬럼은 기본적으로 trade_date, ticker_name, ticker_code, open_price, high_price, low_price, close_price, volume, daily_change를 사용한다.
- 값은 SQL에 직접 넣지 말고 :ticker_code, :start_date, :end_date, :limit 같은 named bind parameter를 사용한다.
- Samsung Electronics, 삼성전자, 삼선전가, 삼성전가처럼 물으면 ticker_code = :ticker_code, params.ticker_code = "005930"을 사용한다.
- 사용자가 "2026-07-01~2026-07-11"처럼 명시 날짜 범위를 주면 trade_date::date BETWEEN :start_date::date AND :end_date::date를 사용한다.
- 사용자가 "최근 일주일", "최근 1주일", "지난 일주일"이라고 하면 LIMIT로 대체하지 말고 최근 7일 날짜 조건을 사용한다.
- "최근 일주일"의 기준일은 해당 종목의 DB상 가장 최근 거래일로 잡는다.
- 최근 일주일 SQL 예시:
  trade_date::date BETWEEN (
      SELECT MAX(trade_date::date) - INTERVAL '7 days'
      FROM public.t_stock_price_data
      WHERE ticker_code = :ticker_code
  ) AND (
      SELECT MAX(trade_date::date)
      FROM public.t_stock_price_data
      WHERE ticker_code = :ticker_code
  )
- 사용자가 기간을 전혀 말하지 않고 "주가 알려줘", "현재가 알려줘"처럼 물으면 최신 거래일 기준 최근 10개 거래일을 조회하고 LIMIT :limit를 사용한다.
- 최신/최근 조회는 ORDER BY trade_date::date DESC를 사용한다.
- reason은 반드시 한국어로 작성한다.
""".strip()

    chat_payload = {
        "model": OLLAMA_MODEL,
        "format": "json",
        "stream": False,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question},
        ],
        "options": {
            "temperature": 0,
            "num_predict": OLLAMA_NUM_PREDICT,
        },
    }

    try:
        response = requests.post(
            f"{OLLAMA_HOST}/api/chat",
            json=chat_payload,
            timeout=OLLAMA_TIMEOUT,
        )
    except requests.exceptions.ReadTimeout as exc:
        raise RuntimeError(
            f"Ollama response timed out after {OLLAMA_TIMEOUT} seconds. "
            "The model may still be loading or the selected model may be too "
            "large for this machine. Try running the script again, set a "
            "larger OLLAMA_TIMEOUT, or use a smaller model such as qwen2.5:3b."
        ) from exc

    if response.status_code == 404 and "model" in response.text.lower():
        raise RuntimeError(
            f"Ollama model not found: {OLLAMA_MODEL}. "
            f"Run `ollama pull {OLLAMA_MODEL}` first, or set OLLAMA_MODEL "
            "to one of the names shown by `ollama list`."
        )

    if response.status_code == 404:
        prompt = f"{system_prompt}\n\nUser question:\n{question}"
        response = requests.post(
            f"{OLLAMA_HOST}/api/generate",
            json={
                "model": OLLAMA_MODEL,
                "format": "json",
                "stream": False,
                "prompt": prompt,
                "options": {
                    "temperature": 0,
                    "num_predict": OLLAMA_NUM_PREDICT,
                },
            },
            timeout=OLLAMA_TIMEOUT,
        )
        if response.status_code == 404 and "model" in response.text.lower():
            raise RuntimeError(
                f"Ollama model not found: {OLLAMA_MODEL}. "
                f"Run `ollama pull {OLLAMA_MODEL}` first, or set OLLAMA_MODEL "
                "to one of the names shown by `ollama list`."
            )
        if response.status_code == 404:
            response = requests.post(
                f"{OLLAMA_HOST}/v1/chat/completions",
                headers={"Authorization": f"Bearer {OPENAI_COMPAT_API_KEY}"},
                json={
                    "model": OLLAMA_MODEL,
                    "response_format": {"type": "json_object"},
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": question},
                    ],
                    "temperature": 0,
                    "max_tokens": OLLAMA_NUM_PREDICT,
                },
                timeout=OLLAMA_TIMEOUT,
            )
            if response.status_code == 404:
                raise RuntimeError(
                    "LLM server endpoint not found. Tried "
                    f"{OLLAMA_HOST}/api/chat, {OLLAMA_HOST}/api/generate, "
                    f"and {OLLAMA_HOST}/v1/chat/completions. "
                    "If you are using Ollama, run `ollama serve` and check "
                    "`ollama list`. Also make sure OLLAMA_HOST points to the "
                    "actual Ollama server, usually http://localhost:11434."
                )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
        else:
            response.raise_for_status()
            content = response.json()["response"]
    else:
        response.raise_for_status()
        content = response.json()["message"]["content"]

    return json.loads(content)


def validate_generated_sql(sql: str) -> str:
    normalized_sql = " ".join(sql.strip().split())
    lowered_sql = normalized_sql.lower()

    if not lowered_sql.startswith("select "):
        raise ValueError(f"Only SELECT SQL is allowed: {sql}")

    if ";" in normalized_sql:
        raise ValueError(f"Semicolons are not allowed: {sql}")

    if BLOCKED_SQL_PATTERN.search(normalized_sql):
        raise ValueError(f"Blocked SQL keyword found: {sql}")

    if not any(table in lowered_sql for table in ALLOWED_TABLES):
        raise ValueError(f"Only t_stock_price_data can be queried: {sql}")

    return normalized_sql


def repair_trade_date_casts(sql: str) -> str:
    repaired_sql = re.sub(
        r"MAX\(\s*trade_date\s*\)\s*-\s*INTERVAL",
        "MAX(trade_date::date) - INTERVAL",
        sql,
        flags=re.IGNORECASE,
    )
    repaired_sql = re.sub(
        r"MAX\(\s*trade_date\s*\)",
        "MAX(trade_date::date)",
        repaired_sql,
        flags=re.IGNORECASE,
    )
    repaired_sql = re.sub(
        r"ORDER BY\s+trade_date\s+DESC",
        "ORDER BY trade_date::date DESC",
        repaired_sql,
        flags=re.IGNORECASE,
    )
    repaired_sql = re.sub(
        r"ORDER BY\s+trade_date\s+ASC",
        "ORDER BY trade_date::date ASC",
        repaired_sql,
        flags=re.IGNORECASE,
    )
    return repaired_sql


def normalize_params(params: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(params or {})

    if "limit" in normalized:
        normalized["limit"] = int(normalized["limit"])

    for key in ("start_date", "end_date"):
        if key in normalized:
            datetime.strptime(str(normalized[key]), "%Y-%m-%d")

    return normalized


def make_json_safe(value: Any) -> Any:
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d")

    if isinstance(value, (int, float, str, bool)) or value is None:
        return value

    return str(value)


def prepare_rows_for_answer(rows: list[dict], max_rows: int = 30) -> list[dict]:
    return [
        {key: make_json_safe(value) for key, value in row.items()}
        for row in rows[:max_rows]
    ]


def call_ollama_for_answer(question: str, sql: str, rows: list[dict]) -> str:
    answer_rows = prepare_rows_for_answer(rows)
    system_prompt = """
너는 DB에서 조회한 주가 데이터를 근거로 사용자 질문에 답하는 한국어 금융 데이터 도우미다.
반드시 제공된 rows 안의 데이터만 근거로 답한다.
사용자가 동향, 흐름, 변동, 최고/최저, 거래량, 특정 날짜 비교 등을 물으면 rows를 계산/비교해서 답한다.
사용자가 단순히 주가를 물으면 핵심 가격과 기간을 간단히 알려준다.
투자 조언, 매수/매도 추천, 수익률 보장 표현은 하지 않는다.
답변은 자연스러운 한국어로 작성한다.
""".strip()
    user_prompt = f"""
사용자 질문:
{question}

실행한 SQL:
{sql}

DB 조회 결과 rows:
{json.dumps(answer_rows, ensure_ascii=False, indent=2)}

위 rows를 근거로 사용자 질문에 직접 답해줘.
""".strip()

    try:
        response = requests.post(
            f"{OLLAMA_HOST}/api/chat",
            json={
                "model": OLLAMA_MODEL,
                "stream": False,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "options": {
                    "temperature": 0.2,
                    "num_predict": max(OLLAMA_NUM_PREDICT, 512),
                },
            },
            timeout=OLLAMA_TIMEOUT,
        )
    except requests.exceptions.ReadTimeout as exc:
        raise RuntimeError(
            f"Ollama answer timed out after {OLLAMA_TIMEOUT} seconds. "
            "Try a smaller model or increase OLLAMA_TIMEOUT."
        ) from exc

    if response.status_code == 404:
        response = requests.post(
            f"{OLLAMA_HOST}/api/generate",
            json={
                "model": OLLAMA_MODEL,
                "stream": False,
                "prompt": f"{system_prompt}\n\n{user_prompt}",
                "options": {
                    "temperature": 0.2,
                    "num_predict": max(OLLAMA_NUM_PREDICT, 512),
                },
            },
            timeout=OLLAMA_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()["response"].strip()

    response.raise_for_status()
    return response.json()["message"]["content"].strip()


class StockPriceRepository:
    def __init__(self, db: PostgresDB):
        self.db = db

    def fetch_by_generated_sql(self, sql: str, params: dict[str, Any]) -> list[dict]:
        with self.db.get_postgres_db() as session:
            result = session.execute(text(sql), params)
            return [dict(row._mapping) for row in result]


def format_stock_rows(rows: list[dict]) -> str:
    preferred_columns = [
        "trade_date",
        "ticker_name",
        "ticker_code",
        "open_price",
        "high_price",
        "low_price",
        "close_price",
        "volume",
        "daily_change",
    ]
    columns = [column for column in preferred_columns if column in rows[0]]
    columns.extend(column for column in rows[0] if column not in columns)

    header = " | ".join(columns)
    lines = [header, "-" * len(header)]

    for row in rows:
        values = []
        for column in columns:
            value = row.get(column)
            if hasattr(value, "strftime"):
                value = value.strftime("%Y-%m-%d")
            elif column == "daily_change" and value is not None:
                value = f"{float(value):.4f}"
            values.append(str(value))

        lines.append(" | ".join(values))

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("question", nargs="*")
    args = parser.parse_args()

    question = " ".join(args.question).strip()
    if not question:
        question = input("질문 입력: ").strip()

    if not question:
        question = DEFAULT_QUESTION

    print(f"[question] {question}")
    print(f"[ollama] host={OLLAMA_HOST}, model={OLLAMA_MODEL}")

    raw_query = call_ollama_for_sql(question)
    sql = validate_generated_sql(str(raw_query.get("sql", "")))
    sql = repair_trade_date_casts(sql)
    params = normalize_params(raw_query.get("params", {}))

    print("[generated]")
    print(json.dumps({"sql": sql, "params": params, "reason": raw_query.get("reason")}, ensure_ascii=False, indent=2))

    repository = StockPriceRepository(db=PostgresDB())
    rows = repository.fetch_by_generated_sql(sql, params)
    if not rows:
        print("[result] no rows")
        return

    print("[result]")
    print(format_stock_rows(rows))

    answer = call_ollama_for_answer(question, sql, rows)
    print("[answer]")
    print(answer)


if __name__ == "__main__":
    main()
