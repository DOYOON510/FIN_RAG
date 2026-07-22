from pathlib import Path
import html
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.llm.llm_tool_calling import LLMToolCalling

# =========================================================
# Streamlit 기본 설정
# st로 화면을 그리기 전에 가장 먼저 실행되어야 함
# =========================================================
st.set_page_config(
    page_title="금융 AI Assistant",
    page_icon="📊",
    layout="wide",
)

# =========================================================
# 경로 및 객체 설정
# =========================================================
BASE_DIR = Path(__file__).resolve().parent
LOGO_PATH = BASE_DIR / "assets" / "logo.png"

tool_calling = LLMToolCalling()


# =========================================================
# 세션 상태
# =========================================================
if "question_input" not in st.session_state:
    st.session_state.question_input = ""

if "conversation" not in st.session_state:
    st.session_state.conversation = []

if "submitted_question" not in st.session_state:
    st.session_state.submitted_question = ""

# =========================================================
# CSS
# =========================================================
st.markdown(
    """
<style>
/* 전체 배경 */
.stApp {
    background:
        radial-gradient(
            circle at 10% 0%,
            rgba(49, 94, 251, 0.10),
            transparent 30%
        ),
        #f7f9fc;
}

/* 기본 콘텐츠 영역 */
.block-container {
    max-width: 1180px;
    padding-top: 2rem;
    padding-bottom: 4rem;
}

/* Streamlit 상단 헤더 */
header[data-testid="stHeader"] {
    background: transparent;
}

/* 카드 스타일 */
div[data-testid="stVerticalBlockBorderWrapper"] {
    border-color: #e1e6ef;
    border-radius: 22px;
    background: rgba(255, 255, 255, 0.92);
    box-shadow: 0 14px 38px rgba(32, 45, 80, 0.07);
}

/* 제목 */
.main-title {
    margin:0 0 8px 0;
    color: #202738;
    font-size: 42px;
    font-weight: 800;
    line-height: 1.2;
    letter-spacing: -2px;
}

.main-description {
    margin-top:2px;
    line-height:1.6;
    color: #7c8597;
    font-size: 16px;
    line-height: 1.7;
}

/* FIN-RAG 배지 */
.service-badge {
    display: inline-block;
    padding: 5px 11px;
    margin-bottom: 9px;

    border-radius: 999px;
    background: #edf2ff;

    color: #315efb;
    font-size: 12px;
    font-weight: 800;
    letter-spacing: 0.5px;
}

/* 섹션 설명 */
.section-description {
    margin-top: -5px;
    margin-bottom: 14px;

    color: #8a93a5;
    font-size: 14px;
}

/* 질문 입력창 */
.stTextInput div[data-baseweb="input"] {
    min-height: 54px;

    border: 1px solid #dfe5ef;
    border-radius: 14px;

    background: white;
    box-shadow: 0 4px 16px rgba(24, 39, 75, 0.05);
}

.stTextInput div[data-baseweb="input"]:focus-within {
    border-color: #4c72ff;
    box-shadow: 0 0 0 3px rgba(76, 114, 255, 0.12);
}

.stTextInput input {
    font-size: 16px;
}

/* 기본 버튼 */
.stButton > button {
    min-height: 46px;

    border: 1px solid #dfe5ef;
    border-radius: 13px;

    background: white;
    color: #4f596b;

    font-size: 14px;
    font-weight: 600;

    transition: 0.2s ease;
}

/* 버튼 hover */
.stButton > button:hover {
    border-color: #8ba4ff;
    color: #315efb;
    background: #f5f7ff;

    transform: translateY(-1px);
}

/* Primary 버튼 */
.stButton > button[kind="primary"] {
    min-height: 54px;

    border: none;
    background: linear-gradient(135deg, #315efb, #6685ff);
    color: white;

    font-size: 15px;
    font-weight: 700;

    box-shadow: 0 9px 22px rgba(49, 94, 251, 0.22);
}

.stButton > button[kind="primary"]:hover {
    border: none;
    color: white;
    background: linear-gradient(135deg, #294fe1, #5877ee);

    box-shadow: 0 12px 27px rgba(49, 94, 251, 0.30);
}

/* 사용자 질문 말풍선 */
.user-question {
    max-width: 75%;
    margin-left: auto;
    padding: 16px 20px;

    border-radius: 19px 19px 5px 19px;
    background: linear-gradient(135deg, #315efb, #6483ff);
    color: white;

    box-shadow: 0 9px 24px rgba(49, 94, 251, 0.20);
}

.user-question-label {
    margin-bottom: 6px;

    font-size: 12px;
    font-weight: 800;
    opacity: 0.75;
}

.user-question-text {
    font-size: 16px;
    font-weight: 600;
    line-height: 1.65;
    word-break: keep-all;
}

/* AI 답변 */
.answer-title {
    color: #222a3a;
    font-size: 16px;
    font-weight: 800;
}

.answer-text {
    margin-top: 10px;

    color: #3f4859;
    font-size: 16px;
    line-height: 1.85;
    word-break: keep-all;
}

/* 로고가 없을 때 대체 영역 */
.logo-fallback {
    width: 94px;
    height: 94px;

    display: flex;
    align-items: center;
    justify-content: center;

    border-radius: 22px;
    background: linear-gradient(135deg, #315efb, #6f8cff);
    color: white;

    font-size: 32px;
    font-weight: 800;

    box-shadow: 0 10px 25px rgba(49, 94, 251, 0.22);
}

/* 모바일 */
@media (max-width: 768px) {
    .block-container {
        padding: 1rem 0.9rem 3rem;
    }

    .main-title {
        font-size: 31px;
        letter-spacing: -1.3px;
    }

    .main-description {
        font-size: 14px;
    }

    .user-question {
        max-width: 92%;
    }
}
</style>
""",
    unsafe_allow_html=True,
)


