import os
import json
from flask import Flask, request, jsonify
from flask_cors import CORS
from pydantic import BaseModel, Field, field_validator
from typing import List, Dict, Optional, Any, Union
from dotenv import load_dotenv
import asyncio
import logging
import requests

load_dotenv()

# OpenAI client import
from openai import OpenAI

# Initialize the client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Setup for agent-based validation
from langchain.agents import initialize_agent, AgentType
from langchain.tools import Tool
from langchain_community.utilities import DuckDuckGoSearchAPIWrapper
from langchain_openai import ChatOpenAI

app = Flask(__name__)
CORS(app)
logging.basicConfig(level=logging.INFO)

# Set up DuckDuckGo search tool for validation agent
search = DuckDuckGoSearchAPIWrapper()


# Initialize the validation agent
def duckduckgo_search(query):
    return search.run(query)


tools = [
    Tool(
        name="Search",
        func=duckduckgo_search,
        description="Useful for searching the web for information. Use targeted queries with academic terms.",
    )
]

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
agent = initialize_agent(
    tools, llm, agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION, verbose=True
)


# Define Pydantic models for validation results
class ValidationResult(BaseModel):
    is_correct: Optional[bool] = None
    explanation: str
    sources: List[str] = []


class QuizQuestion(BaseModel):
    question: str = Field(
        description="The quiz question text, specific and university-level"
    )
    option_a: str = Field(
        description="First answer option, plausible and subject-specific"
    )
    option_b: str = Field(
        description="Second answer option, plausible and subject-specific"
    )
    option_c: str = Field(
        description="Third answer option, plausible and subject-specific"
    )
    option_d: str = Field(
        description="Fourth answer option, plausible and subject-specific"
    )
    correct_answer: str = Field(
        description="The correct answer (a, b, c, or d)", pattern="^[a-d]$"
    )
    explanation: str = Field(
        description="Brief explanation of the correct answer, referencing advanced concepts or theories"
    )
    validation: Optional[ValidationResult] = None

    # Pydantic V2 validators
    @field_validator(
        "question", "option_a", "option_b", "option_c", "option_d", "explanation"
    )
    @classmethod
    def not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Field cannot be empty")
        return v.strip()

    @field_validator("correct_answer")
    @classmethod
    def valid_answer(cls, v: str) -> str:
        if v not in ["a", "b", "c", "d"]:
            raise ValueError("Correct answer must be a, b, c, or d")
        return v

    def to_api_format(self) -> Dict[str, Any]:
        result = {
            "question": self.question,
            "options": {
                "a": self.option_a,
                "b": self.option_b,
                "c": self.option_c,
                "d": self.option_d,
            },
            "correct_answer": self.correct_answer,
            "explanation": self.explanation,
        }

        if self.validation:
            result["validation"] = {
                "is_correct": self.validation.is_correct,
                "explanation": self.validation.explanation,
                "sources": self.validation.sources,
            }

        return result


class QuizOutput(BaseModel):
    questions: List[QuizQuestion]


