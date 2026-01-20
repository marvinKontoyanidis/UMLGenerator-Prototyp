from sqlalchemy import Column, Integer, JSON, Text, DateTime
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
    generated_task = Column(Text, nullable=False)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    def build_prompt(self) -> str:
        return self.prompt_template.format(**self.parameters)
