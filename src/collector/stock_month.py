import pandas as pd


class StockMonth:
    """
    =====================================
    종목 정보 전처리 클래스
    =====================================

    처리 목적:
    1. 원본 CSV 로드
    2. 우선주 / 전환주 / 스팩 제거
    3. ticker_name / ticker_code 컬럼 생성
    4. 중복 제거
    5. DB 적재용 ticker_info 생성
    """

    def __init__(self, file_path):

        # 원본 CSV 경로
        self.file_path = file_path

    def run(self):

        df = pd.read_csv(
            self.file_path,
            encoding="cp949"
        )

        preferred_patterns = (
            r"(우$|우B$|우C$|\(전환\)$|스팩)"
        )

        df = df[
            ~df["종목명"].str.contains(
                preferred_patterns,
                regex=True,
                na=False
            )
        ]

        '''
        스팩(SPAC) 제거
    
        제거 대상 :   IBKS제25호스팩
                    KB제32호스팩
                    삼성스팩10호
                    하나35호스팩
                    미래에셋비전스팩10호
                    엔에이치스팩32호
        
        제거 이유:
        - 실제 사업 회사가 아니고, 합병 목적 특수회사
    
        '''

        df = df.rename(columns={
            "종목명": "ticker_name",
            "종목코드": "ticker_code"
        })

        df = df[
            ["ticker_name", "ticker_code"]
        ]

        return df


# =========================
# 실행 코드
# =========================
if __name__ == "__main__":

    # 원본 CSV 경로
    ranker = StockMonth(
        "C:/Users/kimha/Desktop/SKY/RAG/data.csv"
    )

    # 종목 전처리 실행
    ticker_df = ranker.run()

    # 결과 CSV 저장
    ticker_df.to_csv(
        r"C:\Users\kimha\Desktop\SKY\RAG\ticker_info.csv",
        index=False,
        encoding="utf-8-sig"
    )

    # 결과 확인
    print(ticker_df.head())

    # 최종 종목 개수 확인
    print(len(ticker_df))