
class CommonConstant:
    """전역 설정(상수) 보관 클래스"""
    table_mapping_dict = {
        "t_data_collect_log": {
            "table_id": "collect_id", "table_code": "C", "padding_n":2, "prefix_col_list":None, "prefix_date":None
        },
        "t_news_data": {
            "table_id": "news_id", "table_code": "N", "padding_n": 4,
            "prefix_col_list":["source_type", "publisher_name"], "prefix_date": "published_date"
        },
        "t_stock_price_data": {
            "table_id": "stock_id", "table_code": "S", "padding_n": 4, "prefix_col_list":None, "prefix_date": "trade_date"
        },
    }
