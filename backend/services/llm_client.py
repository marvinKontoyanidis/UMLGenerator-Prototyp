import os
from dataclasses import dataclass
from typing import Optional
import logging

import google.generativeai as genai
from dotenv import load_dotenv
from openai import OpenAI

import requests

# Load local environment file if present (for development)
# This will not override already-set environment variables.
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env.local"), override=False)

logger = logging.getLogger(__name__)


@dataclass
class LLMConfig:
    #ChatGPT OpenAI
    bisai_url: str = None
    bisai_api_key: Optional[str] = None
    #Gemini AI Google
    gemini_api_key: Optional[str] = None

    @classmethod
    def from_env(cls) -> "LLMConfig":
        return cls(
            bisai_url=os.getenv("BISAI_BASE_URL"),
            bisai_api_key=os.getenv("BISAI_API_KEY"),
            gemini_api_key=os.getenv("GEMINI_API_KEY"),
        )


class LLMClient:
    """Simple LLM abstraction supporting OpenAI and (optionally) Gemini."""

    def __init__(self, config: Optional[LLMConfig] = None) -> None:
        self.config = config or LLMConfig.from_env()

        if not self.config.bisai_api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is not set. Please configure it in .env.local or the environment."
            )

        self._openai_client = OpenAI(api_key=self.config.bisai_api_key)

        # Gemini is optional – only initialize if a key is present
        self._gemini_client: Optional[genai.GenerativeModel] = None
        if self.config.gemini_api_key:
            genai.configure(api_key=self.config.gemini_api_key)

    def generate(self, user_prompt: str, model: str) -> str:
        """Generate a UML exercise using a given model.

        - Default model: "gpt-4" (OpenAI)
        - Supported values: "gpt-4", "gpt-3.5", "gemini-1.5"
        """

        system_prompt = (
            "You are an assistant that generates UML modeling exercises for students in software engineering. "
            "Return the exercise in clear structured JSON with fields: "
            "title, description, requirements, diagram_type."
        )

        if model in ("gpt-4", "gpt-3.5" , "gpt-oss:120b"):
            logger.info("Sending prompt to OpenAI model %s", model)
            return send_to_basai(self, model, system_prompt, user_prompt)
        elif model == "gemini-2.5-flash":
            logger.info("Sending prompt to Gemini model %s", model)
            return send_to_gemini(self, model, system_prompt, user_prompt)
        else:
            raise ValueError(f"Unsupported model: {model}")


# Backwards-compatible function for any existing direct imports
_client_singleton: Optional[LLMClient] = None


def _get_default_client() -> LLMClient:
    global _client_singleton
    if _client_singleton is None:
        _client_singleton = LLMClient()
    return _client_singleton


def generate_uml_exercise_with_openai(user_prompt: str) -> str:
    """Legacy helper that delegates to the shared LLMClient instance using default model."""
    return _get_default_client().generate(user_prompt)


def send_to_basai(self: LLMClient, model_name: str, system_prompt: str, user_prompt: str) -> str:

    url = f"{self.config.bisai_url}/api/chat/completions"
    headers = {
        'Authorization': f'Bearer {self.config.bisai_api_key}',
        'Content-Type': 'application/json',
    }

    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
    }

    response = requests.post(url,headers=headers, json=payload, timeout=60)
    response.raise_for_status()
    data = response.json()

    return data["choices"][0]["message"]["content"]


def send_to_gemini(self: LLMClient, model_name: str, system_prompt: str, user_prompt: str) -> str:
    if not self.config.gemini_api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Please configure it in .env.local or the environment to use Gemini."
        )

    full_prompt = system_prompt + "\n" + user_prompt

    model = genai.GenerativeModel(model_name)
    response = model.generate_content(full_prompt)

    return response.text or ""


