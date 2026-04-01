from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# from src.common.setup_log import SetupLogger
from src.config.env_config import PostgresConstants


class PostgresDB:
    """
    PostgreSQL DB에 연결하는 클래스
    """

    _engine = None

    def __init__(self):
        # self.logger = SetupLogger.get_logger()

        self.POSTGRES_URL = (
            f"postgresql+psycopg2://"
            f"{PostgresConstants.DB_USER}:{PostgresConstants.DB_PASSWORD}"
            f"@{PostgresConstants.DB_HOST}:{PostgresConstants.DB_PORT}"
        )

        if PostgresDB._engine is None:
            PostgresDB._engine = self.create_engine_for_db()

        self.session_maker = sessionmaker(
            bind=PostgresDB._engine,
            autocommit=False,
            autoflush=False,
            expire_on_commit=False
        )

    def create_engine_for_db(self):
        """

        :return:
        """
        postgres_db_url = f"{self.POSTGRES_URL}/{PostgresConstants.DB_NAME}"
        return create_engine(postgres_db_url, pool_pre_ping=True)

    @contextmanager
    def get_postgres_db(self):
        """
        PostgreSQL DB 세션 반환
        :return:
        """
        session = self.session_maker()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()