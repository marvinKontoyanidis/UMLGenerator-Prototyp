import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base, GenerationRequest
from services.llm_client import LLMClient
import logging


def create_app(*, session_factory=None, llm_client=None, database_url=None):
    app = Flask(__name__)
    CORS(app)
    logging.basicConfig(level=logging.INFO)

    if session_factory is None:
        resolved_db_url = database_url or os.getenv(
            "DATABASE_URL",
            "postgresql+psycopg2://uml_user:uml_pass@db:5432/uml_tasks",
        )
        engine = create_engine(resolved_db_url)
        Base.metadata.create_all(engine)
        session_factory = sessionmaker(bind=engine)
    app.session_factory = session_factory

    llm_client = llm_client or LLMClient()

    @app.route("/api/generate", methods=["POST"])
    def generate_task():
        payload = request.get_json() or {}
        parameters = payload.get("parameters")

        if not isinstance(parameters, dict) or not parameters:
            return jsonify({"error": "parameters must be a non-empty object"}), 400


        session = session_factory()
        try:
            model = parameters["param_model"]
            ex_type = parameters["param_ex_type"]
            dif_level = parameters["param_dif_level"]
            study_goal = parameters["param_study_goal"]
            length = parameters["param_length"]

            llm_response, prompt = llm_client.generate(
                model=model,
                ex_type=ex_type,
                dif_level=dif_level,
                study_goal=study_goal,
                length=length,
            )

            app.logger.info("Generated prompt for LLM: %s", prompt)
            app.logger.info("LLM response: %s", llm_response)

            generation_request = GenerationRequest(
                parameters=parameters,
                param_model=model,
                param_ex_type=ex_type,
                param_dif_level=dif_level,
                param_study_goal=study_goal,
                param_length=length,
                prompt_template=prompt,
                generated_response=llm_response,
            )
            session.add(generation_request)
            session.commit()  # assign primary key before hitting the LLM


            return (
                jsonify(
                    {
                        "id": generation_request.id,
                        "prompt": prompt,
                        "response": llm_response,
                        "parameters": generation_request.parameters,
                    }
                ),
                200,
            )
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    @app.route("/api/health", methods=["GET"])
    def health_check():
        return "OK", 200

    return app


if __name__ == "__main__":
    application = create_app()
    application.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
