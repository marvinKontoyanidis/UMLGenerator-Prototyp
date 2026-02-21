from sqlalchemy import Column, Integer, JSON, Text, DateTime, ForeignKey, Float
from sqlalchemy.orm import declarative_base
from datetime import datetime

Base = declarative_base()


class GenerationRequest(Base):
    __tablename__ = "generation_requests"

    id = Column(Integer, primary_key=True)

    parameters = Column(JSON, nullable=False)

    # Wichtige Filterfelder als eigene Spalten
    param_model = Column(Text, nullable=False)
    param_ex_type = Column(Text, nullable=False)
    param_dif_level = Column(Text, nullable=False)
    param_study_goal = Column(Text, nullable=False)
    param_length = Column(Text, nullable=False)

    prompt_template = Column(Text, nullable=False)
    generated_response = Column(Text, nullable=False)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )


class EvaluationResult(Base):
    __tablename__ = "evaluation_results"

    id = Column(Integer, primary_key=True)

    generation_request_id = Column(
        Integer,
        ForeignKey("generation_requests.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Detailed scalar scores for scientific analysis

    evaluation_model = Column(Text, nullable=False)
    justification = Column(Text, nullable=False)

    # T: Exercise adherence
    T1 = Column(Float, nullable=True)
    T2 = Column(Float, nullable=True)
    T = Column(Float, nullable=True)
    # D: Difficulty profile adherence
    D1 = Column(Float, nullable=True)
    D2 = Column(Float, nullable=True)
    D3 = Column(Float, nullable=True)
    D4 = Column(Float, nullable=True)
    D = Column(Float, nullable=True)
    # S: Study goal alignment
    S1 = Column(Float, nullable=True)
    S2 = Column(Float, nullable=True)
    S3 = Column(Float, nullable=True)
    S = Column(Float, nullable=True)
    # L: Length adherence
    L1 = Column(Float, nullable=True)
    L2 = Column(Float, nullable=True)
    L = Column(Float, nullable=True)
    # P: Pedagogical quality
    P1 = Column(Float, nullable=True)
    P2 = Column(Float, nullable=True)
    P3 = Column(Float, nullable=True)
    P4 = Column(Float, nullable=True)
    P = Column(Float, nullable=True)

    full_score = Column(Float, nullable=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
