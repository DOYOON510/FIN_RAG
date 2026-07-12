import json
from typing import Any

from ollama import chat


# ollama list에서 확인한 실제 모델명으로 수정
MODEL_NAME = "qwen3:1.7b"


def search_news(ticker_name: str, query: str) -> dict[str, Any]:
    """
    특정 종목과 관련된 뉴스를 검색한다.

    현재는 Tool Calling 테스트를 위해 고정된 결과를 반환한다.

    Args:
        ticker_name: 조회할 종목명
        query: 검색할 뉴스 주제 또는 사용자 질문

    Returns:
        가짜 뉴스 검색 결과
    """
    print("\n[실제 Python 함수 실행]")
    print(f"search_news(ticker_name={ticker_name}, query={query})")

    return {
        "ticker_name": ticker_name,
        "query": query,
        "news": [
            {
                "title": f"{ticker_name}, 반도체 실적 전망 하향",
                "summary": "시장에서는 반도체 수요 둔화 가능성을 우려하고 있습니다.",
            }
        ],
    }


def search_stock(ticker_name: str, period_days: int = 30) -> dict[str, Any]:
    """
    특정 종목의 주식 데이터를 조회한다.

    현재는 Tool Calling 테스트를 위해 고정된 결과를 반환한다.

    Args:
        ticker_name: 조회할 종목명
        period_days: 최근 조회 기간

    Returns:
        가짜 주식 데이터 조회 결과
    """
    print("\n[실제 Python 함수 실행]")
    print(
        f"search_stock("
        f"ticker_name={ticker_name}, period_days={period_days})"
    )

    return {
        "ticker_name": ticker_name,
        "period_days": period_days,
        "start_close": 70000,
        "latest_close": 65800,
        "return_rate": -6.0,
    }


# LLM이 요청한 함수 이름과 실제 Python 함수를 연결
AVAILABLE_FUNCTIONS = {
    "search_news": search_news,
    "search_stock": search_stock,
}


def run_agent(user_question: str) -> str:
    """
    사용자 질문을 Ollama에 전달하고,
    필요한 도구를 실행한 뒤 최종 답변을 반환한다.
    """
    messages = [
        {
            "role": "system",
            "content": (
                "당신은 금융 데이터 분석 도우미입니다. "
                "뉴스나 사건, 이슈, 원인이 필요하면 search_news를 사용하세요. "
                "실제 주가, 종가, 수익률, 거래량 또는 가격 흐름이 필요하면 "
                "search_stock을 사용하세요. "
                "주가 변동 원인을 묻는 질문은 실제 주가 흐름과 관련 뉴스가 "
                "모두 필요하므로 두 도구를 모두 사용하세요. "
                "도구에 전달하는 검색어는 사용자의 원문 언어를 유지하세요."
                "종목명이나 검색어를 임의로 영어로 번역하지 마세요."
                "도구 결과에 없는 사실은 만들지 마세요."
                "도구가 반환한 정보만 사용해서 답변하세요."
                "도구 결과에 없는 날짜, 수치, 사실은 절대로 생성하지 마세요."
                "모르면 제공된 데이터에는 없습니다.라고 답하세요."
            ),
        },
        {
            "role": "user",
            "content": user_question,
        },
    ]

    # 한 질문에서 무한히 도구를 호출하지 않도록 제한
    for _ in range(5):
        # LLM 한테 물어보는 부분?
        response = chat(
            model=MODEL_NAME,
            messages=messages,
            tools=[search_news, search_stock],
        )

        assistant_message = response.message
        messages.append(assistant_message)
        print(messages)

        tool_calls = assistant_message.tool_calls or []

        # 도구 호출 요청이 없으면 최종 답변
        if not tool_calls:
            return assistant_message.content

        for tool_call in tool_calls:
            function_name = tool_call.function.name
            arguments = tool_call.function.arguments

            print("\n[LLM이 선택한 도구]")
            print(f"함수명: {function_name}")
            print(f"인자: {arguments}")

            function = AVAILABLE_FUNCTIONS.get(function_name)

            if function is None:
                tool_result = {
                    "success": False,
                    "message": f"지원하지 않는 함수입니다: {function_name}",
                }
            else:
                try:
                    tool_result = function(**arguments)
                except Exception as error:
                    tool_result = {
                        "success": False,
                        "message": str(error),
                    }

            print("[함수 실행 결과]")
            print(json.dumps(tool_result, ensure_ascii=False, indent=2))

            # 실행 결과를 다시 LLM에게 전달
            messages.append(
                {
                    "role": "tool",
                    "tool_name": function_name,
                    "content": json.dumps(
                        tool_result,
                        ensure_ascii=False,
                    ),
                }
            )

    return "도구 호출 횟수 제한을 초과했습니다."


if __name__ == "__main__":
    question = input("질문을 입력하세요: ")

    answer = run_agent(question)

    print("\n[최종 답변]")
    print(answer)