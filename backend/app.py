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
    item_scores: dict,
    dimension_averages: dict,
    total_score: dict,
) -> EvaluationResult:
    """Map parsed evaluation JSON into an EvaluationResult ORM instance.

    Expected JSON shape (see evaluation prompt in `llm_client.evaluate`):
    {
      "metadata": { ... },
      "item_scores": {
        "T1": {"score": 0|1|2, "justification": "..."},
        ...
        "P4": {"score": 0|1|2, "justification": "..."}
      },
      "dimension_averages": {
        "exercise_type_adherence": number,
        "difficulty_profile_adherence": number,
        "study_goal_alignment": number,
        "length_adherence": number,
        "pedagogical_quality": number
      },
      "total_score": {"score": number, "max": 10}
    }
    """

    def _score(key: str):
        try:
            entry = item_scores.get(key) or {}
            return float(entry.get("score")) if entry.get("score") is not None else None
        except (TypeError, ValueError):
            return None

    def _avg(dim_key: str):
        try:
            val = dimension_averages.get(dim_key)
            return float(val) if val is not None else None
        except (TypeError, ValueError):
            return None

    def _total():
        try:
            val = total_score.get("score") if isinstance(total_score, dict) else None
            return float(val) if val is not None else None
        except (TypeError, ValueError):
            return None

    # Store all justifications as a JSON string for later analysis
    import json

    justifications = {
        key: (item_scores.get(key) or {}).get("justification")
        for key in item_scores.keys()
    }
    justification_text = json.dumps(justifications, ensure_ascii=False)

    return EvaluationResult(
        generation_request_id=generation_request_id,
        evaluation_model=eval_model,
        justification=justification_text,
        # T: Exercise adherence
        T1=_score("T1"),
        T2=_score("T2"),
        T=_avg("exercise_type_adherence"),
        # D: Difficulty profile adherence
        D1=_score("D1"),
        D2=_score("D2"),
        D3=_score("D3"),
        D4=_score("D4"),
        D=_avg("difficulty_profile_adherence"),
        # S: Study goal alignment
        S1=_score("S1"),
        S2=_score("S2"),
        S3=_score("S3"),
        S=_avg("study_goal_alignment"),
        # L: Length adherence
        L1=_score("L1"),
        L2=_score("L2"),
        L=_avg("length_adherence"),
        # P: Pedagogical quality
        P1=_score("P1"),
        P2=_score("P2"),
        P3=_score("P3"),
        P4=_score("P4"),
        P=_avg("pedagogical_quality"),
        # Overall total score
        full_score=_total(),
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

            evaluation = None

            if evaluate:

                eval_model = "gpt-5.1"  # This could be made dynamic based on parameters or config

                app.logger.info(
                    "Sending evaluation request to LLM. model=%s",
                    eval_model
                )

                # Call dedicated evaluation method which builds the evaluation prompt internally
                eval_response = llm_client.evaluate(llm_response)

                raw_eval = eval_response
                try:
                    import json

                    if isinstance(raw_eval, str):
                        cleaned = raw_eval.replace("```json", "").replace("```", "").strip()
                        parsed = json.loads(cleaned)
                    else:
                        parsed = raw_eval

                    item_scores = parsed.get("item_scores") if isinstance(parsed, dict) else None
                    dimension_averages = parsed.get("dimension_averages") if isinstance(parsed, dict) else None
                    total_score = parsed.get("total_score") if isinstance(parsed, dict) else None

                    app.logger.info(
                        "Parsed evaluation: item_scores_keys=%r dimension_averages=%r total_score=%r",
                        list(item_scores.keys()) if isinstance(item_scores, dict) else None,
                        dimension_averages,
                        total_score,
                    )
                except Exception as e:  # pragma: no cover - defensive
                    app.logger.error("Failed to parse evaluation response: %s", e)
                    item_scores = None
                    dimension_averages = None
                    total_score = None

                if isinstance(item_scores, dict):
                    evaluation_result = _create_evaluation_result(
                        generation_request_id=generation_request.id,
                        eval_model=eval_model,
                        item_scores=item_scores,
                        dimension_averages=dimension_averages or {},
                        total_score=total_score or {},
                    )
                    session.add(evaluation_result)
                    session.commit()

                    # Build structured evaluation payload for frontend
                    import json
                    justifications = {}
                    try:
                        if evaluation_result.justification:
                            justifications = json.loads(evaluation_result.justification)
                    except Exception:
                        justifications = {}

                    evaluation = {
                        "items": {
                            "T1": evaluation_result.T1,
                            "T2": evaluation_result.T2,
                            "D1": evaluation_result.D1,
                            "D2": evaluation_result.D2,
                            "D3": evaluation_result.D3,
                            "D4": evaluation_result.D4,
                            "S1": evaluation_result.S1,
                            "S2": evaluation_result.S2,
                            "S3": evaluation_result.S3,
                            "L1": evaluation_result.L1,
                            "L2": evaluation_result.L2,
                            "P1": evaluation_result.P1,
                            "P2": evaluation_result.P2,
                            "P3": evaluation_result.P3,
                            "P4": evaluation_result.P4,
                        },
                        "dimensions": {
                            "T": evaluation_result.T,
                            "D": evaluation_result.D,
                            "S": evaluation_result.S,
                            "L": evaluation_result.L,
                            "P": evaluation_result.P,
                        },
                        "fullScore": evaluation_result.full_score,
                        "justifications": justifications,
                    }

            return jsonify(
                {
                    "id": generation_request.id,
                    "parameters": parameters,
                    "response": llm_response,
                    "prompt": prompt,
                    "evaluation": evaluation,
                }
            )
        except Exception as e:
            app.logger.error("Error in /api/generate: %s", e, exc_info=True)
            session.rollback()
            return jsonify({"error": str(e)}), 500
        finally:
            session.close()

    @app.route("/api/health", methods=["GET"])
    def health_check():
        return "OK", 200

    @app.route("/api/tasks/<int:task_id>", methods=["GET"])
    def get_task(task_id: int):
        """Return a stored generation request (and its evaluation) by ID.

        The response mirrors the shape of /api/generate, so the frontend
        can reuse the same rendering logic.
        """
        session = session_factory()
        try:
            generation_request = session.query(GenerationRequest).get(task_id)
            if generation_request is None:
                return jsonify({"error": f"Task with id {task_id} not found"}), 404

            # Fetch the latest evaluation result for this task (if any)
            evaluation_row = (
                session.query(EvaluationResult)
                .filter(EvaluationResult.generation_request_id == generation_request.id)
                .order_by(EvaluationResult.created_at.desc())
                .first()
            )

            evaluation = None
            if evaluation_row is not None:
                import json as _json
                justifications = {}
                try:
                    if evaluation_row.justification:
                        justifications = _json.loads(evaluation_row.justification)
                except Exception:
                    justifications = {}

                evaluation = {
                    "items": {
                        "T1": evaluation_row.T1,
                        "T2": evaluation_row.T2,
                        "D1": evaluation_row.D1,
                        "D2": evaluation_row.D2,
                        "D3": evaluation_row.D3,
                        "D4": evaluation_row.D4,
                        "S1": evaluation_row.S1,
                        "S2": evaluation_row.S2,
                        "S3": evaluation_row.S3,
                        "L1": evaluation_row.L1,
                        "L2": evaluation_row.L2,
                        "P1": evaluation_row.P1,
                        "P2": evaluation_row.P2,
                        "P3": evaluation_row.P3,
                        "P4": evaluation_row.P4,
                    },
                    "dimensions": {
                        "T": evaluation_row.T,
                        "D": evaluation_row.D,
                        "S": evaluation_row.S,
                        "L": evaluation_row.L,
                        "P": evaluation_row.P,
                    },
                    "fullScore": evaluation_row.full_score,
                    "justifications": justifications,
                }

            return jsonify(
                {
                    "id": generation_request.id,
                    "parameters": generation_request.parameters,
                    "response": generation_request.generated_response,
                    "prompt": generation_request.prompt_template,
                    "evaluation": evaluation,
                    "created_at": generation_request.created_at.isoformat() if generation_request.created_at else None,
                }
            )
        finally:
            session.close()

    return app


if __name__ == "__main__":
    application = create_app()
    application.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
