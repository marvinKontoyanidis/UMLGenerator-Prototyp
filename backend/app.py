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
        prompt_template = payload.get("prompt_template")

        if not isinstance(parameters, dict) or not parameters:
            return jsonify({"error": "parameters must be a non-empty object"}), 400
        if not isinstance(prompt_template, str) or not prompt_template.strip():
            return jsonify({"error": "prompt_template must be a non-empty string"}), 400

        session = session_factory()
        try:
            generation_request = GenerationRequest(
                parameters=parameters,
                param_model=parameters["param_model"],
                param_ex_type=parameters["param_ex_type"],
                param_dif_level=parameters["param_dif_level"],
                param_study_goal=parameters["param_study_goal"],
                param_length=parameters["param_length"],
                prompt_template=prompt_template,
                generated_task="",
            )
            session.add(generation_request)
            session.flush()  # assign primary key before hitting the LLM

            try:
                prompt = generation_request.build_prompt()
                app.logger.info("Generated prompt for LLM: %s", prompt)
            except KeyError as exc:
                session.rollback()
                return (
                    jsonify({"error": f"Missing parameter for prompt template: {exc}"}),
                    400,
                )

            llm_response = llm_client.generate(prompt, generation_request.param_model)
            app.logger.info("LLM response: %s", llm_response)
            generation_request.generated_task = llm_response
            session.commit()

            return (
                jsonify(
                    {
                        "id": generation_request.id,
                        "prompt": prompt,
                        "task": llm_response,
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
