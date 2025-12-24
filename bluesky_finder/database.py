from datetime import datetime
from sqlalchemy import (
    create_engine,
    Column,
    String,
    Integer,
    Float,
    DateTime,
    JSON,
    ForeignKey,
    Boolean,
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship, Session
from .config import settings

Base = declarative_base()


class DbCandidate(Base):
    __tablename__ = "candidates"
    did = Column(String, primary_key=True)
    handle = Column(String, index=True)
    # Storing set as JSON list
    discovery_sources = Column(JSON, default=list)
    discovered_at = Column(DateTime, default=datetime.utcnow)

    profile = relationship(
        "DbProfile",
        back_populates="candidate",
        uselist=False,
        cascade="all, delete-orphan",
    )
    posts = relationship(
        "DbPost", back_populates="candidate", cascade="all, delete-orphan"
    )
    llm_eval = relationship(
        "DbLlmEval",
        back_populates="candidate",
        uselist=False,
        cascade="all, delete-orphan",
    )


class DbProfile(Base):
    __tablename__ = "profiles"

    handle = Column(String, index=True, nullable=True)

    did = Column(String, ForeignKey("candidates.did"), primary_key=True)
    display_name = Column(String, nullable=True)
    description = Column(String, nullable=True)
    avatar_url = Column(String, nullable=True)
    fetched_at = Column(DateTime, default=datetime.utcnow)

    candidate = relationship("DbCandidate", back_populates="profile")


class DbPost(Base):
    __tablename__ = "posts"
    uri = Column(String, primary_key=True)
    cid = Column(String)
    author_did = Column(String, ForeignKey("candidates.did"), index=True)
    created_at = Column(DateTime)
    text = Column(String)
    is_repost = Column(Boolean, default=False)

    candidate = relationship("DbCandidate", back_populates="posts")


class DbLlmEval(Base):
    __tablename__ = "llm_evals"
    did = Column(String, ForeignKey("candidates.did"), primary_key=True)
    model = Column(String)
    run_at = Column(DateTime, default=datetime.utcnow)
    score_location = Column(Float)
    score_tech = Column(Float)
    score_overall = Column(Float)
    label = Column(String)
    rationale = Column(String)
    evidence = Column(JSON)
    uncertainties = Column(JSON)

    candidate = relationship("DbCandidate", back_populates="llm_eval")


def get_db() -> Session:
    engine = create_engine(f"sqlite:///{settings.db_path}")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()
