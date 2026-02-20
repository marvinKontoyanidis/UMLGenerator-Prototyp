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
    S1_score = Column(Float, nullable=True)
    S2_score = Column(Float, nullable=True)
    S3_score = Column(Float, nullable=True)
    S_total = Column(Float, nullable=True)

    T1_score = Column(Float, nullable=True)
    T2_score = Column(Float, nullable=True)
    T3_score = Column(Float, nullable=True)
    T_total = Column(Float, nullable=True)

    evaluation_model = Column(Text, nullable=False)
    evaluation_prompt = Column(Text, nullable=False)
    raw_response = Column(Text, nullable=False)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
