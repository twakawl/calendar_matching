"""
Simple script to print all records from google_accounts table.
"""

from pathlib import Path
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

# Adjust path if needed — this matches your app recommendation
DB_PATH = Path(__file__).resolve().parent / "calendar.db"
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)


def main() -> None:
    from app import GoogleAccount  # import your ORM model

    print(f"Using database: {DB_PATH}")
    print("-" * 60)

    with SessionLocal() as session:
        records = session.execute(select(GoogleAccount)).scalars().all()

        if not records:
            print("No records found.")
            return

        for acc in records:
            print(
                {
                    "account_label": acc.account_label,
                    "google_sub": acc.google_sub,
                    "email": acc.email,
                    "selected_as": acc.selected_as,
                    "created_at": acc.created_at,
                }
            )


if __name__ == "__main__":
    main()
