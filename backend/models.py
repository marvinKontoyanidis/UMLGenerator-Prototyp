from sqlalchemy import Column, Integer, JSON, Text
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class GenerationRequest(Base):
    __tablename__ = "generation_requests"

    id = Column(Integer, primary_key=True)
    parameters = Column(JSON, nullable=False)
    prompt_template = Column(Text, nullable=False)
    generated_task = Column(Text, nullable=False)

    def build_prompt(self) -> str:
        return self.prompt_template.format(**self.parameters)

