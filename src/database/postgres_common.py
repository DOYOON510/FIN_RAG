from sqlalchemy import text

from src.database.connect_postgres import PostgresDB

def test_connection():
    db = PostgresDB()

    with db.get_postgres_db() as session:
        result = session.execute(text("SELECT 1"))
        print(result.fetchone())

if __name__ == "__main__":
    test_connection()