from src.database.postgres_common import PostgresInsert

class CollectNewsData:
    """

    """
    def __init__(self):
        # self.logger = SetupLogger.get_logger()

        self.postgre_insert = PostgresInsert()

    def collect_news_data(self):
        data_list =  [
        {
            "collect_id": "C26040701",
            "source_type": "NAVER",
            "news_title": "금리 인상 전망에 따른 국내 증시 변동성 확대",
            "publisher_name": "H",
            "category": "경제",
            "published_date": "2026-04-07",
            "contents": "한국은행의 금리 인상 가능성이 제기되면서 국내 증시에 변동성이 커지고 있다.",
            "url": "https://news.example.com/article1",
        }]

        self.postgre_insert.insert_data_to_postgres("t_news_data", data_list)