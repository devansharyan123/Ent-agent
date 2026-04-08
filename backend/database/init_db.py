from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import os

# backend folder path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# backend/.env
ENV_PATH = os.path.join(BASE_DIR, ".env")
load_dotenv(ENV_PATH)

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL not found in backend/.env")

engine = create_engine(DATABASE_URL)

# root/db_scripts
ROOT_DIR = os.path.dirname(BASE_DIR)
SQL_DIR = os.path.join(ROOT_DIR, "db_scripts")


def run_sql_file(path):
    with open(path, "r", encoding="utf-8") as f:
        sql = f.read()

    with engine.connect() as conn:
        conn.execute(text(sql))
        conn.commit()


def init_db():
    run_sql_file(os.path.join(SQL_DIR, "app_schema.sql"))
    run_sql_file(os.path.join(SQL_DIR, "vector_schema.sql"))
    print("Schemas and tables created successfully")


if __name__ == "__main__":
    init_db()