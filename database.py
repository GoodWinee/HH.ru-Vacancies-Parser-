import os

import psycopg2
from dotenv import load_dotenv

load_dotenv()


def get_db_connection():
    """Возвращает подключение к базе данных (облачной или локальной)."""
    # Если есть DATABASE_URL (из GitHub Secrets), используем его
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return psycopg2.connect(database_url)
    
    # Иначе используем локальные переменные из .env
    return psycopg2.connect(
        dbname=os.getenv("POSTGRES_DB", "parser"),
        user=os.getenv("POSTGRES_USER", "parser_user"),
        password=os.getenv("POSTGRES_PASSWORD", "parser_password"),
        host=os.getenv("DB_HOST", "db"),
        port=os.getenv("DB_PORT", "5432")
    )


def init_db():
    """Создаёт таблицу для хранения обработанных вакансий, если её нет."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS processed_vacancies (
            id SERIAL PRIMARY KEY,
            url VARCHAR(500) UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    cur.close()
    conn.close()
    print("✅ База данных инициализирована.")


def is_vacancy_processed(url: str) -> bool:
    """Проверяет, есть ли уже такая ссылка в базе."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM processed_vacancies WHERE url = %s", (url,))
    exists = cur.fetchone() is not None
    cur.close()
    conn.close()
    return exists


def save_vacancy(url: str):
    """Сохраняет ссылку на вакансию в базу данных."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO processed_vacancies (url) VALUES (%s) ON CONFLICT (url) DO NOTHING",
            (url,)
        )
        conn.commit()
    except psycopg2.Error as e:
        print(f"❌ Ошибка при сохранении вакансии в БД: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()
