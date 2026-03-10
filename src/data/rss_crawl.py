import os
import re
import time

from pathlib import Path
from urllib.parse import quote
import mimetypes
import requests
from bs4 import BeautifulSoup

from src.common.common_const import CommonConstant


class RSSCrawler:
    def __init__(self):
        self.const = CommonConstant()
        self.rss_api_boan = self.const.boannews_api
        # self.report_type = self.const.REPORT_TYPE
        # self.start_year = self.const.START_YEAR
        # self.sleep = self.const.SLEEP_BETWEEN_REQ

    def fetch_report_page(self, session: requests.Session):
        """

        """
        # ref = f"{self.rss_api_boan}/media/t_list.asp?Page=2&kind="
        ref = f"{self.rss_api_boan}/media/t_list.asp?mkind=0"
        i=3
        ref = f"https://www.boannews.com/media/t_list.asp?Page={i}&kind="
        resp = session.get(ref)
        if resp.status_code == 200:
            html = resp.text
            soup = BeautifulSoup(html, 'html.parser')
            items = soup.select("#news_area .news_list")

            # print(items[0])
            for item in items:
                news_writer_info = item.select_one("span.news_writer").get_text()
                news_link_info = item.select_one("a.news_content")["href"]
                news_img_info = [img['src'] for img in item.select("img")]
                news_title = item.select_one("span.news_txt").get_text()

                # 기사 본문 접속
                detail_url = f"{self.rss_api_boan}{news_link_info}"
                detail_resp = session.get(detail_url)
                detail_html = detail_resp.text
                detail_items = BeautifulSoup(detail_html, 'html.parser')

                article_div = detail_items.find("div", id="news_content")
                copyright_p = article_div.find("p", align="center")

                if copyright_p:
                    copyright_p.decompose()


                article_txt = article_div.get_text(separator="\n", strip=True)

                print(article_div.find("p", align="center"))
                print("=" * 80)
                print("[제목]")
                print(news_title)

                print("\n[기자 / 날짜]")
                print(news_writer_info)

                print("\n[기사 링크]")
                print(news_link_info)

                print("\n[이미지 URL]")
                for img in news_img_info:
                    print(img)

                print("\n[본문 미리보기 (앞 500자)]")
                print(article_txt)

                print("\n[본문 길이]")
                print(len(article_txt))
                print("=" * 80)

                break

        else:
            print(resp.status_code)


    def main(self):
        with requests.Session() as s:
            self.fetch_report_page(s)


if __name__ == "__main__":
    rss_crawler = RSSCrawler()
    rss_crawler.main()