# =========================================================
# 함수
# =========================================================
def select_recommended_question(question_text: str) -> None:
    """추천 질문을 입력창에 적용한다."""
    st.session_state.question_input = question_text

def submit_question() -> None:
    """입력된 질문을 제출용 변수에 저장하고 입력창을 비운다."""
    st.session_state.submitted_question = (
        st.session_state.question_input.strip()
    )

    st.session_state.question_input = ""

# 주가 차트 출력
def render_stock_chart(stock_data: dict):
    price_data = stock_data.get("price_data", [])

    if not price_data:
        st.info("표시할 주가 데이터가 없습니다.")
        return

    stock_df = pd.DataFrame(price_data)

    required_columns = {
        "trade_date",
        "open_price",
        "high_price",
        "low_price",
        "close_price",
    }

    if not required_columns.issubset(stock_df.columns):
        st.warning("주가 데이터 형식이 올바르지 않습니다.")
        return

    stock_df["trade_date"] = pd.to_datetime(stock_df["trade_date"], errors="coerce")

    stock_df = stock_df.dropna(subset=["trade_date"])
    stock_df = stock_df.sort_values("trade_date")
    stock_df = stock_df.set_index("trade_date")

    ticker_name = stock_data.get("ticker_name", "종목")
    ticker_code = stock_data.get("ticker_code", "")

    chart_title = ticker_name

    if ticker_code:
        chart_title += f" ({ticker_code})"

    fig = go.Figure(
        data=[
            go.Candlestick(
                x=stock_df.index,
                open=stock_df["open_price"],
                high=stock_df["high_price"],
                low=stock_df["low_price"],
                close=stock_df["close_price"],
                increasing_line_color="#ef4444",
                decreasing_line_color="#2563eb",
                increasing_fillcolor="#ef4444",
                decreasing_fillcolor="#2563eb",
                name=ticker_name,
            )
        ]
    )

    fig.update_layout(
        title={
            "text": chart_title,
            "x": 0.01,
            "xanchor": "left",
        },
        height=430,
        template="plotly_white",
        xaxis_rangeslider_visible=False,
        margin=dict(
            l=20,
            r=20,
            t=55,
            b=20,
        ),
        showlegend=False,
        hovermode="x unified",
    )

    fig.update_xaxes(
        showgrid=True,
        gridcolor="#eef1f6",
    )

    fig.update_yaxes(
        showgrid=True,
        gridcolor="#eef1f6",
        tickformat=",",
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
        config={
            "displayModeBar": False,
        },
    )


