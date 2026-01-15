from flask import Flask, request, jsonify

app = Flask(__name__)


@app.post("/generate")
def generate():
    payload = request.get_json(force=True)
    prompt = payload.get("prompt", "")
    # Simple echo mock to keep pipeline testable without real LLM access
    response_text = f"[MOCK LLM RESPONSE]\nPrompt received:\n{prompt}"
    return jsonify({"text": response_text})


@app.get("/health")
def health():
    return "OK", 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
