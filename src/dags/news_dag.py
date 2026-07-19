from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.email import EmailOperator
from datetime import datetime, timedelta
import sys
import pendulum

# Airflow 컨테이너 내부의 FIN_RAG 경로 추가
FIN_RAG_PATH = '/opt/airflow/FIN_RAG'
if FIN_RAG_PATH not in sys.path:
    sys.path.append(FIN_RAG_PATH)

# 실제 파일에서 '클래스'를 직접 임포트
# try:
#     from src.collector.rss_news_collector import RssNewsCollector
#     from src.data_access.news_chunker import NewsChunker
#     from src.data_access.news_embedding import EmbeddingNewsData
# except ImportError as e:
#     print(f"FIN_RAG - 뉴스 관련 클래스를 불러오는 중 오류 발생: {e}")
#     RssNewsCollector, NewsChunker, EmbeddingNewsData = None, None, None

from src.collector.rss_news_collector import RssNewsCollector
from src.data_access.news_chunker import NewsChunker
from src.data_access.news_embedding import EmbeddingNewsData

def rss_news_collector():
    if RssNewsCollector is None:
        raise ImportError("RssNewsCollector 클래스를 임포트하지 못했습니다.")

    # 클래스 인스턴스 생성
    rss_collector = RssNewsCollector()

    # 클래스 내부의 주요 실행 메서드 호출
    rss_collector.main()

def news_chunker():
    if NewsChunker is None:
        raise ImportError("NewsChunker 클래스를 임포트하지 못했습니다.")

    # 클래스 인스턴스 생성
    chunker = NewsChunker()

    # 클래스 내부의 주요 실행 메서드 호출
    chunker.run(
        chunk_size=500,
        chunk_overlap=100,
    )


def news_embedding():
    if EmbeddingNewsData is None:
        raise ImportError("EmbeddingNewsData 클래스를 임포트하지 못했습니다.")

    # 클래스 인스턴스 생성
    embedding = EmbeddingNewsData()

    # 클래스 내부의 주요 실행 메서드 호출
    embedding.run(500)


# 기본 설정
default_args = {
    'owner': 'aidev',
    'depends_on_past': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

KST = pendulum.timezone("Asia/Seoul")

with DAG(
    dag_id="news_data_collector_pipeline",
    default_args=default_args,
    description="뉴스 수집, 청킹, 임베딩을 수행하는 파이프라인",
    schedule="0 18 * * *",
    start_date=pendulum.datetime(2026, 1, 1, tz=KST),
    catchup=False,
    tags=["production", "finance", "rag"],
) as dag:

    # [Task 1] 뉴스 데이터 수집하기
    task_collect_rss = PythonOperator(
    task_id='collect_rss_news_data',
    python_callable=rss_news_collector,  # 위에서 정의한 실행 함수 매핑
    )

    # [Task 2] 수집된 뉴스 데이터 청킹
    task_chunking_news_data = PythonOperator(
    task_id='chunking_news_data',
    python_callable=news_chunker,  # 위에서 정의한 실행 함수 매핑
    )

    # [Task 3] 청킹된 뉴스 데이터 임베딩
    task_embedding_news_data = PythonOperator(
        task_id='embedding_news_data',
        python_callable=news_embedding,  # 위에서 정의한 실행 함수 매핑
    )

    # [Task 4] 전체 파이프라인 성공 이메일 발송
    email_task = EmailOperator(
        task_id='send_notification',
        to=['2radg_y@naver.com', 'kimhaneul0917@naver.com', 'aud824@naver.com'],
        subject='[FIN_RAG] {{ ds }} 뉴스 데이터 자동 수집 완료',
        html_content="""
            <h3>FIN_RAG 뉴스 데이터 파이프라인 완료</h3>

            <p>
                <b>처리 날짜:</b>
                {{ data_interval_end.in_timezone('Asia/Seoul').strftime('%Y-%m-%d') }}
            </p>

            <p>
                <b>실행 기준 시각(KST):</b>
                {{ data_interval_end.in_timezone('Asia/Seoul').strftime('%Y-%m-%d %H:%M:%S') }}
            </p>

            <br>

            <p>
                뉴스 데이터 수집, 청킹 및 임베딩 작업이 정상적으로 완료되었습니다.
            </p>
                """
    )

    # 뉴스 수집 → 청킹 → 임베딩 → 완료 이메일
    (
        task_collect_rss
        >> task_chunking_news_data
        >> task_embedding_news_data
        >> email_task
    )