import os
from dataclasses import dataclass
from typing import Optional
import logging

import google.generativeai as genai
from dotenv import load_dotenv
from openai import OpenAI

import requests
from sqlalchemy import null

# Load local environment file if present (for development)
# This will not override already-set environment variables.
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env.local"), override=False)

logger = logging.getLogger(__name__)


@dataclass
class LLMConfig:
    # ChatGPT OpenAI
    openai_api_key: Optional[str] = None
    # BaSiAI (OpenAI-compatible API)
    bisai_url: str = None
    bisai_api_key: Optional[str] = None
    # Gemini AI Google
    gemini_api_key: Optional[str] = None

    @classmethod
    def from_env(cls) -> "LLMConfig":
        return cls(
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            bisai_url=os.getenv("BISAI_BASE_URL"),
            bisai_api_key=os.getenv("BISAI_API_KEY"),
            gemini_api_key=os.getenv("GEMINI_API_KEY"),
        )


class LLMClient:
    """Simple LLM abstraction supporting OpenAI and Gemini."""

    def __init__(self, config: Optional[LLMConfig] = None) -> None:
        self.config = config or LLMConfig.from_env()

        if not self.config.bisai_api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is not set. Please configure it in .env.local or the environment."
            )

        if not self.config.openai_api_key:
            raise RuntimeError(
                "OPENAI_KEY is not set. Please configure it in .env.local or the environment."
            )

        self._openai_client = OpenAI(api_key=self.config.openai_api_key)


        # Gemini is optional – only initialize if a key is present
        self._gemini_client: Optional[genai.GenerativeModel] = None
        if self.config.gemini_api_key:
            genai.configure(api_key=self.config.gemini_api_key)

    def generate(self, model: str, ex_type: str, dif_level: str, study_goal: str, length: str) -> tuple[str, str]:
        """Generate a UML exercise using a given model.

        This method is **only** for exercise generation. It always builds
        an internal system prompt via `prompt_generation` based on the
        structured parameters.

        - Default model: "gpt-4" (OpenAI)
        - Supported values: "gpt-4", "gpt-3.5", "gemini-1.5"

        Returns:
            - llm_response: `str`
            - system_prompt: `str`
        """

        system_prompt = prompt_generation(ex_type, dif_level, study_goal, length)


        if model == "gpt-5":
            logger.info("Sending generation prompt to OpenAI model %s", model)
            llm_response = send_to_openai(self, model, system_prompt)
        if model in ("gpt-4", "gpt-3.5", "gpt-oss:120b"):
            logger.info("Sending generation prompt to OpenAI-compatible model %s", model)
            llm_response = send_to_basai(self, model, system_prompt)
        elif model == "gemini-2.5-flash":
            logger.info("Sending generation prompt to Gemini model %s", model)
            llm_response =  send_to_gemini(self, model, system_prompt)
        else:
            raise ValueError(f"Unsupported model: {model}")

        return llm_response, system_prompt

    def evaluate(self, model: str, evaluation_prompt: str) -> str:
        """Send an evaluation prompt as-is to the given model and return raw text.

        This method must be used for scoring/evaluation, so that the
        evaluation prompt built in the API layer is not overridden by
        the exercise-generation logic.
        """

        if model == "gpt-5":
            logger.info("Sending evaluation prompt to OpenAI model %s", model)
            return send_to_openai(self, model, evaluation_prompt)
        if model in ("gpt-4", "gpt-3.5", "gpt-oss:120b"):
            logger.info("Sending evaluation prompt to OpenAI-compatible model %s", model)
            return send_to_basai(self, model, evaluation_prompt)
        elif model == "gemini-2.5-flash":
            logger.info("Sending evaluation prompt to Gemini model %s", model)
            return send_to_gemini(self, model, evaluation_prompt)
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

def send_to_openai(self: LLMClient, model_name: str, system_prompt: str) -> str:
    response = self._openai_client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "system", "content": system_prompt}
        ],
        temperature=1,
    )
    return response.choices[0].message.content

def send_to_basai(self: LLMClient, model_name: str, system_prompt: str) -> str:
    url = f"{self.config.bisai_url}/api/chat/completions"
    headers = {
        'Authorization': f'Bearer {self.config.bisai_api_key}',
        'Content-Type': 'application/json',
    }

    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": system_prompt}
        ]
    }

    response = requests.post(url, headers=headers, json=payload, timeout=60)
    response.raise_for_status()
    data = response.json()

    return data["choices"][0]["message"]["content"]


