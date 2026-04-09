
class CommonConstant:
    """크롤러 전역 설정(상수) 보관 클래스"""
    table_mapping_dict = {
        "t_data_collect_log": {
            "table_id": "collect_id", "table_code": "C", "padding_n":2, "prefix_col_list":None, "prefix_date":None
        },
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
