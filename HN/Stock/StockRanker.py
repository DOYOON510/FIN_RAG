import pandas as pd


class StockRanker:
    """
    CSV 기반 주식 데이터를 점수화하여
    상위 종목을 선별하는 랭킹 모델 클래스

    전체 흐름:
    1. 데이터 로드
    2. 이상치/불필요 종목 필터링
    3. 파생 변수 생성
    4. 정규화
    5. 점수 계산
    6. Top N 추출
    """

    def __init__(self, file_path):
        """
        초기 데이터 경로 설정

        Input:
            file_path: 주식 원본 CSV 경로
        """
        self.file_path = file_path
        self.df = None

    # =========================
    # 1. 데이터 로드
    # =========================
    def load_data(self):
        """
        CSV 파일을 DataFrame으로 로드

        Output:
            전체 데이터프레임 (self.df)
        """
        self.df = pd.read_csv(self.file_path, encoding="cp949")
        return self.df

    # =========================
    # 2. 데이터 필터링
    # =========================
    def filter_data(self):
        """
        투자 비정상/저유동성 종목 제거

        필터 조건:
        - 거래대금 1억 이상
        - 거래량 5만 이상
        - 시가총액 10억 이상
        - 우선주 (우, 우B, 우C 등) 제거
        - 영문 종목코드 제거

        Output:
            필터링된 데이터프레임
        """
        df = self.df.copy()

        preferred_patterns = r"(?:우$|우B$|우C$|\(전환\)$)"

        df = df[
            (df["거래대금"] >= 100000000) &
            (df["거래량"] >= 50000) &
            (df["시가총액"] >= 1000000000) &
            (~df["종목명"].str.contains(preferred_patterns, regex=True, na=False)) &
            (~df["종목코드"].astype(str).str.contains(r"[A-Za-z]", na=False))
        ]

        self.df = df
        return self.df

    # =========================
    # 3. Feature 생성
    # =========================
    def create_features(self):
        """
        거래 효율성 지표 생성

        생성 변수:
        - 거래회전율 = 거래대금 / 시가총액

        Output:
            feature 추가된 데이터프레임
        """
        df = self.df.copy()

        df["거래회전율"] = (
            df["거래대금"] / df["시가총액"]
        ).replace([float("inf"), -float("inf")], 0)

        df["거래회전율"] = df["거래회전율"].fillna(0)

        self.df = df
        return self.df

    # =========================
    # 4. Min-Max 정규화
    # =========================
    def minmax_normalize(self, df, col):
        """
        특정 컬럼을 0 ~ 1 범위로 정규화

        Input:
            df: 데이터프레임
            col: 정규화 대상 컬럼

        Output:
            정규화된 Series
        """
        min_val = df[col].min()
        max_val = df[col].max()

        if max_val == min_val:
            return pd.Series([0] * len(df))

        return (df[col] - min_val) / (max_val - min_val)

    # =========================
    # 5. 정규화 적용
    # =========================
    def normalize(self):
        """
        주요 지표 정규화 수행

        대상:
        - 시가총액
        - 거래대금
        - 거래회전율

        Output:
            *_norm 컬럼 추가된 데이터프레임
        """
        df = self.df.copy()

        df["시가총액_norm"] = self.minmax_normalize(df, "시가총액")
        df["거래대금_norm"] = self.minmax_normalize(df, "거래대금")
        df["거래회전율_norm"] = self.minmax_normalize(df, "거래회전율")

        self.df = df
        return self.df

    # =========================
    # 6. Score 계산
    # =========================
    def score(self):
        """
        종합 점수 계산

        가중치:
        - 시가총액: 40%
        - 거래대금: 40%
        - 거래회전율: 20%

        Output:
            score 컬럼 추가된 데이터프레임
        """
        df = self.df.copy()

        df["score"] = (
            df["시가총액_norm"] * 0.4 +
            df["거래대금_norm"] * 0.4 +
            df["거래회전율_norm"] * 0.2
        )

        self.df = df
        return self.df

    # =========================
    # 7. Top N 추출
    # =========================
    def get_top(self, n=1000):
        """
        score 기준 상위 N개 종목 반환

        Input:
            n: 추출 개수

        Output:
            정렬된 Top N DataFrame
        """
        return self.df.sort_values("score", ascending=False).head(n)

    # =========================
    # 8. 전체 실행 파이프라인
    # =========================
    def run(self):
        """
        전체 분석 파이프라인 실행

        흐름:
        1. 데이터 로드
        2. 필터링
        3. feature 생성
        4. 정규화
        5. 점수 계산
        6. Top 1000 반환

        Output:
            Top 1000 종목 DataFrame
        """
        self.load_data()
        self.filter_data()
        self.create_features()
        self.normalize()
        self.score()

        return self.get_top(1000)


# =========================
# 실행 코드
# =========================
ranker = StockRanker("C:/Users/kimha/Desktop/SKY/RAG/data.csv")

top1000 = ranker.run()

# DB / 시스템 표준 컬럼명으로 변경
top1000 = top1000.rename(columns={
    "종목명": "ticker_name",
    "종목코드": "ticker_code"
})

# 결과 저장
top1000[["ticker_name", "ticker_code"]].to_csv(
    r"C:\Users\kimha\Desktop\SKY\RAG\top1000_result.csv",
    index=False,
    encoding="utf-8-sig"
)