# 주가 테이블 출력
def render_stock_table(stock_data: dict):
    price_data = stock_data.get("price_data", [])

    if not price_data:
        return

    stock_df = pd.DataFrame(price_data)

    rename_columns = {
        "trade_date": "날짜",
        "open_price": "시가",
        "high_price": "고가",
        "low_price": "저가",
        "close_price": "종가",
        "volume": "거래량",
    }

    available_columns = {
        key: value
        for key, value in rename_columns.items()
        if key in stock_df.columns
    }

    stock_df = stock_df.rename(columns=available_columns)

    if "날짜" in stock_df.columns:
        stock_df["날짜"] = pd.to_datetime(
            stock_df["날짜"],
            errors="coerce",
        ).dt.strftime("%Y-%m-%d")

    number_columns = [
        "시가",
        "고가",
        "저가",
        "종가",
        "거래량",
    ]

    column_config = {}

    for column in number_columns:
        if column in stock_df.columns:
            column_config[column] = st.column_config.NumberColumn(
                column,
                format="%d",
            )

    st.dataframe(
        stock_df,
        use_container_width=True,
        hide_index=True,
        column_config=column_config,
    )

# 뉴스 출력
def render_news(news_data: list):
    st.markdown("### 📰 관련 뉴스")

    if not news_data:
        st.info("표시할 뉴스가 없습니다.")
        return

    for news in news_data:
        title = news.get("news_title", "제목 없음")
        publisher = news.get("publisher_name", "언론사 정보 없음")
        published_date = news.get("published_date", "날짜 정보 없음")
        url = news.get("url")

        with st.container(border=True):
            st.markdown(f"#### {title}")
            st.caption(f"{publisher} · {published_date}")

            if url:
                st.link_button(
                    "기사 보기",
                    url,
                    use_container_width=True,
                )

# =========================================================
# 상단 헤더
# =========================================================
with st.container(border=True):
    logo_col, title_col = st.columns(
        [1.4, 6],
        vertical_alignment="center",
    )

    with logo_col:
        if LOGO_PATH.exists():
            st.image(
                str(LOGO_PATH),
                width=200,  # 95 → 170
            )
        else:
            st.markdown(
                """
<div class="logo-fallback">F</div>
""",
                unsafe_allow_html=True,
            )

    with title_col:
        st.markdown(
            """
<div class="service-badge">FIN-RAG</div>
<div class="main-title">금융 AI Assistant</div>
<div class="main-description">
    금융 뉴스와 주가 데이터를 분석하여<br>
    궁금한 금융 정보를 쉽고 빠르게 설명해드립니다.
</div>
""",
            unsafe_allow_html=True,
        )


st.write("")


# =========================================================
# 질문 입력 영역
# =========================================================
st.subheader("무엇이 궁금하신가요?")

st.markdown(
    """
<div class="section-description">
    종목명, 조회 기간, 궁금한 내용을 함께 입력하면
    더 정확한 답변을 받을 수 있어요.
</div>
""",
    unsafe_allow_html=True,
)

input_col, submit_col = st.columns(
    [8, 1.4],
    vertical_alignment="bottom",
)

with input_col:
    st.text_input(
        "질문",
        key="question_input",
        label_visibility="collapsed",
        placeholder="예: 최근 삼성전자 주가 흐름과 관련 뉴스를 알려줘"
    )

with submit_col:
    submit_clicked = st.button(
        "질문하기",
        type="primary",
        use_container_width=True,
        on_click=submit_question,
    )


# =========================================================
# 추천 질문
# =========================================================
st.caption("추천 질문")

recommend_col1, recommend_col2, recommend_col3 = st.columns(3)

with recommend_col1:
    st.button(
        "📈 삼성전자 최근 주가",
        use_container_width=True,
        on_click=select_recommended_question,
        args=("최근 삼성전자 주가 흐름을 알려줘",),
    )

with recommend_col2:
    st.button(
        "📰 반도체 업계 주요 이슈",
        use_container_width=True,
        on_click=select_recommended_question,
        args=("최근 반도체 업계의 주요 이슈를 알려줘",),
    )

with recommend_col3:
    st.button(
        "🔥 최근 거래량이 많은 종목",
        use_container_width=True,
        on_click=select_recommended_question,
        args=("최근 거래량이 가장 많은 종목을 알려줘",),
    )


