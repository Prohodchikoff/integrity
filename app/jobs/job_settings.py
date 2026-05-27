import os
from sqlalchemy import Column, Integer, String, Text, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker


DATABASE_URL = os.getenv("JOB_DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError(
        "JOB_DATABASE_URL is required (e.g. mysql+pymysql://user:pass@host:3306/jobs)"
    )

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class JobStatusRow(Base):
    __tablename__ = "integrity_job_statuses"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(String(64), unique=True, index=True, nullable=False)
    kind = Column(String(16), nullable=False)
    status = Column(String(16), nullable=False, index=True)
    project_name = Column(String(128), nullable=False, index=True)
    env_name = Column(String(128), nullable=True, index=True)
    created_at = Column(String(64), nullable=False)
    started_at = Column(String(64), nullable=True)
    finished_at = Column(String(64), nullable=True)
    progress_done = Column(Integer, nullable=False, default=0)
    progress_total = Column(Integer, nullable=True)
    error_text = Column(Text, nullable=True)
    result_json = Column(Text, nullable=True)


class JobEventRow(Base):
    __tablename__ = "integrity_job_events"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(String(64), index=True, nullable=False)
    event_kind = Column(String(32), nullable=False)
    item_name = Column(String(255), nullable=True)
    status = Column(String(16), nullable=False)
    error_text = Column(Text, nullable=True)
    payload_json = Column(Text, nullable=True)
    created_at = Column(String(64), nullable=False)


def init_job_tables() -> None:
    Base.metadata.create_all(bind=engine)
