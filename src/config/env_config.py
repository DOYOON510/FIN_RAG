import os
from dotenv import load_dotenv

# 환경 설정 로드 개발 환경에서는 .env 파일 로드
if os.getenv("ENV") != "production":
    load_dotenv()


class PostgresConstants:
    DB_HOST = os.getenv("POSTGRES_HOST")
    DB_PORT = os.getenv("POSTGRES_PORT")
    DB_USER = os.getenv("POSTGRES_USER")
    DB_PASSWORD = os.getenv("POSTGRES_PASSWORD")
    DB_NAME = os.getenv("POSTGRES_DB")
