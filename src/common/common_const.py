class CommonConstant:
    """크롤러 전역 설정(상수) 보관 클래스"""
    table_mapping_dict = {
        "t_data_collect_log": {
            "table_id": "collect_id",
            "need_collect_id": "Y",
            "need_table_id": "Y",
            "table_code": "C",
            "padding_n": 2
        },
        "t_news_data": {
            "table_id": "news_id",
            "need_collect_id": "Y",
            "need_table_id": "Y",
            "table_code": "N",
            "padding_n": 4,
            "prefix_col_list": ["source_type", "publisher_name"],
            "prefix_date": "published_date"
        },
        # "t_stock_price_data": {
        #     "table_id": "stock_id",
        #     "table_code": "S",
        #     "padding_n": 4,
        #     "prefix_col_list": None,
        #     "prefix_date": "trade_date"
        # },

        "t_stock_original_price_data": {
            "table_id": "stock_id",
            "need_collect_id": "Y",
            "need_table_id": "Y",
            "table_code": "S",
            "padding_n": 4,
            "prefix_date": "trade_date"
        },

        "t_vector_data": {
            "table_id": "chunking_id",
            "need_collect_id": "N",
            "need_table_id": "N",
        },

        # TODO: t_ticker_info 쓰는데가 있었나??
        "t_ticker_info": {
            "table_id": "ticker_sno", "table_code": "", "padding_n": 0,
        },
    }
    


class StockConstant:
    """
    # TODO: 주석 추가
    """
    token_url = "https://openapi.koreainvestment.com:9443/oauth2/tokenP"
    stock_url = "https://openapi.koreainvestment.com:9443/uapi/domestic-stock/v1/quotations/inquire-price"



