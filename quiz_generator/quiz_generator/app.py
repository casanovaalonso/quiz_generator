import os
import json
from flask import Flask, request, jsonify
from flask_cors import CORS
from pydantic import BaseModel, Field, field_validator
from typing import List, Dict, Optional, Any
from dotenv import load_dotenv

load_dotenv()

from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

app = Flask(__name__)
CORS(app)


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
        return {
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


class QuizOutput(BaseModel):
    questions: List[QuizQuestion]


def generate_quiz(
    learning_objective: str, num_questions: int = 3
) -> List[QuizQuestion]:
    """
    Generate quiz questions based on a learning objective using the OpenAI v1.0 API.

    Args:
        learning_objective (str): The learning objective to generate questions for
        num_questions (int): Number of questions to generate (default: 3)

    Returns:
        List[QuizQuestion]: A list of structured quiz questions
    """
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
        app.logger.info("Generating quiz using OpenAI API v1.0")

        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
        )

        raw_content = completion.choices[0].message.content
        app.logger.debug(f"Raw content: {raw_content}")
        data = json.loads(raw_content)
        quiz_output = QuizOutput.model_validate(data)
        return quiz_output.questions

    except Exception as e:
        app.logger.error(f"Error generating quiz questions: {str(e)}")

        try:
            if "raw_content" in locals():
                import re

                json_pattern = r"({[\s\S]*})"
                matches = re.findall(json_pattern, raw_content)

                if matches:
                    for potential_json in matches:
                        try:
                            data = json.loads(potential_json)
                            quiz_output = QuizOutput.model_validate(data)
                            app.logger.info(
                                "Successfully extracted JSON from partial response"
                            )
                            return quiz_output.questions
                        except:
                            continue
        except:
            pass

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
        if not learning_objective:
            return jsonify({"error": "Learning objective is required"}), 400
        num_questions = max(1, min(10, num_questions))
        quiz_questions = generate_quiz(learning_objective, num_questions)
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
