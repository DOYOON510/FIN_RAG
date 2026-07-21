import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from src.llm.llm_tool_calling import LLMToolCalling

# # 샘플 데이터
# sample_response = {
#   "user_question": "최근 삼성전자 주가 흐름 알려줘",
#   "stock_data": {
#     "ticker_name": "삼성전자",
#     "ticker_code": "005930",
#     "period_days": 30,
#     "price_data": [
#       {
#         "trade_date": "2026-07-09",
#         "open_price": 69200,
#         "high_price": 69900,
#         "low_price": 68900,
#         "close_price": 69700
#       },
#       {
#         "trade_date": "2026-07-10",
#         "open_price": 69800,
#         "high_price": 70500,
#         "low_price": 69500,
#         "close_price": 70300
#       },
#       {
#         "trade_date": "2026-07-13",
#         "open_price": 70400,
#         "high_price": 70800,
#         "low_price": 69900,
#         "close_price": 70100
#       },
#       {
#         "trade_date": "2026-07-14",
#         "open_price": 70200,
#         "high_price": 71000,
#         "low_price": 70000,
#         "close_price": 70800
#       },
#       {
#         "trade_date": "2026-07-15",
#         "open_price": 70900,
#         "high_price": 71500,
#         "low_price": 70500,
#         "close_price": 71200
#       },
#       {
#         "trade_date": "2026-07-16",
#         "open_price": 71300,
#         "high_price": 71800,
#         "low_price": 70800,
#         "close_price": 71000
#       },
#       {
#         "trade_date": "2026-07-17",
#         "open_price": 71100,
#         "high_price": 71400,
#         "low_price": 70600,
#         "close_price": 70700
#       }
#     ]
#   },
#   "news_data": [
#     {
#       "news_title": "삼성전자, 외국인 순매도 확대…반도체 업황 우려 지속",
#       "published_date": "2026-07-18",
#       "publisher_name": "매일경제",
#       "url": "https://www.mk.co.kr/news/economy/12095683"
#     },
#     {
#       "news_title": "AI 반도체 투자 확대에도 삼성전자 주가 혼조",
#       "published_date": "2026-07-17",
#       "publisher_name": "한국경제",
#       "url": "https://www.hankyung.com/economy/article/202607170001"
#     },
#     {
#       "news_title": "증권가 \"삼성전자 하반기 실적 개선 기대\"",
#       "published_date": "2026-07-16",
#       "publisher_name": "연합뉴스",
#       "url": "https://www.yna.co.kr/view/AKR20260716000100008"
#     }
#   ],
#   "assistant_message": "삼성전자 주가는 최근 30일 동안 전반적으로 박스권 흐름을 보였으며, 최근 종가는 70,700원입니다. 단기적으로는 외국인 순매도와 반도체 업황 둔화 우려로 변동성이 확대되었지만, 증권가에서는 하반기 실적 개선 가능성도 함께 제시하고 있습니다."
# }

# 주식 차트 생성 함수

tool_calling = LLMToolCalling()
# all_result = tool_calling.run_agent(question)

def render_stock_chart(stock_data: dict):
  price_data = stock_data["price_data"]

  stock_df = pd.DataFrame(price_data)
  stock_df["trade_date"] = pd.to_datetime(stock_df["trade_date"])
  stock_df = stock_df.set_index("trade_date")

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
      )
    ]
  )

  fig.update_layout(
    title=f"{stock_data['ticker_name']} ({stock_data['ticker_code']})",
    height=450,
    template="plotly_white",
    xaxis_rangeslider_visible=False,
    margin=dict(l=20, r=20, t=50, b=20),
  )

  st.plotly_chart(fig, use_container_width=True)

def render_stock_table(stock_data: dict):
  stock_df = pd.DataFrame(stock_data["price_data"])

  stock_df = stock_df.rename(
    columns={
      "trade_date": "날짜",
      "open_price": "시가",
      "high_price": "고가",
      "low_price": "저가",
      "close_price": "종가",
    }
  )

  # st.subheader("주가 데이터")
  st.dataframe(
    stock_df,
    use_container_width=True,
    hide_index=True,
  )

# 뉴스
def render_news(news_data: list):
  st.subheader("📰 관련 뉴스")

  for news in news_data:
    with st.container(border=True):
      st.markdown(f"#### {news['news_title']}")
      st.caption(
        f"{news['publisher_name']} | {news['published_date']}"
      )
      st.link_button(
        "기사 보기",
        news["url"],
        use_container_width=True
      )


st.set_page_config(
    page_title="FIN RAG",
    page_icon="📈",
    layout="wide",
)

st.markdown(
    """
    <style>
    .stApp {
        background: #f7f9fc;
    }

    .block-container {
        max-width: 1280px;
        padding-top: 1.5rem;
        padding-bottom: 6rem;
    }

    h1, h2, h3, h4, h5 {
        color: #101828;
    }

    div[data-testid="stVerticalBlockBorderWrapper"] {
        background: #ffffff;
        border: 1px solid #d9e2f1;
        border-radius: 12px;
        box-shadow: 0 2px 8px rgba(16, 24, 40, 0.03);
    }

    div[data-testid="stChatInput"] {
        background: #ffffff;
        border: 1px solid #9db9ff;
        border-radius: 12px;
        box-shadow: 0 2px 10px rgba(37, 99, 235, 0.08);
    }

    div[data-testid="stDataFrame"] {
        border: 1px solid #e5eaf2;
        border-radius: 8px;
        overflow: hidden;
    }

    .question-label,
    .answer-label {
        color: #1769ff;
        font-size: 14px;
        font-weight: 700;
        margin-bottom: 8px;
    }

    .question-text {
        font-size: 17px;
        font-weight: 600;
        color: #111827;
    }

    .answer-text {
        font-size: 15px;
        line-height: 1.8;
        color: #1f2937;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("금융 AI Assistant")
st.caption("금융 뉴스와 주가 데이터를 궁금한 금융 정보를 답변해 드립니다.")

question = st.chat_input("궁금한 금융 정보를 질문해 주세요.")

if question:
    llm_response = tool_calling.run_agent(question)
    # 질문 박스
    with st.container(border=True):
      st.markdown(
        f"""
          <div class="question-label">질문</div>
          <div class="question-text">{question}</div>
          """,
        unsafe_allow_html=True,
      )

    # 답변 박스
    with st.container(border=True):
      st.markdown(
        f"""
          <div class="answer-label">AI 답변</div>
          <div class="answer-text">
              {llm_response["assistant_message"]}
          </div>
          """,
        unsafe_allow_html=True,
      )

    stock_data = llm_response.get("stock_data")
    news_data = llm_response.get("news_data", [])

    if stock_data and news_data:
      left_col, right_col = st.columns([1.3, 1])

      with left_col:
        with st.container(border=True):
          render_stock_chart(stock_data)
          render_stock_table(stock_data)

      with right_col:
        with st.container(border=True):
          render_news(news_data)

    elif stock_data:
      with st.container(border=True):
        render_stock_chart(stock_data)
        render_stock_table(stock_data)

    elif news_data:
      with st.container(border=True):
        render_news(news_data)