class NewsCollectorConfig:
    # =========================
    # 뉴스 크롤링 (naver api)
    # =========================
    KEYWORDS_BY_CATEGORY = {
        "경제": [
            "금리", "기준금리", "인플레이션", "CPI", "GDP",
            "경기침체", "고용지표", "실업률", "국채금리", "통화정책",
            "환율", "원달러환율", "소비자물가", "생산자물가", "PPI",
            "연준", "FOMC", "양적완화", "긴축", "스태그플레이션", "유가", "원자재",
        ],

        "증권": [
            "코스피", "코스닥", "나스닥", "S&P500", "증시",
            "주가", "공매도", "IPO", "PER", "실적발표",
            "시가총액", "배당", "배당금", "EPS", "PBR",
            "테마주", "밸류업", "ETF", "선물", "옵션",
        ],

        "IT": [
            "AI", "반도체", "HBM", "파운드리", "클라우드",
            "데이터센터", "빅테크", "자율주행", "전기차", "2차전지",
            "생성형AI", "LLM", "챗GPT", "GPU", "엔비디아",
            "삼성전자", "SK하이닉스", "메타버스", "로봇", "사이버보안",
            "오픈AI", "애플", "테슬라", "모빌리티", "플랫폼",
        ],

        "부동산": [
            "부동산", "아파트", "주택시장", "전세", "월세",
            "정책", "분양", "청약", "재건축", "LTV",
            "재개발", "공시지가", "종부세", "취득세", "임대차",
            "미분양", "부동산PF", "금리인상", "전세사기", "주택공급",
        ],

        "정치": [
            "정부정책", "규제", "법안", "국회", "대통령", "정부",
            "선거", "정책발표", "세금", "예산안", "경제정책",
            "추경", "감세", "증세", "행정수도", "대외정책",
            "외교", "한미관계", "정당", "총선", "대선",
        ],

        "국제": [
            "경제", "미국", "환율", "원달러", "달러인덱스",
            "유가", "WTI", "무역", "관세", "공급망",
            "연준", "FOMC", "중국경제", "EU", "중동",
            "우크라이나", "금리인상", "금리인하", "인플레이션", "글로벌증시",
        ],

        "사회": [
            "고용시장", "물가상승", "가계부채", "출산율", "인구감소", "고용", "물가",
            "청년실업", "노동시장", "최저임금", "임금상승", "복지정책",
            "실업률", "비정규직", "청년정책", "주거난", "고령화",
            "사교육", "의료개혁", "건강보험", "산업재해", "복지예산",
        ],

        "주요 기업": [
            "삼성전자", "SK하이닉스", "엔비디아", "애플", "마이크로소프트",
            "테슬라", "아마존", "구글", "TSMC", "현대차",
            "넷플릭스", "오픈AI", "메타", "카카오", "네이버",
            "LG에너지솔루션", "포스코", "인텔", "AMD", "퀄컴",
        ]
    }

    MEDIA_DOMAINS = {
        "매일경제": "mk.co.kr",
        "한국경제": "hankyung.com",
        "국민일보": "kmib.co.kr"
    }

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        )
    }

    PUBLISHER_CODE_MAP = {
        "매일경제": "M",
        "한국경제": "H",
        "국민일보": "K",
    }

    ARTICLE_SELECTORS = {
        "매일경제": [
            "div.news_cnt_detail_wrap",
            "div.art_txt",
            "div.news_detail_wrap",
            "section.news_cnt_detail_wrap",
        ],
        "한국경제": [
            "div.article-body",
            "div#articletxt",
            "div.articleBody",
            "div.view-content",
        ],
        "국민일보": [
            "div#articleBody",
            "div.article_body",
            "div#article_body",
            "div.article-body",
        ]
    }

    RSS_FEEDS = {
        "매일경제": {
            "경제": "https://www.mk.co.kr/rss/30100041/",
            "정치": "https://www.mk.co.kr/rss/30200030/",
            "사회": "https://www.mk.co.kr/rss/50400012/",
            "국제": "https://www.mk.co.kr/rss/30300018/",
            "증권": "https://www.mk.co.kr/rss/50200011/",
            "부동산": "https://www.mk.co.kr/rss/50300009/",
        },
        "한국경제": {
            "증권": "https://www.hankyung.com/feed/finance",
            "경제": "https://www.hankyung.com/feed/economy",
            "부동산": "https://www.hankyung.com/feed/realestate",
            "IT": "https://www.hankyung.com/feed/it",
            "정치": "https://www.hankyung.com/feed/politics",
            "국제": "https://www.hankyung.com/feed/international",
            "사회": "https://www.hankyung.com/feed/society",
        },
        "국민일보": {
            "경제": "https://www.kmib.co.kr/rss/data/kmibEcoRss.xml",
            "정치": "https://www.kmib.co.kr/rss/data/kmibPolRss.xml",
            "국제": "https://www.kmib.co.kr/rss/data/kmibIntRss.xml",
            "사회": "https://www.kmib.co.kr/rss/data/kmibSocRss.xml",
        }
    }


class EbeddingTestQuery:
    test_query_dict = {"1. 삼성전자의 최근 AI 투자 관련 소식 알려줘",
                       "2. SK하이닉스의 HBM 사업 관련 기사 찾아줘",
                       "3. 네이버 실적 전망에 대한 뉴스 알려줘",
                       "4. 카카오의 신규 사업 관련 기사 찾아줘",
                       "5. LG에너지솔루션 배터리 수주 관련 기사 알려줘",
                       "6. 금리 인하 가능성에 대한 최근 기사 알려줘",
                       "7. 환율 상승이 국내 증시에 미치는 영향 관련 뉴스 찾아줘",
                       "8. 반도체 업황 회복 전망 기사 알려줘",
                       "9. 미국 FOMC 결과와 관련된 기사 찾아줘",
                       "10. 한국 경제성장률 전망 기사 알려줘",
                       "11. 반도체 시장에서 가장 유리한 기업은 어디야?",
                       "12. 최근 배터리 업계 분위기는 어때",
                       "13. 요즘 국내 증시에 영향을 주는 주요 이슈는 뭐야",
                       "14. AI 관련 수혜주로 언급되는 기업은 어디야?",
                       "15. 반도체 기업들의 투자 계획은 어떤것같아?"
                       }
    test_model_name_list = ["BAAI/bge-m3", "nlpai-lab/KURE-v1", "Qwen/Qwen3-Embedding-0.6B"]