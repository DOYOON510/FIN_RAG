from airflow import DAG
from airflow.operators.python import PythonOperator, BranchPythonOperator
from airflow.operators.email import EmailOperator
from datetime import datetime, timedelta
import sys

from sqlalchemy import text

# Airflow 컨테이너 내부의 FIN_RAG 경로 추가
FIN_RAG_PATH = '/opt/airflow/FIN_RAG'
if FIN_RAG_PATH not in sys.path:
    sys.path.append(FIN_RAG_PATH)

# 실제 파일에서 '클래스'를 직접 임포트
try:
    from src.collector.today_stock_collector import TodayStockCollector
    from src.database.connect_postgres import PostgresDB
except ImportError as e:
    print(f"FIN_RAG - 클래스를 불러오는 중 오류 발생: {e}")
    TodayStockCollector = None
    PostgresDB = None


def run_stock_collector():
    if TodayStockCollector is None:
        raise ImportError("TodayStockCollector 클래스를 임포트하지 못했습니다.")

    # 클래스 인스턴스 생성
    stock_collector = TodayStockCollector()

    # 클래스 내부의 주요 실행 메서드 호출
    result = stock_collector.insert_today_stock_data()

    return result

def check_stock_result(ti):
    result = ti.xcom_pull(task_ids="collect_today_stock_data")

    if not result:
            return "calculate_stock_price_data"

    return "send_error_notification"

def run_calculate_stock_price_data():
    if PostgresDB is None:
        raise ImportError("PostgresDB 클래스를 임포트하지 못했습니다.")

    db = PostgresDB()

    sql_path = "/opt/airflow/FIN_RAG/src/data_access/calculate_stock_price_data.sql"

    with open(sql_path, "r", encoding="utf-8") as file:
        query = file.read()

    with db.get_postgres_db() as session:
        session.execute(text(query))
        session.commit()

    print("주가 계산 SQL 실행 완료")


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
        schedule="0 12 * * *",
        start_date=datetime(2026, 1, 1),
        catchup=False,
        tags=['production', 'finance', 'rag'],
) as dag:
    # [Task 1] 주식 데이터 수집하기
    task_collect_stock = PythonOperator(
        task_id='collect_today_stock_data',
        python_callable=run_stock_collector,
    )

    # [Task 2] 수집 결과 확인 및 분기
    check_result = BranchPythonOperator(
        task_id="check_stock_result",
        python_callable=check_stock_result,
    )

    # [Task 3] 주가 지표 계산하기
    task_calculate_stock_price = PythonOperator(
        task_id='calculate_stock_price_data',
        python_callable=run_calculate_stock_price_data,
    )

    # [Task 4] 성공 이메일 보내기
    success_email_task = EmailOperator(
        task_id="send_success_notification",
        to=["2radg_y@naver.com", "kimhaneul0917@naver.com", "aud824@naver.com"],
        subject="[FIN_RAG] {{ ds }} 주식 데이터 자동 수집 완료",
        html_content="""
            <h3>FIN_RAG: 주식 데이터 수집 파이프라인 완료</h3>
            <p><b>수집 날짜:</b> {{ ds }}</p>
            <p>오늘 자 주식 데이터 수집 및 지표 계산이 무사히 완료되었습니다.</p>
        """
    )

    # [Task 5] 실패 이메일 보내기
    error_email_task = EmailOperator(
        task_id="send_error_notification",
        to=["2radg_y@naver.com", "kimhaneul0917@naver.com", "aud824@naver.com"],
        subject="[FIN_RAG] {{ ds }} 주식 데이터 수집 실패",
        html_content="""
            <h3>FIN_RAG: 주식 데이터 수집 실패</h3>
            <p><b>수집 날짜:</b> {{ ds }}</p>
            <p>주식 데이터 수집에 실패했습니다.</p>
            <p>insert_today_stock_data()의 반환값을 확인해주세요.</p>
        """
    )

    # 파이프라인 흐름 정의
    task_collect_stock >> check_result

    # 수집 성공 시
    check_result >> task_calculate_stock_price >> success_email_task

    # 수집 실패 시
    check_result >> error_email_task
