import os
from sqlmodel import create_engine, Session

# Use DATABASE_URL from environment for Postgres connection
# Example: postgresql://user:password@host:port/database
database_url = os.environ.get("DATABASE_URL", "sqlite:///database.db") 

engine = create_engine(database_url, echo=True)

def get_session():
    with Session(engine) as session:
        yield session

