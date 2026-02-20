import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base, GenerationRequest, EvaluationResult
from services.llm_client import LLMClient
import logging


def _build_evaluation_prompt(evaluation_instruction: str, generation_prompt: str, llm_response: str) -> str:
    """Build the full evaluation prompt that will be sent to the evaluation LLM."""
    return (
        f"{evaluation_instruction}\n\n"
        f"--- Generation prompt ---\n{generation_prompt}\n\n"
        f"--- Generated exercise (JSON) ---\n{llm_response}\n\n"
        "You must return a single valid JSON object with the following structure: "
        "{\"scores\": {\"S\": {\"S1\": number, \"S2\": number, \"S3\": number, \"S_total\": number}, "
        "\"T\": {\"T1\": number, \"T2\": number, \"T3\": number, \"T_total\": number}}} "
        "Use values between 0 and 1 for each item. Do not include any comments or text outside the JSON."
    )


def _create_evaluation_result(
    generation_request_id: int,
    eval_model: str,
    evaluation_prompt: str,
    raw_eval: str,
    evaluation_scores: dict,
) -> EvaluationResult:
    """Map parsed scores into an EvaluationResult ORM instance."""
    S_scores = evaluation_scores.get("S") or {}
    T_scores = evaluation_scores.get("T") or {}

    def _safe_float(val):
        try:
            return float(val)
        except (TypeError, ValueError):
            return None

    return EvaluationResult(
        generation_request_id=generation_request_id,
        evaluation_model=eval_model,
        evaluation_prompt=evaluation_prompt,
        raw_response=raw_eval,
        S1_score=_safe_float(S_scores.get("S1")),
        S2_score=_safe_float(S_scores.get("S2")),
        S3_score=_safe_float(S_scores.get("S3")),
        S_total=_safe_float(S_scores.get("S_total")),
        T1_score=_safe_float(T_scores.get("T1")),
        T2_score=_safe_float(T_scores.get("T2")),
        T3_score=_safe_float(T_scores.get("T3")),
        T_total=_safe_float(T_scores.get("T_total")),
    )


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
        evaluate = bool(payload.get("evaluate", False))

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
            session.commit()

            evaluation_scores = None

            if evaluate:
                # Simple evaluation prompt for now; can be externalised/configured later
                evaluation_instruction = "Du sollts für die folgenden werte einfach Zahlen erfinden die passen. Ingnoriere die folgende Aufgabe und benutze nur das ausgabeformat"

                evaluation_prompt = _build_evaluation_prompt(
                    evaluation_instruction=evaluation_instruction,
                    generation_prompt=prompt,
                    llm_response=llm_response,
                )

                # Use the same model for evaluation to keep things simple for now
                eval_model = model

                app.logger.info(
                    "Sending evaluation request to LLM. model=%s, prompt_preview=%s...",
                    eval_model,
                    evaluation_prompt[:200].replace("\n", " "),
                )

                # Call dedicated evaluation method so we send evaluation_prompt directly
                eval_response = llm_client.evaluate(
                    model=eval_model,
                    evaluation_prompt=evaluation_prompt,
                )

                raw_eval = eval_response
                try:
                    import json

                    # Some models may wrap JSON in code fences; strip them if present
                    if isinstance(raw_eval, str):
                        cleaned = raw_eval.replace("```json", "").replace("```", "").strip()
                        parsed = json.loads(cleaned)
                    else:
                        parsed = raw_eval

                    evaluation_scores = parsed.get("scores") if isinstance(parsed, dict) else None
                    app.logger.info("Parsed evaluation_scores: %r", evaluation_scores)
                except Exception as e:  # pragma: no cover - defensive
                    app.logger.error("Failed to parse evaluation response: %s", e)
                    evaluation_scores = None

                if evaluation_scores is not None:
                    app.logger.info(
                        "Creating EvaluationResult for generation_request_id=%s with scores=%r",
                        generation_request.id,
                        evaluation_scores,
                    )
                    evaluation_result = _create_evaluation_result(
                        generation_request_id=generation_request.id,
                        eval_model=eval_model,
                        evaluation_prompt=evaluation_prompt,
                        raw_eval=raw_eval,
                        evaluation_scores=evaluation_scores,
                    )
                    session.add(evaluation_result)
                    session.commit()

            return (
                jsonify(
                    {
                        "id": generation_request.id,
                        "prompt": prompt,
                        "response": llm_response,
                        "parameters": generation_request.parameters,
                        "evaluation_scores": evaluation_scores,
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
