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


        if model == "gpt-5.1-chat-latest":
            logger.info("Sending generation prompt to OpenAI model %s", model)
            llm_response = send_to_openai(self, model, system_prompt)
        elif model in ("gpt-4", "gpt-3.5", "gpt-oss:120b"):
            logger.info("Sending generation prompt to OpenAI-compatible model %s", model)
            llm_response = send_to_basai(self, model, system_prompt)
        elif model == "gemini-2.5-flash":
            logger.info("Sending generation prompt to Gemini model %s", model)
            llm_response =  send_to_gemini(self, model, system_prompt)
        else:
            raise ValueError(f"Unsupported model: {model}")

        return llm_response, system_prompt

    def evaluate(self, exercise_text: str) -> str:
        """Send an evaluation prompt as-is to the given model and return raw text.

        This method must be used for scoring/evaluation, so that the
        evaluation prompt built in the API layer is not overridden by
        the exercise-generation logic.

        Evaluation is currently done only with the OPenAI 5.1 model.
        """
        evaluation_prompt = """
        You are an expert rater for UML class diagram exercises. Your task is to evaluate a single generated exercise according to a predefined rating instrument.

        You will receive:
        - A JSON metadata block describing the generation parameters.
        - The full text of the exercise (problem description).
        
        Your job:
        1. Apply the rating instrument with all its dimensions and items.
        2. Assign scores on a 0/1/2 scale for each item.
        3. Compute per-dimension scores and an overall total score.
        4. Provide a brief textual justification for each item score.
        
        -----------------------------
        RATING INSTRUMENT OVERVIEW
        -----------------------------
        
        The rating instrument has five dimensions:
        
        1) Exercise type adherence (T1–T2)
        2) Difficulty profile adherence (D1–D4)
        3) Study goal alignment (S1–S3)
        4) Length adherence (L1–L2)
        5) Pedagogical quality (P1–P4)
        
        All items use the same 3-point scale:
        - 2 = criterion fully met
        - 1 = criterion partially met
        - 0 = criterion not met
        
        You must strictly follow the rubrics below for each item.
        
        ---------------------------------
        DIMENSION 1: EXERCISE TYPE (T)
        ---------------------------------
        
        T1 – Explicit class diagram request  
        Question: Does the exercise explicitly require students to construct a UML class diagram as the solution artefact?
        
        - 2: The exercise explicitly states that students should construct a UML class diagram as the solution artefact (e.g., “construct a UML class diagram” or equivalent wording), and no other diagram type is suggested.
        - 1: The exercise refers to a “class diagram” or “class model”, but without explicitly mentioning UML or with somewhat vague wording (e.g., “model the classes of the system”); it is still reasonably clear that a class diagram is intended.
        - 0: The exercise does not mention a class diagram at all, suggests a different type of diagram (e.g., sequence diagram), or leaves the solution artefact entirely unclear.
        
        T2 – Purely text-based task  
        Question: Is the problem description purely text-based, without given diagrams or code?
        
        - 2: The problem description is purely text-based; it contains no UML diagrams, no code snippets, and no other non-textual solution elements (aside from simple lists or headings).
        - 1: The problem description contains minor structured elements (e.g., a short table, a small code fragment) that support understanding the domain, but the task is still clearly formulated as a text-based exercise.
        - 0: The exercise provides substantial non-textual material that is central to the task (e.g., pre-given UML diagrams, extensive code, pseudo-graphical models), so that it is no longer a purely text-based modelling task.
        
        
        -------------------------------------
        DIMENSION 2: DIFFICULTY PROFILE (D)
        -------------------------------------
        
        Use the metadata fields for difficulty level (e.g., "easy", "medium", "hard") and your understanding of typical model complexity for that level.
        
        D1 – Size and scope  
        Question: Does the expected model size match the target difficulty level?
        
        - 2: The intended solution requires approximately the number of classes and relationships expected for the target difficulty level (e.g., few and clearly distinguishable classes for easy; noticeably more classes and relationships with richer structure for hard).
        - 1: Size and scope are in the general vicinity of the target level, but somewhat too small or too large (e.g., slightly complex easy task or somewhat simple hard task).
        - 0: Size and scope deviate substantially from what would be expected for that level (e.g., easy task that actually needs a large complex model; hard task solvable with a very small trivial model).
        
        D2 – Relationship complexity  
        Question: Does the range and complexity of relationships fit the difficulty level?
        
        - 2: The task requires about the range and complexity of relationships (associations, aggregation/composition, inheritance, etc.) that are plausible for the selected level (e.g., mainly simple associations for easy; more varied and combined relationships for hard).
        - 1: Some expected relationship types or combinations are present, but overall relationship complexity is slightly below or above the target profile.
        - 0: Relationships are almost exclusively trivial (or, conversely, overly complex) and clearly do not match what one would expect for the selected difficulty level.
        
        D3 – Constraints and precision  
        Question: Does the amount and type of constraints/precision match the difficulty level?
        
        - 2: The description contains the amount and type of constraints and required precision appropriate for this level (e.g., few simple constraints for easy; several explicit conditions to be reflected in the model for medium/hard).
        - 1: Some relevant constraints or precision requirements are present, but their number or importance is somewhat below or above what would be expected for this level.
        - 0: Either almost no relevant constraints where they would be expected (especially medium/hard), or a nominally easy task is overloaded with detailed constraints that do not fit the level.
        
        D4 – Ambiguity and cognitive demand  
        Question: Does ambiguity and cognitive effort match the difficulty level?
        
        - 2: The degree of textual ambiguity and cognitive effort corresponds closely to the selected level (e.g., very low ambiguity and straightforward interpretation for easy; deliberate ambiguity or openness requiring modelling decisions for hard).
        - 1: Ambiguity and cognitive demand are roughly in line with the target level, but slightly too low or too high.
        - 0: Ambiguity and cognitive demand are clearly inappropriate for the level (e.g., highly vague and confusing for easy; extremely trivial and straightforward for hard).
        
        ----------------------------------
        DIMENSION 3: STUDY GOAL (S)
        ----------------------------------
        
        Use the metadata field “study_goal” (values: "LIS", "COM", "ATR", "HOL") and the following detailed descriptions of each goal. When scoring S1–S3, check how well the exercise supports the respective study goal.
        
        STUDY GOAL "LIS" – Incorrect use of multiplicity between classes  
        
        Targeted misconception: Incorrect use of multiplicity between classes (LIS).
        
        Explanation:  
        In UML class diagrams, multiplicities express how many instances of one class can be related to instances of another class (e.g., 1, 0..*, 1..*, *). Many students struggle to define correct multiplicities. Typical problems include:
        - Omitting multiplicities entirely,
        - Using 1-to-1 where 1-to-* or 0..* is required,
        - Failing to recognise that a whole–part relationship may involve multiple parts,
        - Confusing multiplicity issues with method design (e.g., introducing getAllX() instead of modelling a 1-to-* association).
        
        For a good LIS exercise:
        - Correct multiplicities must be crucial for a valid solution,
        - At least one association should require a non-trivial multiplicity (e.g., 1-to-*, 0..*, 1..*),
        - The scenario should naturally invite the typical student error of choosing 1-to-1 instead of 1-to-*,
        - The text should be realistic and understandable for undergraduate students.
        
        STUDY GOAL "COM" – Classes with inappropriate or insufficient behavior  
        
        Targeted misconception: Classes with inappropriate or insufficient behavior (COM).
        
        Explanation:  
        A class should encapsulate essential attributes and behaviours relevant for the system. Students often struggle to assign appropriate behaviour to classes. Typical problems:
        - Methods that do not correspond to the underlying concept of the class,
        - Overloaded classes with many unrelated methods and low cohesion,
        - Classes without meaningful behaviour (only attributes and trivial getters/setters),
        - Misplaced behaviour that conceptually belongs to another class.
        
        Examples:
        - Adding moveFurniture() to a Room class,
        - Attaching payment/registration methods to a Bet class instead of a Payment/Registration class,
        - Defining classes with only get()/set() and no domain-specific operations.
        
        For a good COM exercise:
        - Correct assignment of behaviour (methods) to classes is crucial for a good solution,
        - At least one class clearly requires cohesive, domain-relevant methods,
        - The scenario naturally invites errors like overloading a class or assigning behaviour to the wrong class,
        - A reasonable solution requires thinking about abstraction and responsibility distribution.
        
        STUDY GOAL "ATR" – Attributes that should be modelled as classes  
        
        Targeted misconception: Defining attributes that should be modelled as classes (ATR).
        
        Explanation:  
        Novices tend to simplify complex domain concepts as single attributes instead of modelling them as separate classes. Typical issues:
        - Collapsing rich concepts into a single attribute (e.g., a "type" attribute instead of a dedicated class),
        - Misassigning attributes to the wrong class,
        - Omitting important attributes or related classes,
        - Thinking in “data fields” rather than abstractions and responsibilities.
        
        Examples:
        - Using an attribute "type" or "typeOfBet" instead of a separate BetType class,
        - Assigning salary calculation directly to Employee instead of HumanResources/Payroll,
        - Treating complex concepts as mere fields instead of entities with own attributes/behaviour.
        
        For a good ATR exercise:
        - The domain must include at least one concept that clearly deserves to be a separate class rather than a simple attribute,
        - A typical novice solution would be tempted to model this concept as a single attribute on another class,
        - A better solution recognises the need for a dedicated class with its own attributes and behaviour,
        - Students must think about abstraction level and which concepts should become classes.
        
        STUDY GOAL "HOL" – Not considering the problem holistically  
        
        Targeted misconception: Not considering the problem from a holistic perspective (HOL).
        
        Explanation:  
        Students often focus only on the most obvious part of a problem and neglect other relevant aspects needed for a complete solution. Typical issues:
        - Concentrating on main objects while ignoring important secondary concepts,
        - Failing to identify all required classes or relationships,
        - Overlooking contextual information and edge cases in the description,
        - Violating basic OO design principles, resulting in incomplete or low-quality models.
        
        Examples:
        - Ignoring collisions or boundary conditions in moving-object scenarios,
        - Omitting essential classes in more complex domains.
        
        For a good HOL exercise:
        - A correct diagram must consider multiple aspects of the scenario, not just a single main task,
        - The text should contain secondary requirements/conditions that are easy to overlook but important,
        - A typical novice solution would miss at least one important class/relationship/constraint because focus is only on core functionality,
        - A high-quality solution integrates all mentioned aspects into a coherent model.
        
        Now apply the generic study goal items:
        
        S1 – Target misconception is central to the task  
        Question: Is the selected study goal clearly at the core of the exercise?
        
        - 2: The selected study goal is clearly central: scenario and requirements are obviously designed around this specific conceptual difficulty (in the sense of the corresponding description above).
        - 1: The targeted concept/misconception is recognisably relevant, but other aspects are at least equally prominent, so the focus is diluted.
        - 0: The study goal plays at most a marginal role; the scenario does not seem designed around this particular difficulty.
        
        S2 – Correct solution requires addressing the targeted misconception  
        Question: Is addressing the study goal necessary for a good solution?
        
        - 2: A high-quality solution is only possible if students explicitly overcome the targeted misconception (e.g., correct multiplicities for LIS, appropriate behaviour assignment for COM, correct class vs attribute decision for ATR, or consideration of all relevant aspects for HOL).
        - 1: Correctly addressing the misconception clearly improves the solution quality, but a reasonably acceptable solution is still possible if this aspect is only partially or implicitly addressed.
        - 0: Students can solve the task in a largely satisfactory way without really addressing the targeted misconception.
        
        S3 – Plausibility of typical novice errors  
        Question: Are typical errors for this study goal plausible in this task?
        
        - 2: The description makes it very plausible that typical novice errors for this goal could occur (as described above for the respective study goal).
        - 1: Such errors are possible, but not particularly likely or strongly suggested by the wording.
        - 0: It is hard to imagine that the typical novice errors for this study goal would occur here; the scenario does not naturally invite them.
        
        -------------------------------
        DIMENSION 4: LENGTH (L)
        -------------------------------
        
        Use the metadata “length” (e.g., "short", "medium", "long") and the actual sentence count.
        
        L1 – Sentence count within target range  
        Question: Does the number of sentences fit the length category?
        
        - 2: Sentence count lies within or very close to the predefined range for the selected category (short/medium/long).
        - 1: Sentence count deviates slightly (e.g., by one or two sentences), but still roughly reflects the intended category.
        - 0: Sentence count clearly deviates (e.g., “short” task with many sentences or “long” task with very few).
        
        L2 – Density and relevance of information  
        Question: Is the information density appropriate for the length?
        
        - 2: Amount of information is appropriate: most sentences contribute relevant details to the modelling task, with little or no unnecessary narrative fluff.
        - 1: A noticeable number of sentences are only loosely related (flavour text), but core information remains sufficiently dense and relevant.
        - 0: Many sentences are off-topic, redundant, or irrelevant, making the task unnecessarily bloated or, conversely, missing important information.
        
        ------------------------------------
        DIMENSION 5: PEDAGOGICAL QUALITY (P)
        ------------------------------------
        
        P1 – Clarity and comprehensibility  
        Question: Is the problem clearly worded and understandable?
        
        - 2: Clearly worded, unambiguous, and easy to understand for undergraduate students; main task and expectations are explicitly stated.
        - 1: Some unclear or awkward phrases, but overall task and expectations remain understandable.
        - 0: Several passages are unclear, ambiguous, or misleading; students are likely to be confused about what to do.
        
        P2 – Realism and appropriateness of the scenario  
        Question: Is the scenario realistic and appropriate for the learner group?
        
        - 2: Scenario is realistic and appropriate; describes a domain that students can plausibly relate to without being distracted by implausible, exotic, or inconsistent details.
        - 1: Scenario is somewhat artificial, unusual, or simplified, but still acceptable and not seriously distracting.
        - 0: Scenario is clearly unrealistic, internally inconsistent, or so exotic that it is likely to distract or confuse students.
        
        P3 – Suitability for an introductory UML course  
        Question: Is the task suitable for an introductory course?
        
        - 2: In terms of scope, complexity, and formulation, the exercise is well suited for an introductory UML course (e.g., homework or exam question); it neither clearly under- nor over-challenges typical beginners.
        - 1: Slightly too easy or slightly too demanding, but still usable with minor adjustments.
        - 0: Clearly inappropriate: either trivial and not requiring meaningful modelling skills, or overly complex/technical/advanced.
        
        P4 – Internal consistency and completeness  
        Question: Is the task internally consistent and sufficiently complete?
        
        - 2: Description is internally consistent and sufficiently complete: no obvious contradictions, and all information necessary to construct a reasonable UML class diagram is present (even if some details remain open by design).
        - 1: Minor inconsistencies, unclear references, or small gaps exist, but they do not fundamentally prevent construction of a reasonable solution.
        - 0: Serious contradictions or missing essential information so that students cannot reasonably construct a UML class diagram without major unsupported assumptions.
        
        -----------------
        SCORING AND OUTPUT
        -----------------
        
        For each item (T1–T2, D1–D4, S1–S3, L1–L2, P1–P4):
        
        1. Decide whether the correct score is 0, 1, or 2 based on the rubrics above.
        2. Provide a short justification (1–3 sentences) referencing concrete aspects of the exercise text and/or metadata.
        
        Then compute per-dimension averages as follows:
        
        - T = (T1 + T2) / 2                            // exercise adherence
        - D = (D1 + D2 + D3 + D4) / 4                   // difficulty profile adherence
        - S = (S1 + S2 + S3) / 3                        // study goal alignment
        - L = (L1 + L2) / 2                             // length adherence
        - P = (P1 + P2 + P3 + P4) / 4                   // pedagogical quality
        
        Then compute the total score as the sum of these five averages:
        
        - full_score = T + D + S + L + P                // range 0–10
        
        -----------------
        RESPONSE FORMAT
        -----------------
        
        Return your answer as valid JSON with the following structure:
        
        {
          "metadata": {
            "difficulty": "...",
            "study_goal": "...",
            "length": "...",
            "model": "..."          // if given
          },
          "item_scores": {
            "T1": { "score": 0|1|2, "justification": "..." },
            "T2": { "score": 0|1|2, "justification": "..." },
            "D1": { "score": 0|1|2, "justification": "..." },
            "D2": { "score": 0|1|2, "justification": "..." },
            "D3": { "score": 0|1|2, "justification": "..." },
            "D4": { "score": 0|1|2, "justification": "..." },
            "S1": { "score": 0|1|2, "justification": "..." },
            "S2": { "score": 0|1|2, "justification": "..." },
            "S3": { "score": 0|1|2, "justification": "..." },
            "L1": { "score": 0|1|2, "justification": "..." },
            "L2": { "score": 0|1|2, "justification": "..." },
            "P1": { "score": 0|1|2, "justification": "..." },
            "P2": { "score": 0|1|2, "justification": "..." },
            "P3": { "score": 0|1|2, "justification": "..." },
            "P4": { "score": 0|1|2, "justification": "..." }
          },
          "dimension_averages": {
            "exercise_type_adherence": T,
            "difficulty_profile_adherence": D,
            "study_goal_alignment": S,
            "length_adherence": L,
            "pedagogical_quality": P
          },
          "total_score": {
            "score": full_score,
            "max": 10
          }
        }
        
        Do not include any additional commentary outside this JSON. Base all judgements strictly on the rubrics above, the study goal descriptions, and the given exercise text and metadata.
        
        After this prompt, you will receive the metadata and the exercise to rate.


        """

        response = self._openai_client.chat.completions.create(
            model="gpt-5.1",
            messages=[
                {"role": "system", "content": evaluation_prompt},
                {"role": "user", "content": exercise_text}
            ]
        )

        return response.choices[0].message.content






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