def validate_answer(
    question_text: str, correct_answer: str, explanation: str
) -> ValidationResult:
    """
    Validates only the correct answer of a quiz question.

    Args:
        question_text (str): The text of the quiz question
        correct_answer (str): The correct answer option text
        explanation (str): The explanation for why the answer is correct

    Returns:
        ValidationResult: An object containing the validation outcome, explanation, and sources.
    """
    instructions = """
    You are a validation agent for educational quiz questions. Your task is to validate whether the provided correct answer to a quiz question is factually accurate.

    To validate the answer:
    1. Generate search queries targeting academic information about the topic.
    2. Use the search tool to find relevant information.
    3. Analyze the search results to determine if the correct answer is supported by factual information.
    4. Focus only on determining if the provided correct answer is actually correct.
    5. If the information is inconclusive or contradictory, indicate that in the result.

    Once you have gathered enough information, provide your final answer in the following JSON format:
    {
        "is_correct": true/false/null,
        "explanation": "A brief explanation of your findings about the correctness of the answer",
        "sources": ["list", "of", "source", "URLs"]
    }
    - Set "is_correct" to true if the answer is verified correct, false if it's wrong, or null if inconclusive.
    - Include at least one source if possible.
    """

    claim = f"Question: '{question_text}'\nCorrect answer: '{correct_answer}'\nExplanation: {explanation}"

    try:
        raw_result = agent.run(f"{instructions}\n\nAnswer to validate: {claim}")

        if "Final Answer:" in raw_result:
            final_answer = raw_result.split("Final Answer:")[-1].strip()
        else:
            import re

            json_match = re.search(r"({[\s\S]*})", raw_result)
            if json_match:
                final_answer = json_match.group(1)
            else:
                raise ValueError("No structured response found")

        result_dict = json.loads(final_answer)

        validation_result = ValidationResult(**result_dict)

    except json.JSONDecodeError:
        validation_result = ValidationResult(
            is_correct=None,
            explanation="Could not determine if the answer is correct. The validation system failed to parse the results.",
            sources=[],
        )
    except Exception as e:
        validation_result = ValidationResult(
            is_correct=None,
            explanation=f"Could not validate the answer: {str(e)}",
            sources=[],
        )

    return validation_result


async def validate_question(question: QuizQuestion) -> QuizQuestion:
    """
    Validates only the correct answer for a quiz question.

    Args:
        question (QuizQuestion): The quiz question to validate

    Returns:
        QuizQuestion: The question with validation results added
    """
    # Get the text of the correct answer option
    correct_option = getattr(question, f"option_{question.correct_answer}")

    # Validate only the correct answer
    validation_result = validate_answer(
        question_text=question.question,
        correct_answer=correct_option,
        explanation=question.explanation,
    )

    # Add validation results to the question
    question.validation = validation_result

    return question


async def validate_quiz_questions(questions: List[QuizQuestion]) -> List[QuizQuestion]:
    """
    Validates only the correct answers for all questions in a quiz.

    Args:
        questions (List[QuizQuestion]): The list of quiz questions to validate

    Returns:
        List[QuizQuestion]: The list of questions with validation results added
    """
    # Create validation tasks for each question
    validation_tasks = [validate_question(question) for question in questions]

    # Run validations in parallel
    validated_questions = await asyncio.gather(*validation_tasks)

    return validated_questions