def send_to_gemini(self: LLMClient, model_name: str, system_prompt: str) -> str:
    if not self.config.gemini_api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Please configure it in .env.local or the environment to use Gemini."
        )

    model = genai.GenerativeModel(model_name)
    response = model.generate_content(system_prompt)

    return response.text or ""


def prompt_generation(exercise_type: str, difficulty_level: str, study_goal: str, length: str) -> str:
    start_prompt = None
    exercise_prompt = None
    difficulty_prompt = None
    study_goal_prompt = None
    length_prompt = None
    output_prompt = None

    # Start prompt
    # Defines the overall context and a role for the LLM
    start_prompt = """
        You are an AI tutoring assistant that generates UML modelling exercises for undergraduate computer science students.
        Your primary goal is to create pedagogically meaningful, text-based problem statements that help students practise and improve their UML modelling skills.
        
        Context:
            - The exercises are used in a university course on software modelling and UML.
            - Target learners are Bachelor students with basic introductory knowledge of UML.
            - The generated exercises will be reviewed and possibly adapted by human instructors.
            
        General requirements:
            - Always generate a realistic, domain-independent scenario that can be understood without specialised prior knowledge.
            - Focus on clarity, coherence, and sufficient detail so that students can derive an unambiguous UML model, unless controlled ambiguity is explicitly requested.
            - Respect all constraints given in the prompt parameters (exercise type, difficulty level, study goal, and length).
            - Do not generate any UML diagrams or code directly; instead, describe the scenario and the modelling requirements in natural language so that students can create the diagram themselves.
            - If there is any conflict between general conventions and the explicit parameter descriptions, always follow the explicit parameter descriptions.
        """
    
    # Defines exercise type prompt
    if exercise_type == "Class diagram":
        exercise_prompt = """
            Exercise type: UML class diagram (text-based).

            You must generate an exercise whose intended solution is a UML class diagram.
            Design a problem description that describes a domain scenario and the required classes, associations, and constraints only implicitly, through natural-language requirements.
            
            Constraints:
            - The output must be purely text-based.
            - Do NOT include any UML class diagram notation, ASCII art, or code.
            - Instead, describe the scenario and what needs to be modelled so that students can construct the class diagram themselves.
            - Make it clear from the wording that students are expected to create a UML class diagram as the solution artefact (not another UML diagram type).
            - The text must contain enough information about classes, relevant attributes or roles, and relationships so that a well-defined class diagram can be derived.
            """

    # Define difficulty level prompt
    # Defines the Difficulty Index (DI) for the LLM to follow when generating exercises
    difficulty_prompt = """
        The difficulty of the exercise is controlled using a five-dimensional Difficulty Index (DI). 
        Each dimension is scored from 0 (low) to 2 (high):
        
        1) Size / model scope:   
        - 0: ≤ 4 classes and ≤ 4 relationships   
        - 1: 5–8 classes or 5–10 relationships   
        - 2: ≥ 9 classes or ≥ 11 relationships
        
        2)Relationship complexity:   
        - 0: Associations only; no inheritance; no aggregation/composition   
        - 1: Includes either inheritance or aggregation/composition   
        - 2: Includes inheritance and aggregation/composition, or requires role names / navigability decisions
        
        3)Constraints & precision:   
        - 0: Only basic multiplicities   
        - 1: Multiple multiplicities plus at least one special case (optional/mandatory edge case)   
        - 2: Explicit constraints (OCL-like rules) or cross-cutting consistency constraints
        
        4)Ambiguity in the text:   
        - 0: Fully unambiguous requirements   
        - 1: Exactly one minor ambiguity, resolvable without extra assumptions   
        - 2: Multiple plausible modelling variants; assumptions must be stated and justified
        
        5) Bloom cognitive process level required:   - 0: Remember / understand   - 1: Apply / analyze   - 2: Evaluate / create
        
        You must align the exercise with the following overall difficulty level:
        
        - EASY: 
            Aim for DI scores mostly 0, with at most one dimension at 1.        
            The model size and relationship complexity should be low,
            the text should be unambiguous, and the cognitive demand should be
            limited to remembering, understanding, and basic application.
        
        - MEDIUM: 
            Aim for a mixture of scores 0 and 1, and optionally one dimension at 2.
            The model should have moderate size and at least one advanced          
            relationship type (inheritance or aggregation/composition),          
            with some additional constraints and limited ambiguity.          
            Students should need to apply and analyse, not just recall.
            
        - HARD: 
            Aim for scores mostly 2 across the dimensions.        
            The model should be large, with multiple advanced relationship types,        
            explicit constraints or cross-cutting consistency rules,        
            and controlled ambiguity that requires students to make and justify modelling assumptions.        
            The task should require evaluating alternatives and creating a coherent model.
        
    """
    # Append specific difficulty level instructions
    difficulty_prompt += """
        \n\n You must generate a """ + difficulty_level + """ exercise according to the Difficulty Index. 
        Follow the """ + difficulty_level + """ profile described above.
        """
    # Define study goal prompt
    match study_goal:
        case "LIS":
            study_goal_prompt = """
                Study goal (targeted misconception): Incorrect use of multiplicity between classes (LIS).

                Explanation:
                In UML class diagrams, multiplicities express how many instances of one class can be related to instances of another class (e.g., 1, 0..*, 1..*, *). 
                Empirical studies show that many students struggle to define correct multiplicities. 
                Typical problems include:
                - Omitting multiplicities entirely,
                - Using 1-to-1 where 1-to-* or 0..* is required,
                - Failing to recognise that a whole–part relationship may involve multiple parts,
                - Confusing multiplicity issues with method design (e.g., introducing getAllX() instead of modelling a 1-to-* association).
                
                For this exercise, you must design the problem such that:
                - Correct multiplicities are crucial for a valid solution,
                - At least one association requires a non-trivial multiplicity (e.g., 1-to-*, 0..*, 1..*),
                - The scenario naturally invites the typical student error of choosing 1-to-1 instead of 1-to-*,
                - The text is still realistic and understandable for undergraduate students.
                
                Your exercise must therefore explicitly support the study goal of practising and assessing correct multiplicity choices in UML class diagrams.

            """
        case "COM":
            study_goal_prompt = """
                Study goal (targeted misconception): Classes with inappropriate or insufficient behavior (COM).
                
                Explanation:
                In object-oriented modelling, a class represents an abstraction, while an object is a concrete entity in time and space. A class should encapsulate the essential attributes and behaviors that are relevant for the software system. Empirical studies show that many students struggle to assign appropriate behavior to classes. Typical problems include:
                - Methods that do not correspond to the underlying concept of the class,
                - Overloaded classes with many unrelated methods and low cohesion,
                - Classes without any meaningful behavior (only attributes and trivial getters/setters),
                - Misplaced behavior that conceptually belongs to another class.
                
                For example, students might:
                - Add a moveFurniture() method to a Room class,
                - Attach payment- or registration-related methods to a Bet class instead of a dedicated Payment or Registration class,
                - Define classes with only get() and set() methods and no domain-specific operations.
                
                For this exercise, you must design the problem such that:
                - Correct assignment of behavior (methods) to classes is crucial for a good solution,
                - At least one class in the intended solution clearly requires cohesive, domain-relevant methods,
                - The scenario naturally invites the typical student error of either overloading a class with unrelated methods or assigning behavior to the wrong class,
                - A reasonable solution requires students to think about abstraction and responsibility distribution between classes.
                
                Your exercise must therefore explicitly support the study goal of practising and assessing the proper assignment of behavior to classes in UML class diagrams.

            """
        case "ART":
            study_goal_prompt = """
                Study goal (targeted misconception): Defining attributes that should be modelled as classes (ATR).
    
                Explanation:
                This misconception concerns the tendency to simplify complex domain concepts by representing them only as attributes instead of modelling them as separate classes. Empirical studies show that novice modellers often:
                - Collapse rich concepts into a single attribute (e.g., a "type" attribute instead of a dedicated class),
                - Misassign attributes to the wrong class,
                - Omit important attributes or related classes altogether,
                - Think primarily in terms of data fields rather than object abstractions and responsibilities.
                
                Examples include:
                - Using an attribute "type" or "typeOfBet" instead of a separate BetType class,
                - Assigning salary calculation directly to an Employee class instead of modelling a HumanResources or Payroll class,
                - Treating complex concepts as mere data fields instead of identifying them as entities with their own attributes and behavior.
                
                For this exercise, you must design the problem such that:
                - The domain contains at least one concept that clearly deserves to be modelled as a separate class rather than as a simple attribute,
                - A typical novice solution would be tempted to represent this concept as a single attribute on another class,
                - A better solution recognises the need for a dedicated class with its own attributes and behavior,
                - Students must think about the abstraction level and decide which concepts in the scenario should become classes.
                
                Your exercise must therefore explicitly support the study goal of practising and assessing the correct identification of classes versus mere attributes in UML class diagrams.

            """
        case "HOL":
            study_goal_prompt = """
                Study goal (targeted misconception): Not considering the problem from a holistic perspective (HOL).
    
                Explanation:
                This misconception relates to students focusing only on the most obvious part of a problem while neglecting other relevant aspects that are necessary for a complete solution. Empirical studies show that novice modellers often:
                - Concentrate on the main task or main objects, but ignore important secondary concepts,
                - Fail to identify all required classes or relationships in the domain,
                - Overlook contextual information and edge cases mentioned in the problem description,
                - Violate basic object-oriented design principles, resulting in incomplete or low-quality models.
                
                For example, in scenarios involving moving objects, students may ignore interactions such as collisions or boundary conditions; in more complex domains, they may omit classes that are essential for representing the full behaviour of the system.
                
                For this exercise, you must design the problem such that:
                - A correct UML class diagram requires considering multiple aspects of the scenario, not just a single main task,
                - The text explicitly contains secondary requirements or conditions that are easy to overlook but important for a complete model,
                - A typical novice solution would miss at least one important class, relationship, or constraint because the student focused only on the core functionality,
                - A high-quality solution integrates all mentioned aspects into a coherent set of classes and relationships.
                
                Your exercise must therefore explicitly support the study goal of practising and assessing students' ability to interpret the problem from a holistic perspective and to identify all relevant elements of the domain when constructing a UML class diagram.

            """
        case _:
            study_goal_prompt = """
                No specific study goal selected. Generate a standard UML modelling exercise.
            """

    # Define length prompt

    match length:
        case "Short":
            length_prompt = """
                You must keep the problem description SHORT:
                    - Approximately 3–5 sentences,
                    - Focus on essential domain concepts and relationships,
                    - Avoid unnecessary narrative details.
            """
        case "Medium":
            length_prompt = """
                You must keep the problem description of MEDIUM length:
                    - Approximately 6–10 sentences,
                    - Provide realistic context and some secondary but relevant details,
                    - Ensure that all information needed for the model is clearly present.
            """
        case "Long":
            length_prompt = """
               You must create a LONG problem description:
                    - More than 10 sentences,
                    - Include richer narrative context and multiple related situations,
                    - All details should have potential modelling relevance.
            """

    # Define closing prompt (output format)

    output_prompt = """
    Output format requirements:
    
    You must return the generated exercise as a single valid JSON object.
    Do not include any explanations, comments, or text before or after the JSON.
    Do not use trailing commas. Do not format the JSON as a code block.
    
    The JSON object must have exactly the following structure and fields:
    
    {
      "metadata": {
        "exercise_type": "text_only",
        "difficulty_level": "easy" | "medium" | "hard",
        "length": "short" | "medium" | "long",
        "study_goal_id": "string identifier of the targeted misconception or learning goal",
        "diagram_type": "class" | "sequence" | "state_machine" | "other"
      },
      "difficulty_index_profile": {
        "size_scope": 0 | 1 | 2,
        "relationship_complexity": 0 | 1 | 2,
        "constraints_precision": 0 | 1 | 2,
        "ambiguity": 0 | 1 | 2,
        "bloom_level": 0 | 1 | 2
      },
      "title": "Short, descriptive title of the exercise",
      "learning_objectives": [
        "First learning objective in one sentence.",
        "Second learning objective in one sentence."
      ],
      "problem_description": "Full natural-language description of the exercise scenario and task, in the requested language.",
      "uml_requirements": {
        "must_include": [
          "Explicit UML elements or constraints that must appear in a correct solution, e.g. 'At least one 1-to-* association between Gambler and Bet'."
        ],
        "common_misconceptions_to_trigger": [
          "Optional description of typical student errors that this exercise is intended to reveal, e.g. 'students might model a 1-to-1 association instead of 1-to-*'."
        ]
      }
    }

    Use the parameter values provided earlier in the prompt to fill in:
    - "difficulty_level",
    - "length",
    - "study_goal",
    - "diagram_type",
    - and the Difficulty Index scores in "difficulty_index_profile".
    
    If you are unsure about a field, make a reasonable assumption that is consistent with the rest of the prompt, but never change the JSON structure.

    """

    # Combine all parts into a single prompt

    return (start_prompt + " \n\n "
            + exercise_prompt + " \n\n "
            + difficulty_prompt + " \n\n "
            + study_goal_prompt + " \n\n "
            + length_prompt + " \n\n "
            + output_prompt)


