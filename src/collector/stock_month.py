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
    5. DB 적재용 t_ticker_info 테이블 생성
    """

    def __init__(self, file_path: str, output_path: str):
        """
        초기 설정

        param file_path  : 원본 CSV 파일 경로
        param output_path: 전처리 결과 CSV 저장 경로
        """

        # 원본 CSV 경로
        self.file_path = file_path

        # 결과 CSV 저장 경로
        self.output_path = output_path

    def run(self):
        """
        종목 전처리 실행 및 결과 CSV 저장

        처리 흐름:
        1. 원본 CSV 로드
        2. 우선주 / 전환주 / 스팩 종목 제거
        3. 컬럼명 한글 → 영문 rename (종목명 → ticker_name, 종목코드 → ticker_code)
        4. 필요한 컬럼만 선택 (ticker_name, ticker_code)
        5. 전처리 결과 CSV 저장
        6. 결과 DataFrame 반환

        Output:
            - ticker_df (DataFrame): 전처리 완료된 종목 목록
        """

        df = pd.read_csv(
            self.file_path,
            encoding="cp949"
        )

        # 제거 대상 패턴 (우선주 / 전환주 / 스팩)
        preferred_patterns = (
            r"(우$|우B$|우C$|\(전환\)$|스팩)"
        )

        '''
        스팩(SPAC) 제거

        제거 대상:  IBKS제25호스팩, KB제32호스팩, 삼성스팩10호
                   하나35호스팩, 미래에셋비전스팩10호, 엔에이치스팩32호
        제거 이유:
        - 실제 사업 회사가 아니고, 기업 인수 및 합병 목적 특수회사
        '''

        df = df[
            ~df["종목명"].str.contains(
                preferred_patterns,
                regex=True,
                na=False
            )
        ]

        df = df.rename(columns={
            "종목명": "ticker_name",
            "종목코드": "ticker_code"
        })

        df = df[
            ["ticker_name", "ticker_code"]
        ]

        # 전처리 결과 CSV 저장
        df.to_csv(
            self.output_path,
            index=False,
            encoding="utf-8-sig"
        )

        print(f"CSV 저장 완료: {self.output_path}")
        print(f"최종 종목 수: {len(df)}개")
        print(df.head())

        return df


# =========================
# 실행 코드
# =========================
if __name__ == "__main__":

    ranker = StockMonth(
        file_path=r"C:\Users\kimha\Desktop\SKY\RAG\data.csv",       # ✅ r 추가
        output_path=r"C:\Users\kimha\Desktop\SKY\RAG\ticker_info.csv"
    )

    ranker.run()