def generate_quiz(
    learning_objective: str, num_questions: int = 3, validate: bool = False
) -> List[QuizQuestion]:
    """
    Generate quiz questions based on a learning objective using the OpenAI v1.0 API.

    Args:
        learning_objective (str): The learning objective to generate questions for
        num_questions (int): Number of questions to generate (default: 3)
        validate (bool): Whether to validate the correct answers (default: False)

    Returns:
        List[QuizQuestion]: A list of structured quiz questions
    """
    # TODO: add difficulty level parameter
    system_prompt = """
            You are an expert educational quiz generator specializing in creating high-quality, university-level quiz questions for higher education students. Your task is to generate multiple-choice questions that are challenging, specific, and aligned with academic rigor.

            Follow this structured approach for creating each question:
            1. **Thought**: Identify key concepts from the learning objective that require critical thinking
            2. **Action**: Create a specific, challenging question with four options (one correct)
            3. **Observation**: Verify the question meets university-level standards
            4. **Final Answer**: Format as required JSON

            OUTPUT REQUIREMENTS:
            You must produce ONLY a valid JSON object that conforms exactly to this schema:
            {
            "questions": [
                {
                "question": "Specific university-level question text",
                "option_a": "First plausible answer option",
                "option_b": "Second plausible answer option",
                "option_c": "Third plausible answer option",
                "option_d": "Fourth plausible answer option",
                "correct_answer": "a", // Must be lowercase a, b, c, or d only
                "explanation": "Brief explanation of why the answer is correct, referencing theories or concepts"
                }
                // Additional questions follow the same format
            ]
            }

            CRITICAL RULES:
            1. Output MUST be valid, parseable JSON with no additional text, markdown, or commentary
            2. Each question must be challenging and university-level
            3. Correct answer must be exactly one of: a, b, c, or d (lowercase)
            4. Do NOT include your reasoning process in the output JSON
            5. Ensure your answer is factually correct and can be verified by academic sources

            EXAMPLE OUTPUT FORMAT:
            {
            "questions": [
                {
                "question": "Which of the following best describes the principle of quantum superposition?",
                "option_a": "A quantum system can exist in multiple states simultaneously until measured",
                "option_b": "Quantum particles can teleport instantaneously between locations",
                "option_c": "Quantum systems always exist in discrete energy levels",
                "option_d": "The position and momentum of a particle cannot be simultaneously measured with precision",
                "correct_answer": "a",
                "explanation": "Quantum superposition allows quantum systems to exist as linear combinations of possible states, collapsing to a single state upon measurement, as formalized in quantum mechanical wave equations."
                }
            ]
            }
        """
    user_prompt = f"Generate {num_questions} questions for the learning objective: '{learning_objective}'."

    try:
        # Using OpenAI API v1.0 format for completions
        app.logger.info("Generating quiz using OpenAI API v1.0")

        # Request JSON output format
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
        )

        # Extract the response content
        raw_content = completion.choices[0].message.content
        app.logger.debug(f"Raw content: {raw_content}")

        # Parse the JSON content
        data = json.loads(raw_content)

        # Validate with Pydantic
        quiz_output = QuizOutput.model_validate(data)
        generated_questions = quiz_output.questions

        # Validate questions if requested
        if validate:
            app.logger.info("Validating correct answers for quiz questions")
            # We need to run the async validation in a synchronous context
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            validated_questions = loop.run_until_complete(
                validate_quiz_questions(generated_questions)
            )
            loop.close()
            return validated_questions
        else:
            return generated_questions

    except Exception as e:
        app.logger.error(f"Error generating quiz questions: {str(e)}")

        # Fallback: try to extract JSON if possible
        try:
            if "raw_content" in locals():
                # Try to extract JSON if it's embedded in other text
                import re

                json_pattern = r"({[\s\S]*})"
                matches = re.findall(json_pattern, raw_content)

                if matches:
                    # Try each potential JSON match
                    for potential_json in matches:
                        try:
                            data = json.loads(potential_json)
                            # Validate with Pydantic
                            quiz_output = QuizOutput.model_validate(data)
                            return quiz_output.questions
                        except:
                            continue
        except:
            pass

        # Last resort: return a dummy question indicating the error
        return [
            QuizQuestion(
                question="Error generating quiz question",
                option_a="Contact administrator",
                option_b="Try again later",
                option_c="Provide a different learning objective",
                option_d="Check API configuration",
                correct_answer="c",
                explanation="Failed to generate valid quiz data due to an error in processing the request.",
            )
        ]


@app.route("/generate-quiz", methods=["POST"])
def generate_quiz_endpoint():
    try:
        data = request.get_json()
        learning_objective = data.get("learning_objective", "")
        num_questions = data.get("num_questions", 3)
        validate = data.get("validate", False)  # Parameter to control validation

        # Input validation
        if not learning_objective:
            return jsonify({"error": "Learning objective is required"}), 400

        # Limit number of questions
        num_questions = max(1, min(10, num_questions))

        # Generate quiz questions
        quiz_questions = generate_quiz(learning_objective, num_questions, validate)
        quiz_data = {"questions": [q.to_api_format() for q in quiz_questions]}

        return jsonify(quiz_data)
    except Exception as e:
        app.logger.error(f"Error generating quiz: {str(e)}")
        return jsonify({"error": f"Failed to generate quiz: {str(e)}"}), 500


@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({"status": "healthy"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