# =========================================================
# LLM 호출
# =========================================================
if submit_clicked:
    submitted_question = st.session_state.submitted_question

    try:
        with st.spinner("금융 데이터를 조회하고 답변을 생성하고 있습니다..."):
            llm_response = tool_calling.run_agent(
                submitted_question
            )

        if not isinstance(llm_response, dict):
            llm_response = {
                "assistant_message": str(llm_response),
                "stock_data": [],
                "news_data": [],
            }

        st.session_state.conversation.append(
            {
                "question": submitted_question,
                "response": llm_response,
            }
        )

        # 이미 처리한 질문이 다시 호출되지 않도록 초기화
        st.session_state.submitted_question = ""

        st.rerun()

    except Exception as error:
        # 오류가 나도 동일한 질문이 계속 재호출되지 않도록 초기화
        st.session_state.submitted_question = ""

        st.error("답변을 생성하는 중 오류가 발생했습니다.")

        with st.expander("오류 상세 정보"):
            st.exception(error)

# =========================================================
# 질문 및 답변 기록 출력
# =========================================================
if st.session_state.conversation:
    st.write("")
    st.divider()

    for conversation_index, conversation in enumerate(
        st.session_state.conversation
    ):
        current_question = conversation["question"]
        current_response = conversation["response"]

        assistant_message = current_response.get(
            "assistant_message",
            "답변을 생성하지 못했습니다.",
        )

        stock_data_list = current_response.get(
            "stock_data",
            [],
        ) or []

        news_data_list = current_response.get(
            "news_data",
            [],
        ) or []

        safe_question = html.escape(current_question)

        # 사용자 질문
        st.markdown(
            f"""
<div class="user-question-wrapper">
    <div class="user-question-card">
        <div class="user-question-label">내 질문</div>
        <div class="user-question-text">{safe_question}</div>
    </div>
</div>
""",
            unsafe_allow_html=True,
        )

        # AI 답변
        with st.container(border=True):
            icon_col, answer_col = st.columns(
                [0.5, 8],
                vertical_alignment="top",
            )

            with icon_col:
                st.markdown(
                    """
<div class="answer-icon">✦</div>
""",
                    unsafe_allow_html=True,
                )

            with answer_col:
                st.markdown(
                    """
<div class="answer-title">
    FIN-RAG 답변
    <span class="answer-badge">AI</span>
</div>
""",
                    unsafe_allow_html=True,
                )

                # LLM 답변은 Markdown으로 출력
                st.markdown(assistant_message)

        st.write("")

        # 주가와 뉴스가 모두 있는 경우
        if stock_data_list and news_data_list:
            left_col, right_col = st.columns(
                [1.35, 1],
                gap="large",
            )

            with left_col:
                for stock_data in stock_data_list:
                    with st.container(border=True):
                        ticker_name = stock_data.get(
                            "ticker_name",
                            "주가 데이터",
                        )

                        st.markdown(
                            f"""
<div class="stock-title">
    📈 {ticker_name} 주가 정보
</div>
<div class="stock-description">
    조회 기간의 일별 시가·고가·저가·종가 데이터입니다.
</div>
""",
                            unsafe_allow_html=True,
                        )

                        render_stock_chart(stock_data)
                        render_stock_table(stock_data)

            with right_col:
                render_news(news_data_list)

        # 주가만 있는 경우
        elif stock_data_list:
            for stock_data in stock_data_list:
                with st.container(border=True):
                    ticker_name = stock_data.get(
                        "ticker_name",
                        "주가 데이터",
                    )

                    st.markdown(
                        f"""
<div class="stock-title">
    📈 {ticker_name} 주가 정보
</div>
<div class="stock-description">
    조회 기간의 일별 시가·고가·저가·종가 데이터입니다.
</div>
""",
                        unsafe_allow_html=True,
                    )

                    render_stock_chart(stock_data)
                    render_stock_table(stock_data)

        # 뉴스만 있는 경우
        elif news_data_list:
            render_news(news_data_list)

        # 이전 질문과 구분
        if conversation_index < len(
            st.session_state.conversation
        ) - 1:
            st.write("")
            st.divider()
            st.write("")