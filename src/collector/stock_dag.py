from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.email import EmailOperator
from datetime import datetime, timedelta
import sys

# Airflow 컨테이너 내부의 FIN_RAG 경로 추가
FIN_RAG_PATH = '/opt/airflow/FIN_RAG'
if FIN_RAG_PATH not in sys.path:
    sys.path.append(FIN_RAG_PATH)

# 실제 파일에서 '클래스'를 직접 임포트
try:
    from src.collector.today_stock_collector import TodayStockCollector
except ImportError as e:
    print(f"FIN_RAG - TodayStockCollector 클래스를 불러오는 중 오류 발생: {e}")
    TodayStockCollector = None

def run_stock_collector():
    if TodayStockCollector is None:
        raise ImportError("TodayStockCollector 클래스를 임포트하지 못했습니다.")

    # 클래스 인스턴스 생성
    stock_collector = TodayStockCollector()
    # 클래스 내부의 주요 실행 메서드 호출
    stock_collector.insert_today_stock_data()


# 기본 설정
default_args = {
    'owner': 'aidev',
    'depends_on_past': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

with DAG(
        dag_id='stock_data_collector_pipeline',
        default_args=default_args,
        description='주식 데이터 수집기를 구동하는 파이프라인',
        schedule = "0 15 * * *",
        start_date=datetime(2026, 1, 1),
        catchup=False,
        tags=['production', 'finance', 'rag'],
) as dag:
    # [Task 1] 주식 데이터 수집하기
    task_collect_stock = PythonOperator(
        task_id='collect_today_stock_data',
        python_callable=run_stock_collector,  # 위에서 정의한 실행 함수 매핑
    )

    # [Task 2] 이메일 보내기 (이메일 도구 사용)
    email_task = EmailOperator(
        task_id='send_notification',
        to=['2radg_y@naver.com', 'kimhaneul0917@naver.com', 'aud824@naver.com'],
        subject='[FIN_RAG] {{ ds }} 주식 데이터 자동 수집 완료',
        html_content="""
                <h3>FIN_RAG: 주식 데이터 수집 파이프라인 완료</h3>
                <p><b>수집 날짜:</b> {{ ds }}</p>
                <p><b>실행 시각(KST):</b> {{ data_interval_end.in_timezone('Asia/Seoul').strftime('%Y-%m-%d %H:%M:%S') }}</p>
                <br>
                <p>오늘 자 주식 데이터 수집이 무사히 완료되었습니다.</p>
                """
    )
    # 파이프라인 흐름 정의
    task_collect_stock >> email_task
