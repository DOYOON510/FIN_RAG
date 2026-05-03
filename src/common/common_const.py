
class CommonConstant:
    """크롤러 전역 설정(상수) 보관 클래스"""
    table_mapping_dict = {
        # "t_data_collect_log": {
        #     "table_id": "collect_id", "table_code": "C", "padding_n":2, "prefix_col_list":None, "prefix_date":None
        # },
        "t_news_data": {
            "table_id": "news_id", "table_code": "N", "padding_n": 2,
            "prefix_col_list":["source_type", "publisher_name"], "prefix_date": "published_date"
        },
        "t_stock_price_data": {
            "table_id": "stock_id", "table_code": "S", "padding_n": 4, "prefix_col_list":None, "prefix_date": "trade_date"
        },
    }
    boannews_api = "https://www.boannews.com"
    # # OUT_DIR = r"\\limenas7f\P2025_01_KSPO\03.공단 공통업무 AI 학습용 데이터셋 및 챗봇 구축\data_access\ALIO"
    # OUT_DIR = r"C:\Users\user\Desktop\ejjee\2025\KSPO\251120"
    # REPORT_TYPE = "43006"  # 내부·외부감사결과 고정
    # START_YEAR = 2021  # 기준일 연도가 이 값 이상만 수집
    # SLEEP_BETWEEN_REQ = 0.4  # 요청 간 딜레이(초)

class NewsCollectorConfig:
    # =========================
    # 뉴스 크롤링 (naver api)
    # =========================
    KEYWORDS_BY_CATEGORY = {
        "경제": [
            "금리", "기준금리", "인플레이션", "CPI", "GDP",
            "경기침체", "고용지표", "실업률", "국채금리", "통화정책",
        ]
        # "증권": [
        #     "코스피", "코스닥", "나스닥", "S&P500", "증시",
        #     "주가", "공매도", "IPO", "PER", "실적발표",
        # ],
        # "IT": [
        #     "AI", "반도체", "HBM", "파운드리", "클라우드",
        #     "데이터센터", "빅테크", "자율주행", "전기차", "2차전지",
        # ],
        # "부동산": [
        #     "부동산", "아파트", "주택시장", "전세", "월세",
        #     "정책", "분양", "청약", "재건축", "LTV",
        # ],
        # "정치": [
        #     "정부정책", "규제", "법안", "국회", "대통령", "정부",
        #     "선거", "정책발표", "세금", "예산안", "경제정책",
        # ],
        # "국제": [
        #     "경제", "미국", "환율", "원달러", "달러인덱스",
        #     "유가", "WTI", "무역", "관세", "공급망",
        # ],
        # "사회": [
        #     "고용시장", "물가상승", "가계부채", "출산율", "인구감소", "고용", "물가",
        #     "청년실업", "노동시장", "최저임금", "임금상승", "복지정책",
        # ],
        # "주요 기업": [
        #     "삼성전자", "SK하이닉스", "엔비디아", "애플", "마이크로소프트",
        #     "테슬라", "아마존", "구글", "TSMC", "현대차",
        # ]
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