from sqlalchemy import Column, Integer, JSON, Text, DateTime, ForeignKey, Float
from sqlalchemy.orm import declarative_base
from datetime import datetime

Base = declarative_base()


class GenerationRequest(Base):
    __tablename__ = "generation_requests"

    id = Column(Integer, primary_key=True)

    # Full JSON payload of the request parameters as sent by the frontend
    parameters = Column(JSON, nullable=False)

    # Important filter fields as separate columns for querying/aggregation
    param_model = Column(Text, nullable=False)
    param_ex_type = Column(Text, nullable=False)
    param_dif_level = Column(Text, nullable=False)
    param_study_goal = Column(Text, nullable=False)
    param_length = Column(Text, nullable=False)

    # Prompt that was sent to the LLM and its raw textual response
    prompt_template = Column(Text, nullable=False)
    generated_response = Column(Text, nullable=False)

    # Basic timestamps for auditing
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )


class EvaluationResult(Base):
    """Numeric and textual scores for one LLM-based evaluation.

    Each row belongs to exactly one :class:`GenerationRequest` and stores
    both the detailed per-item scores (T1, D1, ...) and the dimension
    aggregates (T, D, S, L, P) as computed by the evaluation LLM.

    The ``justification`` column contains a JSON string that maps each
    rating item (e.g. "T1") to the natural language explanation provided
    by the LLM. Keeping this as text avoids tight coupling to any ORM
    representation and makes it easy to export for later analysis.
    """

    __tablename__ = "evaluation_results"

    id = Column(Integer, primary_key=True)

    generation_request_id = Column(
        Integer,
        ForeignKey("generation_requests.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Model identifier used for the evaluation (e.g. "gpt-5.1")
    evaluation_model = Column(Text, nullable=False)

    # JSON-encoded map of item-id -> textual justification
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

    # Sum of the five dimension averages (range 0..10)
    full_score = Column(Float, nullable=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
