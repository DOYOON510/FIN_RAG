import json
from typing import Any
from ollama import chat
import time

from src.common.setup_log import SetupLogger
from src.llm.prompts import Prompts

class LLMToolCalling:
    """
    Ollama의 Tool Calling 기능을 사용하는 Agent 클래스.

    사용자의 질문을 LLM에 전달하고,
    LLM이 요청한 Python 함수를 실행한 뒤,
    함수 실행 결과를 다시 LLM에 전달하여 최종 답변을 생성한다.

    전체 흐름:
        1. 사용자 질문과 시스템 프롬프트를 messages에 저장
        2. Ollama LLM 호출
        3. LLM이 도구 호출을 요청했는지 확인
        4. 요청한 Python 함수 실행
        5. 함수 실행 결과를 messages에 추가
        6. 함수 결과를 포함하여 Ollama를 다시 호출
        7. 도구 호출 요청이 없으면 최종 답변 반환
    """

    def __init__(self):
        """
        ToolCalling 클래스 초기 설정.

        - 공통 Logger 생성
        - 사용할 Ollama 모델 지정
        - 시스템 프롬프트 객체 생성
        - LLM이 요청한 함수명과 실제 Python 함수를 연결
        """
        self.logger = SetupLogger.get_logger()
        # self.MODEL_NAME = "qwen3:4b"
        self.MODEL_NAME = "qwen3:1.7b"
        self.prompts = Prompts()

        # LLM이 요청한 함수 이름과 실제 Python 함수를 연결
        self.AVAILABLE_FUNCTIONS = {
            "search_news": self.search_news,
            "search_stock": self.search_stock,
        }


    def search_news(self, ticker_name: str, query: str) -> dict[str, Any]:
        """
        기업 또는 산업과 관련된 뉴스, 사건, 이슈, 전망,
        주가 변동 원인을 검색한다.

        주가 수치, 종가, 수익률을 조회하는 함수는 아니다.
        사용자가 특정 종목의 주가 상승 또는 하락 이유를 질문하면
        search_stock 함수와 함께 사용할 수 있다.

        :param ticker_name: 사용자가 질문에서 언급한 종목명 (종목이 없으면 빈 문자열)
        :param query: 사용자의 원문 언어를 유지한 뉴스 검색어
    
        Returns:
            뉴스 제목과 요약
        """
        self.logger.info("\n[Python 함수 실행 : search_news]")
        self.logger.info(f"search_news(ticker_name={ticker_name}, query={query})")
    
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
    
    
    def search_stock(self, ticker_name: str, period_days: int = 30) -> dict[str, Any]:
        """
        특정 종목의 실제 주가, 종가, 수익률, 거래량, 가격 흐름을 조회한다.
    
        뉴스나 주가 변동 원인을 검색하는 도구가 아니다.
        사용자가 주가 상승 또는 하락 이유를 물으면 search_news와 함께 사용한다.
    
        Args:
            ticker_name: 사용자가 언급한 종목명
            period_days: 최근 조회 기간. 기간이 없으면 30일
    
        Returns:
            시작 종가, 최근 종가, 기간 수익률
        """
        self.logger.info("\n[Python 함수 실행 : search_stock]")
        self.logger.info(
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


    def run_agent(self, user_question: str) -> str:
        """
        사용자 질문을 Ollama에 전달하고,
        필요한 도구를 실행한 뒤 최종 답변을 반환한다.

        Tool Calling 흐름:
            1. 시스템 프롬프트와 사용자 질문을 messages에 저장한다.
            2. messages와 사용 가능한 도구 목록을 Ollama에 전달한다.
            3. LLM이 도구 호출을 요청하면 실제 Python 함수를 실행한다.
            4. 함수 실행 결과를 role="tool" 메시지로 추가한다.
            5. 함수 결과가 포함된 messages를 Ollama에 다시 전달한다.
            6. 더 이상 도구 요청이 없으면 자연어 최종 답변을 반환한다.

        :param user_question: 사용자가 입력한 자연어 질문
        :return: LLM이 생성한 최종 자연어 답변
        """
        agent_start_time = time.perf_counter()

        # Ollama에 전달할 전체 대화 기록
        messages = [
            # LLM의 역할과 도구 사용 규칙을 설명하는 시스템 프롬프트
            {
                "role": "system",
                "content": self.prompts.TOOL_CALLING_PROMPT,
            },

            # 사용자가 실제로 입력한 질문
            {
                "role": "user",
                "content": user_question,
            },
        ]

        self.logger.info(f"[사용자 질문]: {user_question}")

        try:
            # 한 질문에서 LLM이 도구를 무한 반복 호출하는 상황을 방지하기 위해 최대 5번까지만 LLM을 호출
            for loop_count in range(1, 6):
                self.logger.info(f"[LLM 호출 #{loop_count}]")

                llm_start_time = time.perf_counter()

                # Ollama LLM 호출
                response = chat(
                    model=self.MODEL_NAME,
                    messages=messages,  # 현재까지 누적된 시스템, 사용자, assistant, tool 메시지 전달
                    tools=[self.search_news, self.search_stock],  # LLM이 사용할 수 있는 Python 함수 목록
                )

                # 현재 LLM 호출에 걸린 시간 계산
                llm_elapsed_time = (
                        time.perf_counter() - llm_start_time
                )

                self.logger.info(f"[LLM 호출 #{loop_count} 완료] - 소요 시간: {llm_elapsed_time}")
                self.logger.debug(f"response: {response}")

                # Ollama 응답 중 assistant 메시지만 추출 (assistantd에  role, content, tool_calls와 같은 주요 정보가 있음)
                assistant_message = response.message

                # LLM이 생성한 assistant 메시지를 대화 기록에 추가
                messages.append(assistant_message)
                self.logger.debug(f"messages: {messages}")

                # LLM이 요청한 도구 호출 목록
                tool_calls = assistant_message.tool_calls or []

                # LLM이 자연어 답변을 생성했다면 내용 로그 출력
                if assistant_message.content:
                    self.logger.info(f"LLM 응답 내용: {assistant_message.content}")
                else:
                    self.logger.info("답변 내용 없음 — 도구 호출 요청")

                self.logger.info(f"\n[요청한 도구] {tool_calls}")

                # 도구 호출 요청이 없으면 최종 답변
                if not tool_calls:
                    self.logger.info(f"[LLM 최종 답변 생성 완료] - {assistant_message.content}")
                    return assistant_message.content

                # LLM이 호출한 도구를 순서대로 실행
                for tool_call in tool_calls:
                    # LLM이 선택한 함수 이름 (ex."search_stock")
                    function_name = tool_call.function.name

                    # LLM이 생성한 함수 호출 인자 ex.{"ticker_name": "삼성전자", "period_days": 30}
                    arguments = tool_call.function.arguments

                    self.logger.info(f"[LLM이 선택한 도구 - 함수명: {function_name}, 인자: {arguments}]")

                    # 함수 이름을 이용해 실제 Python 함수 객체를 조회
                    function = self.AVAILABLE_FUNCTIONS.get(function_name)

                    # 등록되지 않은 함수 이름을 LLM이 요청한 경우
                    if function is None:
                        self.logger.error(f"[지원하지 않는 도구 호출] - {function_name}")
                        tool_result = {
                            "success": False,
                            "message": f"지원하지 않는 함수입니다. : {function_name}",
                        }
                    else:
                        try:
                            # arguments 딕셔너리를 키워드 인자로 풀어서 실제 Python 함수 실행
                            tool_result = function(**arguments)
                        except Exception as error:
                            # 함수 실행 중 오류가 발생한 경우
                            self.logger.error(f"[도구 실행 오류] - {function_name}")
                            tool_result = {
                                "success": False,
                                "message": str(error),
                            }
                    self.logger.info(f"[함수 실행 결과] : {json.dumps(tool_result, ensure_ascii=False, indent=2)}")

                    # 실행 결과를 다시 LLM에게 전달 (함수 실행 결과를 Tool 메시지로 추가)
                    messages.append(
                        {
                            "role": "tool",  # 이 메시지가 Python 함수 실행 결과임을 의미
                            "tool_name": function_name,  # 어떤 함수의 실행 결과인지 표시

                            # 함수 실행 결과를 json.dumps()를 사용하여 문자열로 전달
                            "content": json.dumps(
                                tool_result,
                                ensure_ascii=False,
                            ),
                        }
                    )
                    self.logger.info(f"{function_name} 실행 결과를 LLM에게 전달했습니다.")

                    # 첫번째 loop가 끝나면 for문의 처음으로 돌아간다.
                    # 다음 LLM 호출에서는 messages 안에 assistant의 도구 호출 요청과 Python 함수 실행 결과가 모두 포함되어 있다.
                    # LLM은 해당 결과를 참고하여 최종 자연어 답변을 생성하거나 추가 도구 호출을 요청한다.

            # 최대 5번까지 LLM을 호출했는데도 계속 도구 호출을 요청한 경우 반환
            return "도구 호출 횟수 제한을 초과했습니다."

        finally:
            # run_agent 함수가 정상 반환되거나, 중간에 예외가 발생하더라도 전체 실행 시간을 기록

            agent_elapsed_time = (
                    time.perf_counter() - agent_start_time
            )
            self.logger.info(f"[Agent 전체 실행 완료] 총 소요 시간: {agent_elapsed_time}")

if __name__ == "__main__":
    tool_calling = LLMToolCalling()

    question = input("질문을 입력하세요: ")

    answer = tool_calling.run_agent(question)

    print(f"\n최종 답변:\n{answer}")