from pathlib import Path

from backend.database.session import SessionLocal
from backend.services.vector_store import ingest_policy_pdfs


def main():
    policies_root = Path(__file__).resolve().parents[2] / "storage" / "policies"
    with SessionLocal() as db:
        count = ingest_policy_pdfs(db, str(policies_root))
        print(f"Stored {count} policy chunks in pgvector.")


if __name__ == "__main__":
    main()
